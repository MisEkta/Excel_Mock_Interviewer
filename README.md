# Excel Mock Interviewer

An AI-powered Excel skills assessment system that conducts interactive interviews to evaluate candidates' Excel proficiency across multiple skill levels.

## Overview

This application simulates a real interview experience where candidates answer Excel-related questions, and an AI evaluator provides detailed feedback and generates comprehensive reports. The system uses **Ollama** for local LLM processing, ensuring privacy and cost-effectiveness.

## Features

- **Interactive Interview Flow**: Progressive questioning from basic to advanced Excel concepts
- **AI-Powered Evaluation**: Intelligent assessment using Ollama LLM models
- **Comprehensive Reporting**: Detailed skill breakdown with strengths, weaknesses, and recommendations
- **Multiple Skill Categories**:
  - Basic Operations (navigation, simple formulas)
  - Formula Proficiency (VLOOKUP, complex functions)
  - Data Management (pivot tables, data validation)
  - Analysis & Visualization (charts, data analysis tools)
  - Advanced Features & Scenarios (real-world problem solving)
- **RESTful API**: Clean API endpoints for integration
- **Web Interface**: User-friendly HTML/CSS/JS frontend
- **SQLite Database**: Lightweight data storage for sessions and responses

## Technology Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite with SQLAlchemy ORM
- **LLM**: Ollama (local deployment)
- **Frontend**: HTML/CSS/JavaScript
- **Logging**: Structured logging with structlog

## Prerequisites

Before running the application, ensure you have:

1. **Python 3.8+** installed
2. **Ollama** installed and running locally
3. An Ollama model downloaded (e.g., `llama2`, `llama3`, `codellama`)

### Installing Ollama

Visit [ollama.ai](https://ollama.ai) and follow the installation instructions for your operating system.

After installation, pull a model:

```bash
ollama pull llama2
# or
ollama pull llama3
```

## Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd excel-mock-interviewer
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the project root:

   ```env
   # Ollama Configuration
   OLLAMA_API_URL=http://localhost:11434/api/generate
   OLLAMA_MODEL=llama2

   # Optional: OpenAI (if you want to use OpenAI instead)
   # OPENAI_API_KEY=your_openai_api_key_here
   # OPENAI_MODEL=gpt-3.5-turbo

   # Server Configuration
   HOST=0.0.0.0
   PORT=8000
   DEBUG=True
   LOG_LEVEL=INFO
   ```

5. **Create the questions database**
   Create a `data/questions.json` file with predefined questions:
   ```json
   {
     "basic": [
       {
         "id": "basic_001",
         "question": "How would you create a SUM formula to add values in cells A1 through A10?",
         "difficulty": "easy",
         "expected_topics": [
           "SUM function",
           "cell references",
           "basic formulas"
         ]
       }
     ],
     "intermediate": [
       {
         "id": "int_001",
         "question": "Explain how VLOOKUP works and provide an example of when you'd use it.",
         "difficulty": "medium",
         "expected_topics": ["VLOOKUP", "lookup functions", "data retrieval"]
       }
     ],
     "advanced": [
       {
         "id": "adv_001",
         "question": "How would you create a dynamic chart that updates automatically when new data is added?",
         "difficulty": "hard",
         "expected_topics": [
           "dynamic charts",
           "named ranges",
           "data visualization"
         ]
       }
     ]
   }
   ```

## Running the Application

1. **Start Ollama server** (if not already running)

   ```bash
   ollama serve
   ```

2. **Run the FastAPI server**

   ```bash
   python run.py
   ```

   Or use uvicorn directly:

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Access the application**
   - Web Interface: http://localhost:8000/interview.html
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/api/v1/health

## Project Structure

```
excel-mock-interviewer/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration settings
│   ├── api_routes.py        # API route definitions
│   ├── interview_engine.py  # Core interview logic
│   ├── llm_service.py      # Ollama LLM integration
│   └── database/
│       ├── __init__.py
│       ├── db.py           # Database connection setup
│       ├── models.py       # SQLAlchemy models
│       └── schemas.py      # Pydantic schemas
├── data/
│   └── questions.json      # Predefined question bank
├── static/
│   ├── interview.html      # Web interface
│   ├── interview.css       # Styling
│   └── interview.js        # Frontend logic
├── requirements.txt
├── run.py                  # Application runner
└── README.md
```

## API Endpoints

### Interview Management

- `POST /api/v1/interviews/start` - Start new interview
- `GET /api/v1/interviews/{session_id}/next-question` - Get next question
- `POST /api/v1/interviews/answer` - Submit answer
- `POST /api/v1/interviews/{session_id}/end` - End interview early

### Status & Reports

- `GET /api/v1/interviews/{session_id}/status` - Get interview status
- `GET /api/v1/interviews/{session_id}/report` - Get final report
- `GET /api/v1/interviews/{session_id}/responses` - Get all responses (admin)

### Utility

- `GET /api/v1/health` - Health check
- `DELETE /api/v1/interviews/{session_id}` - Delete interview data

## Usage Example

1. **Start an interview**

   ```bash
   curl -X POST "http://localhost:8000/api/v1/interviews/start" \
        -H "Content-Type: application/json" \
        -d '{"candidate_name": "John Doe"}'
   ```

2. **Get next question**

   ```bash
   curl "http://localhost:8000/api/v1/interviews/{session_id}/next-question"
   ```

3. **Submit answer**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/interviews/answer" \
        -H "Content-Type: application/json" \
        -d '{
          "session_id": "session_id_here",
          "question_id": "question_id_here",
          "response": "I would use =SUM(A1:A10) to add all values in that range."
        }'
   ```

## Configuration

Key configuration options in `config.py`:

- `OLLAMA_API_URL`: Ollama server endpoint (default: http://localhost:11434/api/generate)
- `OLLAMA_MODEL`: Model to use (default: llama2)
- `MAX_INTERVIEW_DURATION`: Maximum interview length in minutes
- `QUESTIONS_PER_CATEGORY`: Number of questions per skill category
- `DATABASE_URL`: SQLite database path

## Troubleshooting

### Common Issues

1. **Ollama Connection Error**

   - Ensure Ollama is installed and running: `ollama serve`
   - Check the model is available: `ollama list`
   - Verify the API URL in your `.env` file

2. **Database Issues**

   - The SQLite database is created automatically
   - Check file permissions in the project directory
   - Delete `excel_interviewer.db` to reset the database

3. **LLM Response Issues**

   - Try a different Ollama model (llama3, codellama, etc.)
   - Increase timeout settings in `llm_service.py`
   - Check Ollama logs: `ollama logs`

4. **Performance Issues**
   - Use a smaller model for faster responses (e.g., llama2:7b vs llama2:13b)
   - Increase system resources allocated to Ollama
   - Consider using OpenAI API for production deployments

## Development

### Adding New Question Categories

1. Update `PHASES` and `CATEGORY_MAP` in `interview_engine.py`
2. Add questions to `data/questions.json`
3. Update skill scoring logic in `_calculate_skill_scores()`

### Customizing Evaluation Criteria

Modify the evaluation prompts in `llm_service.py`:

- `_build_evaluation_prompt()` for answer scoring
- `generate_final_report()` for report generation

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests (if test suite exists)
pytest tests/
```

## Production Deployment

For production use:

1. **Use environment variables** for all sensitive configuration
2. **Configure proper CORS** settings in `main.py`
3. **Use a production WSGI server** like Gunicorn
4. **Set up proper logging** and monitoring
5. **Consider PostgreSQL** instead of SQLite for better performance
6. **Implement rate limiting** and authentication as needed

Example production startup:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

For issues and questions:

- Check the API documentation at `/docs`
- Review the application logs
- Ensure Ollama is properly configured and running
