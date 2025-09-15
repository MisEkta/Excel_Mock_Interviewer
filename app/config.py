"""Simple configuration for Excel Mock Interviewer."""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database
    DATABASE_URL = "sqlite:///./excel_interviewer.db"
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    # Ollama
    OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")
    
    # Interview Settings
    MAX_INTERVIEW_DURATION = 35  # minutes
    QUESTIONS_PER_CATEGORY = 3
    
    # App Settings
    DEBUG = True
    LOG_LEVEL = "INFO"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    # File Paths
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    QUESTION_BANK_PATH = os.path.join(PROJECT_ROOT, "data", "questions.json")

settings = Settings()