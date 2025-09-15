"""Pydantic schemas for API requests and responses."""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog
logger = structlog.get_logger()

class InterviewStart(BaseModel):
    candidate_name: str


class InterviewResponse(BaseModel):
    session_id: str
    status: str
    current_phase: str
    message: str


class QuestionResponse(BaseModel):
    question_id: str
    question_text: str
    category: str
    difficulty: str
    expected_topics: List[str]


class CandidateAnswer(BaseModel):
    session_id: str
    question_id: str
    response: str


class AnswerEvaluation(BaseModel):
    score: float
    feedback: str
    next_question: Optional[QuestionResponse] = None
    interview_complete: bool = False


class SkillScores(BaseModel):
    basic_operations: float
    formula_proficiency: float
    data_management: float
    analysis_visualization: float
    advanced_features: float


class FinalReport(BaseModel):
    session_id: str
    overall_score: float
    proficiency_level: str
    skill_scores: SkillScores
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    detailed_feedback: str
    interview_duration_minutes: float


class InterviewStatus(BaseModel):
    session_id: str
    status: str
    current_phase: str
    questions_answered: int
    total_questions: int
    current_score: float
    elapsed_time_minutes: float