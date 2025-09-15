"""API routes for Excel Mock Interviewer."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import structlog

from app.database.db import get_db
from app.database.schemas import (
    InterviewStart, InterviewResponse, CandidateAnswer, 
    AnswerEvaluation, FinalReport, InterviewStatus
)
from app.interview_engine import InterviewEngine
from app.database.models import Interview, Response, Evaluation

logger = structlog.get_logger()
router = APIRouter()

# Interview endpoints
@router.post("/interviews/start", response_model=InterviewResponse)
async def start_interview(
    request: InterviewStart,
    db: Session = Depends(get_db)
):
    """Start a new interview session."""
    try:
        engine = InterviewEngine(db)
        session_id, welcome_message = engine.start_interview(request.candidate_name)
        
        return InterviewResponse(
            session_id=session_id,
            status="started",
            current_phase="introduction",
            message=welcome_message
        )
    except Exception as e:
        logger.error("Failed to start interview", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start interview"
        )


@router.get("/interviews/{session_id}/next-question")
async def get_next_question(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get the next question for the interview."""
    try:
        engine = InterviewEngine(db)
        question = await engine.get_next_question(session_id)
        
        if not question:
            return {"message": "Interview completed or no more questions available"}
        
        return question
    except Exception as e:
        logger.error("Failed to get next question", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve next question"
        )


@router.post("/interviews/answer", response_model=AnswerEvaluation)
async def submit_answer(
    request: CandidateAnswer,
    db: Session = Depends(get_db)
):
    """Submit and evaluate a candidate's answer."""
    try:
        engine = InterviewEngine(db)
        evaluation = await engine.evaluate_response(
            request.session_id,
            request.question_id,
            request.response
        )
        
        return evaluation
    except ValueError as e:
        logger.warning("Invalid request", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to evaluate answer", session_id=request.session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate answer"
        )


@router.get("/interviews/{session_id}/status", response_model=InterviewStatus)
async def get_interview_status(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get current interview status."""
    try:
        interview = db.query(Interview).filter(
            Interview.session_id == session_id
        ).first()
        
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found"
            )
        
        # Count responses
        response_count = db.query(Response).filter(
            Response.interview_id == interview.id
        ).count()
        
        # Calculate elapsed time
        elapsed_time = 0
        if interview.created_at is not None:
            from datetime import datetime
            elapsed_time = (datetime.utcnow() - interview.created_at).total_seconds() / 60
        
        return InterviewStatus(
            session_id=session_id,
            status=interview.status,  # type: ignore
            current_phase=interview.current_phase,  # type: ignore
            questions_answered=response_count,
            total_questions=15,  # Estimated total
            current_score=interview.total_score,  # type: ignore
            elapsed_time_minutes=elapsed_time
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get interview status", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve interview status"
        )


@router.post("/interviews/{session_id}/end")
async def end_interview(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Allow candidate to end the interview early."""
    try:
        interview = db.query(Interview).filter(
            Interview.session_id == session_id
        ).first()
        
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found"
            )
        
        interview.status = "completed"  # type: ignore
        interview.current_phase = "conclusion"  # type: ignore
        from datetime import datetime
        interview.completed_at = datetime.utcnow()  # type: ignore
        db.commit()
        
        return {"message": "Interview ended by candidate."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to end interview", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end interview"
        )


# Report endpoints
@router.get("/interviews/{session_id}/report", response_model=FinalReport)
async def get_final_report(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get the final interview report."""
    try:
        engine = InterviewEngine(db)
        report = await engine.generate_final_report(session_id)
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not available. Interview may not be completed."
            )
        
        return report
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate report", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate final report"
        )


@router.get("/interviews/{session_id}/responses")
async def get_interview_responses(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get all responses for an interview (for debugging/admin)."""
    try:
        interview = db.query(Interview).filter(
            Interview.session_id == session_id
        ).first()
        
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found"
            )
        
        responses = db.query(Response).filter(
            Response.interview_id == interview.id
        ).all()
        
        return {
            "interview_id": interview.id,
            "session_id": session_id,
            "candidate_name": interview.candidate_name,
            "status": interview.status,
            "responses": [
                {
                    "question_id": r.question_id,
                    "question_text": r.question_text,
                    "candidate_response": r.candidate_response,
                    "category": r.category,
                    "difficulty": r.difficulty,
                    "score": r.score,
                    "feedback": r.feedback,
                    "timestamp": r.timestamp
                }
                for r in responses
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get interview responses", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve interview responses"
        )


@router.delete("/interviews/{session_id}")
async def delete_interview(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Delete an interview and all associated data."""
    try:
        interview = db.query(Interview).filter(
            Interview.session_id == session_id
        ).first()
        
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found"
            )
        
        # Delete associated responses and evaluations
        db.query(Response).filter(Response.interview_id == interview.id).delete()
        db.query(Evaluation).filter(Evaluation.interview_id == interview.id).delete()
        
        # Delete interview
        db.delete(interview)
        db.commit()
        
        return {"message": "Interview deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete interview", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete interview"
        )


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Excel Mock Interviewer API"}