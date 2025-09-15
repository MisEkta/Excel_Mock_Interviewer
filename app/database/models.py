"""Database models for Excel Mock Interviewer."""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.db import Base


class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    candidate_name = Column(String)
    status = Column(String, default="started")  # started, in_progress, completed
    current_phase = Column(String, default="introduction")
    current_question_index = Column(Integer, default=0)
    total_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    responses = relationship("Response", back_populates="interview")
    evaluation = relationship("Evaluation", back_populates="interview", uselist=False)


class Response(Base):
    __tablename__ = "responses"
    
    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"))
    question_id = Column(String)
    question_text = Column(Text)
    candidate_response = Column(Text)
    category = Column(String)  # basic, intermediate, advanced, scenario
    difficulty = Column(String)  # easy, medium, hard
    score = Column(Float, default=0.0)
    feedback = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    interview = relationship("Interview", back_populates="responses")


class Evaluation(Base):
    __tablename__ = "evaluations"
    
    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"))
    
    # Skill scores (0-100)
    basic_operations_score = Column(Float, default=0.0)
    formula_proficiency_score = Column(Float, default=0.0)
    data_management_score = Column(Float, default=0.0)
    analysis_visualization_score = Column(Float, default=0.0)
    advanced_features_score = Column(Float, default=0.0)
    
    # Overall metrics
    overall_score = Column(Float, default=0.0)
    proficiency_level = Column(String)  # beginner, intermediate, advanced, expert
    
    # Detailed feedback
    strengths = Column(JSON)
    weaknesses = Column(JSON)
    recommendations = Column(JSON)
    detailed_report = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    interview = relationship("Interview", back_populates="evaluation")