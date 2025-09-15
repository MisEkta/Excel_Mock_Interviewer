"""Core interview engine managing the interview flow and state."""
import uuid
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
import structlog

from app.database.models import Interview, Response, Evaluation
from app.database.schemas import QuestionResponse, AnswerEvaluation, FinalReport, SkillScores
from app.llm_service import llm_service
QUESTION_BANK_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "questions.json")

logger = structlog.get_logger()

class InterviewEngine:
    PHASES = [
        "introduction",
        "basic_operations", 
        "formula_proficiency",
        "data_management",
        "analysis_visualization",
        "advanced_features",
        "scenario_based",
        "conclusion"
    ]

    CATEGORY_MAP = {
        "basic_operations": "basic",
        "formula_proficiency": "intermediate", 
        "data_management": "intermediate",
        "analysis_visualization": "advanced",
        "advanced_features": "advanced",
        "scenario_based": "scenario"
    }

    PHASE_CATEGORIES = {
        "basic_operations": ["basic"],
        "formula_proficiency": ["intermediate"],
        "data_management": ["intermediate"],
        "analysis_visualization": ["advanced"],
        "advanced_features": ["advanced"],
        "scenario_based": ["scenario"]
    }

    def __init__(self, db: Session):
        self.db = db
        self.question_bank = self._load_question_bank()

    def start_interview(self, candidate_name: str) -> Tuple[str, str]:
        """Start a new interview session."""
        session_id = str(uuid.uuid4())
        interview = Interview(
            session_id=session_id,
            candidate_name=candidate_name,
            status="started",
            current_phase="introduction"
        )
        self.db.add(interview)
        self.db.commit()
        welcome_message = self._get_welcome_message(candidate_name)
        logger.info("Interview started", session_id=session_id, candidate=candidate_name)
        return session_id, welcome_message

    async def get_next_question(self, session_id: str) -> Optional[QuestionResponse]:
        """Get the next question for the interview."""
        interview = self._get_interview(session_id)
        if not interview:
            return None

        current_phase = str(interview.current_phase)
        question_index = int(getattr(interview, "current_question_index", 0) or 0)

        if current_phase == "introduction":
            interview.current_phase = "basic_operations"  # type: ignore
            interview.status = "in_progress"  # type: ignore
            interview.current_question_index = 0  # type: ignore
            self.db.commit()
            current_phase = "basic_operations"

        if current_phase == "conclusion":
            return None

        previous_responses = self._get_previous_responses(interview.id)  # type: ignore
        question = await self._get_question_for_phase(current_phase, question_index, previous_responses)

        if question:
            interview.current_question_index = question_index + 1  # type: ignore
            self.db.commit()

        return question

    async def evaluate_response(
        self, 
        session_id: str, 
        question_id: str, 
        response_text: str
    ) -> AnswerEvaluation:
        """Store candidate's response and manage interview progression (no LLM evaluation here)."""
        interview = self._get_interview(session_id)
        if not interview:
            raise ValueError("Interview not found")

        question_data = self._find_question_by_id(question_id)
        if not question_data:
            raise ValueError("Question not found")

        # Only store the response, do not evaluate
        response = Response(
            interview_id=interview.id,
            question_id=question_id,
            question_text=question_data["question"],
            candidate_response=response_text,
            category=question_data["category"],
            difficulty=question_data.get("difficulty", "medium"),
            score=0.0,  # No score yet
            feedback=""  # No feedback yet
        )
        self.db.add(response)
        self.db.commit()

        should_advance, next_question = await self._should_advance_phase(interview) # type: ignore

        if should_advance and not next_question:
            interview.status = "completed"  # type: ignore
            interview.completed_at = datetime.utcnow()  # type: ignore
            interview.current_phase = "conclusion"  # type: ignore
            self.db.commit()
            return AnswerEvaluation(score=0.0, feedback="", interview_complete=True)

        return AnswerEvaluation(score=0.0, feedback="", next_question=next_question, interview_complete=False)

    async def generate_final_report(self, session_id: str) -> Optional[FinalReport]:
        """Batch evaluate all responses and generate final report."""
        interview = self._get_interview(session_id)
        if not interview or str(interview.status) != "completed":
            return None

        responses = self.db.query(Response).filter(Response.interview_id == interview.id).all()
        if not responses:
            return None

        # Batch evaluate all responses using LLM
        batch_answers = [
            {
                "question": r.question_text,
                "candidate_response": r.candidate_response,
                "category": r.category,
                "difficulty": r.difficulty,
                "expected_topics": [],  # You can fill this if needed
            }
            for r in responses
        ]
        # Get scores and feedbacks for all answers
        batch_results = await llm_service.batch_evaluate_responses(batch_answers)

        # Update responses in DB with scores/feedback
        for r, result in zip(responses, batch_results):
            r.score = result.get("score", 0.0)
            r.feedback = result.get("feedback", "")
        self.db.commit()

        skill_scores = self._calculate_skill_scores(responses)
        overall_score = sum(skill_scores.values()) / len(skill_scores) if skill_scores else 0

        response_data = [
            {
                "category": r.category,
                "question_text": r.question_text,
                "candidate_response": r.candidate_response,
                "score": r.score,
                "feedback": r.feedback
            }
            for r in responses
        ]
        report_data = await llm_service.generate_final_report(response_data, skill_scores)

        evaluation = Evaluation(
            interview_id=interview.id,
            basic_operations_score=skill_scores.get("basic_operations", 0),
            formula_proficiency_score=skill_scores.get("formula_proficiency", 0),
            data_management_score=skill_scores.get("data_management", 0),
            analysis_visualization_score=skill_scores.get("analysis_visualization", 0),
            advanced_features_score=skill_scores.get("advanced_features", 0),
            overall_score=overall_score,
            proficiency_level=report_data.get("proficiency_level", "beginner"),
            strengths=report_data.get("strengths", []),
            weaknesses=report_data.get("weaknesses", []),
            recommendations=report_data.get("recommendations", []),
            detailed_report=report_data.get("detailed_analysis", "")
        )
        self.db.add(evaluation)
        interview.total_score = overall_score  # type: ignore
        self.db.commit()

        duration = ((interview.completed_at or datetime.utcnow()) - interview.created_at).total_seconds() / 60
        logger.info("Final report generated", session_id=session_id, overall_score=overall_score, duration_minutes=duration)

        return FinalReport(
            session_id=session_id,
            overall_score=overall_score,
            proficiency_level=report_data.get("proficiency_level", "beginner"),
            skill_scores=SkillScores(**skill_scores),
            strengths=report_data.get("strengths", []),
            weaknesses=report_data.get("weaknesses", []),
            recommendations=report_data.get("recommendations", []),
            detailed_feedback=report_data.get("detailed_analysis", ""),
            interview_duration_minutes=duration
        )

    def _get_interview(self, session_id: str) -> Optional[Interview]:
        """Get interview by session ID."""
        return self.db.query(Interview).filter(Interview.session_id == session_id).first()

    def _get_previous_responses(self, interview_id: int) -> List[Dict]:
        """Get previous responses for context."""
        responses = self.db.query(Response).filter(Response.interview_id == interview_id).all()
        return [
            {"category": r.category, "score": r.score, "question_text": r.question_text}
            for r in responses
        ]

    async def _get_question_for_phase(
        self, 
        phase: str, 
        question_index: int,
        previous_responses: List[Dict]
    ) -> Optional[QuestionResponse]:
        """Get appropriate question for current phase."""
        category = self.CATEGORY_MAP.get(phase)
        if not category:
            return None

        predefined_question = self._get_predefined_question(category, previous_responses)
        if predefined_question:
            question_id = f"{category}_{predefined_question['id']}_{uuid.uuid4().hex[:8]}"
            return QuestionResponse(
                question_id=question_id,
                question_text=predefined_question["question"],
                category=category,
                difficulty=predefined_question["difficulty"],
                expected_topics=predefined_question["expected_topics"]
            )

        difficulty = self._determine_difficulty(previous_responses, category)
        question_data = await llm_service.generate_next_question(category, difficulty, previous_responses)
        question_id = f"{category}_{difficulty}_{question_index}_{uuid.uuid4().hex[:8]}"
        return QuestionResponse(
            question_id=question_id,
            question_text=question_data["question"],
            category=question_data["category"],
            difficulty=question_data["difficulty"],
            expected_topics=question_data["expected_topics"]
        )

    def _get_predefined_question(self, category: str, previous_responses: List[Dict]) -> Optional[Dict]:
        """Get a predefined question from the question bank."""
        questions = self.question_bank.get(category, [])
        used_questions = len([r for r in previous_responses if r["category"] == category])
        if used_questions < len(questions):
            return questions[used_questions]
        return None

    def _determine_difficulty(self, previous_responses: List[Dict], category: str) -> str:
        """Determine question difficulty based on performance."""
        category_responses = [r for r in previous_responses if r["category"] == category]
        if not category_responses:
            return "easy"
        avg_score = sum(r["score"] for r in category_responses) / len(category_responses)
        if avg_score >= 80:
            return "hard"
        elif avg_score >= 60:
            return "medium"
        else:
            return "easy"

    def _calculate_skill_scores(self, responses: List[Response]) -> Dict[str, float]:
        """Calculate scores for each skill category."""
        skill_scores = {k: 0.0 for k in [
            "basic_operations", "formula_proficiency", "data_management", "analysis_visualization", "advanced_features"
        ]}
        category_map = {
            "basic": "basic_operations",
            "intermediate": ["formula_proficiency", "data_management"],
            "advanced": "analysis_visualization",
            "scenario": "advanced_features"
        }
        scores_by_category = {}
        for response in responses:
            scores_by_category.setdefault(response.category, []).append(response.score)
        for category, scores in scores_by_category.items():
            avg_score = sum(scores) / len(scores) if scores else 0
            mapped = category_map.get(category)
            if isinstance(mapped, list):
                for m in mapped:
                    skill_scores[m] = avg_score
            elif mapped:
                skill_scores[mapped] = avg_score
        return skill_scores

    def _load_question_bank(self) -> Dict:
        """Load predefined question bank."""
        try:
            logger.info("Resolved questions.json path", path=QUESTION_BANK_PATH)
            if os.path.exists(QUESTION_BANK_PATH):
                with open(QUESTION_BANK_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            logger.warning("Question bank file not found", path=QUESTION_BANK_PATH)
            return {}
        except Exception as e:
            logger.error(f"Failed to load question bank: {e}")
            return {}

    def _find_question_by_id(self, question_id: str) -> Optional[Dict]:
        """Find question data by ID."""
        for category, questions in self.question_bank.items():
            for q in questions:
                if question_id.endswith(q["id"]):
                    return {
                        "question": q["question"],
                        "category": category,
                        "difficulty": q["difficulty"],
                        "expected_topics": q["expected_topics"]
                    }
        parts = question_id.split("_")
        if len(parts) >= 2:
            return {
                "question": "Generated question",
                "category": parts[0],
                "difficulty": parts[1] if len(parts) > 1 else "medium",
                "expected_topics": ["Excel skills", "Problem solving"]
            }
        return None

    def _get_welcome_message(self, candidate_name: str) -> str:
        return (
            f"Hello {candidate_name}! Welcome to the Excel Skills Assessment Interview.\n\n"
            "I'm your AI interviewer, and I'll be evaluating your Excel knowledge through a series of questions.\n\n"
            "What to expect:\n"
            "• The interview will take approximately 25-35 minutes\n"
            "• Questions will cover different Excel skill levels\n"
            "• You can explain your answers in detail - the more specific, the better\n"
            "• There are no trick questions - just demonstrate your knowledge\n\n"
            "We'll cover:\n"
            "• Basic Excel operations and navigation\n"
            "• Formulas and functions\n"
            "• Data management and analysis\n"
            "• Advanced features and real-world scenarios\n\n"
            "Ready to begin? Let's start with some foundational questions!"
        )

    async def _should_advance_phase(self, interview) -> Tuple[bool, Optional[QuestionResponse]]:
        """
        Determines if the interview should advance to the next phase.
        Returns (should_advance, next_question).
        """
        current_phase = str(interview.current_phase)
        responses = self.db.query(Response).filter(Response.interview_id == interview.id).all()
        phase_categories = self.PHASE_CATEGORIES.get(current_phase, [])
        current_phase_responses = [r for r in responses if r.category in phase_categories]

        # Example: advance after 3 questions per phase
        if len(current_phase_responses) >= 3:
            next_phase_index = self.PHASES.index(current_phase) + 1 if current_phase in self.PHASES else len(self.PHASES)
            if next_phase_index >= len(self.PHASES):
                return True, None  # Interview complete
            next_phase = self.PHASES[next_phase_index]
            interview.current_phase = next_phase  # type: ignore
            interview.current_question_index = 0  # type: ignore
            self.db.commit()
            next_question = await self._get_question_for_phase(next_phase, 0, self._get_previous_responses(interview.id))
            return True, next_question

        next_question = await self._get_question_for_phase(
            current_phase, len(current_phase_responses), self._get_previous_responses(interview.id)
        )
        return False, next_question