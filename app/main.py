"""Main FastAPI application for Excel Mock Interviewer."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import time

from app.config import settings
from app.database.db import init_db
from app.api_routes import router  # <-- FIXED IMPORT

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="Excel Mock Interviewer API",
    description="AI-powered Excel skills assessment through conversational interviews",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else None
    )
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        "Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        process_time=process_time
    )
    return response

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception",
        error=str(exc),
        method=request.method,
        url=str(request.url)
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Include API routes
app.include_router(router, prefix="/api/v1")  # <-- FIXED ROUTER REGISTRATION

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Excel Mock Interviewer API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Excel Mock Interviewer API")
    init_db()
    logger.info("Database initialized")
    if not settings.OPENAI_API_KEY:
        logger.warning("OpenAI API key not configured - LLM features may not work")
    logger.info("Application startup complete")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Excel Mock Interviewer API")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )