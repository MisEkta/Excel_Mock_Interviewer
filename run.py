"""Simple script to run the Excel Mock Interviewer API."""
import os
from dotenv import load_dotenv
import uvicorn
from app.config import settings

load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )