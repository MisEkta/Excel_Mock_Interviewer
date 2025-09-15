"""Enhanced LLM service with improved error handling and fallback mechanisms."""
import httpx
import json
import asyncio
import re
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import structlog
from app.config import settings

logger = structlog.get_logger()

# Response models for type safety
class QuestionData(BaseModel):
    question: str
    category: str
    difficulty: str
    expected_topics: List[str]
    sample_answer: str

class EvaluationResult(BaseModel):
    score: float
    feedback: str

class ReportData(BaseModel):
    executive_summary: str
    proficiency_level: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    detailed_analysis: str
    next_steps: str

class LLMService:
    def __init__(self):
        self.model = settings.OLLAMA_MODEL
        self.api_url = settings.OLLAMA_API_URL
        self.timeout = 1000  # Increase timeout
        self.max_retries = 3
        
    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _ollama_generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.3) -> str:
        """Enhanced Ollama API call with retry logic and better error handling."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_k": 40,
                "top_p": 0.9
            },
            "stream": False
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                logger.info("Making LLM request", model=self.model, prompt_length=len(prompt))
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                if not data.get("response"):
                    logger.error("Ollama returned empty response", data=data)
                    raise ValueError("Empty response from LLM")
                
                content = data["response"].strip()
                logger.info("LLM response received", response_length=len(content))
                return content
                
            except httpx.TimeoutException:
                logger.error("LLM request timeout", timeout=self.timeout)
                # Fallback: return a message indicating timeout
                return json.dumps({
                    "executive_summary": "Report generation timed out.",
                    "proficiency_level": "unknown",
                    "strengths": [],
                    "weaknesses": [],
                    "recommendations": [],
                    "detailed_analysis": "The LLM did not respond in time. Please try again later.",
                    "next_steps": ""
                })
            except httpx.HTTPStatusError as e:
                logger.error("LLM HTTP error", status_code=e.response.status_code, response=e.response.text)
                raise
            except Exception as e:
                logger.error("LLM request failed", error=str(e), error_type=type(e).__name__)
                raise

    def _extract_json_from_response(self, content: str) -> Optional[Dict]:
        """Extract JSON from LLM response with multiple strategies."""
        # Try direct JSON
        try:
            return json.loads(content)
        except Exception:
            pass
        # Try extracting JSON array/object
        match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        # Try extracting from code block
        if '```json' in content:
            start = content.find('```json') + 7
            end = content.find('```', start)
            json_content = content[start:end].strip()
            try:
                return json.loads(json_content)
            except Exception:
                pass
        logger.warning("Could not extract JSON from LLM response", content_preview=content[:200])
        return None

    async def batch_evaluate_responses(self, batch_answers: List[Dict]) -> List[Dict]:
        """Enhanced batch evaluation with better prompting and error handling."""
        if not batch_answers:
            return []
            
        # Process in smaller chunks to avoid token limits
        chunk_size = 3
        all_results = []
        
        for i in range(0, len(batch_answers), chunk_size):
            chunk = batch_answers[i:i + chunk_size]
            
            prompt = self._build_evaluation_prompt(chunk)
            
            try:
                content = await self._ollama_generate(prompt, max_tokens=1000, temperature=0.2)
                results = self._extract_json_from_response(content)
                
                if results and isinstance(results, list) and len(results) == len(chunk):
                    # Validate each result
                    validated_results = []
                    for result in results:
                        try:
                            eval_result = EvaluationResult(**result)
                            validated_results.append({
                                "score": max(0, min(100, eval_result.score)),  # Clamp score
                                "feedback": eval_result.feedback[:500]  # Limit feedback length
                            })
                        except ValidationError:
                            validated_results.append({
                                "score": 50.0,
                                "feedback": "Evaluation could not be completed. Manual review recommended."
                            })
                    all_results.extend(validated_results)
                else:
                    # Fallback for failed parsing
                    all_results.extend(self._generate_fallback_evaluations(chunk))
                    
            except Exception as e:
                logger.error("Batch evaluation failed for chunk", chunk_size=len(chunk), error=str(e))
                all_results.extend(self._generate_fallback_evaluations(chunk))
                
        return all_results

    def _build_evaluation_prompt(self, answers: List[Dict]) -> str:
        """Build a well-structured evaluation prompt."""
        return f"""You are an expert Excel interviewer evaluating candidate responses.

EVALUATION CRITERIA:
- Technical Accuracy (40%): Is the answer technically correct?
- Completeness (30%): Does it fully address the question?
- Clarity (20%): Is the explanation clear and well-structured?
- Practical Application (10%): Shows real-world understanding?

SCORING SCALE:
- 90-100: Excellent, comprehensive answer with advanced insights
- 80-89: Good answer, covers most key points accurately
- 70-79: Adequate answer, basic understanding demonstrated
- 60-69: Partial answer, some gaps in knowledge
- 50-59: Weak answer, significant misunderstandings
- Below 50: Incorrect or inadequate response

ANSWERS TO EVALUATE:
{json.dumps(answers, indent=2)}

Respond ONLY with a valid JSON array. Do NOT include any explanation, markdown, or extra text.
[
  {{
    "score": <number between 0-100>,
    "feedback": "<specific, constructive feedback explaining the score>"
  }}
]"""

    def _generate_fallback_evaluations(self, answers: List[Dict]) -> List[Dict]:
        """Generate fallback evaluations when LLM fails."""
        return [
            {
                "score": 60.0,  # Neutral score
                "feedback": "System evaluation unavailable. Response shows basic Excel understanding. Manual review recommended for detailed feedback."
            }
            for _ in answers
        ]

    async def generate_next_question(
        self, 
        category: str, 
        difficulty: str, 
        previous_responses: List[Dict]
    ) -> Dict:
        """Generate contextual next question with improved prompting."""
        context = self._build_performance_context(previous_responses)
        
        prompt = f"""Generate a specific Excel interview question.

CATEGORY: {category}
DIFFICULTY: {difficulty}

CATEGORY DEFINITIONS:
- basic: Navigation, simple formulas (SUM, AVERAGE), basic formatting
- intermediate: VLOOKUP, pivot tables, conditional formatting, data validation
- advanced: Complex formulas, charts, data analysis tools
- scenario: Real business problems requiring Excel solutions

{context}

QUESTION REQUIREMENTS:
- Be specific and actionable
- Include clear context if needed
- Avoid yes/no questions
- Focus on practical application

Respond with valid JSON:
{{
  "question": "Clear, specific question about Excel functionality",
  "category": "{category}",
  "difficulty": "{difficulty}",
  "expected_topics": ["topic1", "topic2", "topic3"],
  "sample_answer": "Comprehensive model answer"
}}"""

        try:
            content = await self._ollama_generate(prompt, max_tokens=500, temperature=0.4)
            question_data = self._extract_json_from_response(content)
            
            if question_data:
                try:
                    validated = QuestionData(**question_data)
                    return validated.dict()
                except ValidationError as e:
                    logger.warning("Question validation failed", error=str(e))
                    
        except Exception as e:
            logger.error("Question generation failed", error=str(e))
            
        return self._get_fallback_question(category, difficulty)

    def _build_performance_context(self, previous_responses: List[Dict]) -> str:
        """Build performance context for question generation."""
        if not previous_responses:
            return "CONTEXT: This is the candidate's first question."
            
        scores = [r.get("score", 0) for r in previous_responses if isinstance(r.get("score"), (int, float))]
        if not scores:
            return "CONTEXT: Previous responses available but not yet evaluated."
            
        avg_score = sum(scores) / len(scores)
        
        if avg_score >= 80:
            performance = "excellent"
            adjustment = "Challenge them with advanced concepts."
        elif avg_score >= 65:
            performance = "good"
            adjustment = "Maintain current difficulty level."
        else:
            performance = "needs improvement"
            adjustment = "Focus on fundamental concepts."
            
        return f"""CONTEXT: 
- Questions answered: {len(previous_responses)}
- Average performance: {performance} ({avg_score:.1f}/100)
- Adjustment: {adjustment}"""

    async def generate_final_report(
        self, 
        responses: List[Dict], 
        skill_scores: Dict[str, float]
    ) -> Dict:
        """Generate comprehensive final report with enhanced analysis."""
        if not responses:
            return self._get_fallback_report(0, skill_scores)
            
        overall_score = sum(skill_scores.values()) / len(skill_scores) if skill_scores else 0
        
        # Analyze response patterns
        analysis = self._analyze_response_patterns(responses, skill_scores)
        
        prompt = f"""Generate a comprehensive Excel skills assessment report.

INTERVIEW DATA:
- Total Questions: {len(responses)}
- Overall Score: {overall_score:.1f}/100
- Skill Breakdown: {json.dumps(skill_scores, indent=2)}

PERFORMANCE ANALYSIS:
{analysis}

REPORT REQUIREMENTS:
- Professional tone
- Specific, actionable feedback
- Evidence-based conclusions
- Clear improvement roadmap

Respond with valid JSON:
{{
  "executive_summary": "2-3 sentence professional overview",
  "proficiency_level": "beginner|intermediate|advanced|expert",
  "strengths": ["strength1", "strength2", "strength3"],
  "weaknesses": ["weakness1", "weakness2", "weakness3"],
  "recommendations": ["actionable recommendation1", "actionable recommendation2"],
  "detailed_analysis": "Comprehensive paragraph analyzing performance across all areas",
  "next_steps": "Specific learning path with priorities"
}}"""

        try:
            content = await self._ollama_generate(prompt, max_tokens=1200, temperature=0.3)
            report_data = self._extract_json_from_response(content)
            
            if report_data:
                try:
                    validated = ReportData(**report_data)
                    return validated.dict()
                except ValidationError as e:
                    logger.warning("Report validation failed", error=str(e))
                    
        except Exception as e:
            logger.error("Report generation failed", error=str(e))
            
        return self._get_fallback_report(overall_score, skill_scores)

    def _analyze_response_patterns(self, responses: List[Dict], skill_scores: Dict[str, float]) -> str:
        """Analyze response patterns to provide context for report generation."""
        category_performance = {}
        for response in responses:
            category = response.get("category", "unknown")
            score = response.get("score", 0)
            if category not in category_performance:
                category_performance[category] = []
            category_performance[category].append(score)
        
        analysis_points = []
        for category, scores in category_performance.items():
            avg_score = sum(scores) / len(scores)
            analysis_points.append(f"- {category.title()}: {avg_score:.1f}/100 ({len(scores)} questions)")
        
        return "\n".join(analysis_points) if analysis_points else "- Limited response data available"

    def _get_fallback_question(self, category: str, difficulty: str) -> Dict:
        """Enhanced fallback questions."""
        questions = {
            "basic": {
                "easy": {
                    "question": "Walk me through how you would create a formula to calculate the total of cells A1 through A10, and explain what happens when you copy this formula to another column.",
                    "expected_topics": ["SUM function", "cell references", "formula copying", "relative references"],
                    "sample_answer": "I would use =SUM(A1:A10). When copied to column B, it automatically becomes =SUM(B1:B10) due to relative referencing."
                },
                "medium": {
                    "question": "Describe how you would format a range of cells to highlight values above a certain threshold, and explain the business value of this approach.",
                    "expected_topics": ["conditional formatting", "formatting rules", "data visualization", "business application"],
                    "sample_answer": "Use conditional formatting with a rule like 'Cell Value > threshold' to apply highlighting. This helps quickly identify outliers or targets in business data."
                }
            },
            "intermediate": {
                "medium": {
                    "question": "Explain the difference between VLOOKUP and INDEX-MATCH functions, and when you would choose one over the other.",
                    "expected_topics": ["VLOOKUP", "INDEX", "MATCH", "lookup functions", "performance comparison"],
                    "sample_answer": "VLOOKUP searches left-to-right only and can be slower. INDEX-MATCH can look in any direction and is more flexible and faster for large datasets."
                }
            }
        }
        
        question_data = questions.get(category, {}).get(difficulty, questions["basic"]["easy"])
        
        return {
            "question": question_data["question"],
            "category": category,
            "difficulty": difficulty,
            "expected_topics": question_data["expected_topics"],
            "sample_answer": question_data["sample_answer"]
        }

    def _get_fallback_report(self, overall_score: float, skill_scores: Dict) -> Dict:
        """Enhanced fallback report."""
        if overall_score >= 85:
            proficiency = "advanced"
            summary = "demonstrates strong Excel proficiency with advanced skills"
        elif overall_score >= 70:
            proficiency = "intermediate"
            summary = "shows solid Excel fundamentals with room for advanced growth"
        elif overall_score >= 55:
            proficiency = "beginner"
            summary = "displays basic Excel understanding requiring significant development"
        else:
            proficiency = "novice"
            summary = "needs foundational Excel training before advancing"

        return {
            "executive_summary": f"Candidate {summary} based on comprehensive skills assessment.",
            "proficiency_level": proficiency,
            "strengths": ["Shows willingness to learn", "Communicates clearly", "Attempts problem-solving"],
            "weaknesses": ["Needs more hands-on practice", "Should strengthen core concepts"],
            "recommendations": [
                "Complete structured Excel fundamentals course",
                "Practice daily with real datasets",
                "Focus on formula and function mastery"
            ],
            "detailed_analysis": f"Assessment completed with overall performance of {overall_score:.1f}/100. Systematic improvement in identified weak areas will enhance Excel capabilities significantly.",
            "next_steps": "Begin with Excel basics certification, then progress to intermediate features based on improved competency."
        }

# Global service instance
llm_service = LLMService()