"""
Kimi/Moonshot AI Service for resume optimization and cover letter generation.
Uses the Moonshot API with retry logic and error handling.
"""

import json
import os
import asyncio
from typing import Optional
from openai import AsyncOpenAI

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0
RETRY_BACKOFF_MULTIPLIER = 2.0


def load_moonshot_key():
    """Load from env var (Fly.io) or local file."""
    if os.getenv("MOONSHOT_API_KEY"):
        return os.getenv("MOONSHOT_API_KEY")

    try:
        with open(os.path.expanduser("~/.clawdbot/secrets/tokens.env")) as f:
            for line in f:
                if line.startswith("MOONSHOT_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"')
    except FileNotFoundError:
        pass

    return os.getenv("MOONSHOT_API_KEY", "")


async def retry_with_backoff(func, *args, max_retries=MAX_RETRIES, **kwargs):
    """Execute async function with exponential backoff retry."""
    last_error = None
    delay = RETRY_DELAY_SECONDS

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                print(f"[Kimi] Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay *= RETRY_BACKOFF_MULTIPLIER
            else:
                print(f"[Kimi] All {max_retries} attempts failed. Last error: {e}")

    raise last_error


class KimiResumeOptimizer:
    """Uses Kimi AI to tailor resumes and generate cover letters with retry logic."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or load_moonshot_key()
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.moonshot.ai/v1"
        )
        self.model = "moonshot-v1-32k"

    async def _chat_completion(self, messages, **kwargs):
        """Make a chat completion request with retry logic."""
        async def _request():
            return await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
        return await retry_with_backoff(_request)

    async def tailor_resume(
        self,
        resume_text: str,
        job_description: str,
        optimization_type: str = "balanced"
    ) -> dict:
        """
        Customize resume bullet points to match job description.
        NEVER invents new experience - only rephrases existing.
        """
        prompt = f"""You are an expert resume optimizer. Given the ORIGINAL resume below and a job description,
tailor the experience bullets to use keywords and highlight relevant experience from the ORIGINAL resume only.

CRITICAL RULES:
1. DO NOT invent new experience or skills
2. Only rephrase existing accomplishments to match the JD's language
3. Reorder skills by relevance to the JD
4. Quantify achievements where possible using ONLY data from the original

Optimization style: {optimization_type}
- conservative: Minimal changes, keep original tone
- balanced: Moderate keyword integration, professional tone
- aggressive: Maximum keyword optimization, action-oriented

ORIGINAL RESUME:
{resume_text[:6000]}

JOB DESCRIPTION:
{job_description[:4000]}

Return JSON with:
{{
    "tailored_bullets": [
        {{"company": "Company Name", "role": "Title", "bullets": ["optimized bullet 1", "optimized bullet 2"]}}
    ],
    "suggested_skills_order": ["skill1", "skill2", "skill3"],
    "cover_letter_points": ["key talking point 1", "key talking point 2"],
    "confidence_score": 0.85,
    "keyword_matches": ["keyword1", "keyword2"],
    "missing_requirements": ["requirement not in resume"]
}}"""

        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )

        return json.loads(response.choices[0].message.content)

    async def generate_cover_letter(
        self,
        resume_summary: str,
        job_title: str,
        company_name: str,
        job_requirements: str,
        company_research: str = "",
        tone: str = "professional"
    ) -> str:
        """Generate personalized cover letter using resume facts + company research."""
        prompt = f"""Write a {tone} cover letter using ONLY facts from the resume below.
Incorporate company insights naturally. Address specific JD requirements with actual experience.

RESUME FACTS:
{resume_summary[:3000]}

JOB: {job_title} at {company_name}

COMPANY CONTEXT:
{company_research[:1500] if company_research else "No specific research available."}

KEY REQUIREMENTS:
{job_requirements[:1500]}

RULES:
- Maximum 300 words
- No generic fluff ("I am writing to apply...", "I believe I would be a great fit...")
- Start with a hook about the company's mission, recent news, or a specific project
- Each paragraph should connect YOUR experience to THEIR needs
- End with a forward-looking statement about your potential contribution
- Be specific - use numbers and achievements from the resume

Write the cover letter now:"""

        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        return response.choices[0].message.content.strip()

    async def answer_application_question(
        self,
        question: str,
        resume_context: str,
        existing_answers: dict = None
    ) -> str:
        """Answer screening questions using resume context."""
        existing_str = ""
        if existing_answers:
            for key, value in existing_answers.items():
                if key.lower() in question.lower():
                    return value
            existing_str = f"\nPreviously configured answers for reference:\n{json.dumps(existing_answers, indent=2)}"

        prompt = f"""Answer this job application question based on the resume context.
Be concise, honest, and relevant. If the question asks for something not in the resume,
say so professionally rather than making things up.

QUESTION: {question}

RESUME CONTEXT:
{resume_context[:2000]}
{existing_str}

Answer (keep it concise, 1-3 sentences unless it's a longer-form question):"""

        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500
        )

        return response.choices[0].message.content.strip()

    async def parse_resume(self, resume_text: str) -> dict:
        """Parse resume into structured format."""
        prompt = f"""Parse this resume into structured JSON format.

RESUME:
{resume_text[:8000]}

Return JSON with:
{{
    "contact": {{"name": "", "email": "", "phone": "", "linkedin": "", "location": ""}},
    "summary": "Professional summary if present",
    "skills": ["skill1", "skill2"],
    "experience": [
        {{
            "company": "Company Name",
            "title": "Job Title",
            "dates": "Start - End",
            "location": "City, State",
            "bullets": ["achievement 1", "achievement 2"]
        }}
    ],
    "education": [
        {{
            "school": "University Name",
            "degree": "Degree Type",
            "field": "Field of Study",
            "dates": "Years",
            "gpa": "if mentioned"
        }}
    ],
    "projects": [
        {{"name": "", "description": "", "technologies": []}}
    ],
    "certifications": ["cert1", "cert2"],
    "clearance": "Security clearance if mentioned"
}}"""

        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        return json.loads(response.choices[0].message.content)

    async def answer_clearance_questions(
        self,
        question: str,
        clearance_level: str = None,
        resume_context: str = ""
    ) -> str:
        """Answer security clearance related questions."""
        prompt = f"""Answer this security clearance related job application question.
Be professional and direct. Only mention clearance details if explicitly asked.

QUESTION: {question}

CANDIDATE'S CLEARANCE: {clearance_level or "Not specified"}

RESUME CONTEXT:
{resume_context[:1500]}

Rules:
- Be truthful about clearance status
- Don't speculate about investigation timelines
- Keep answer concise (1-3 sentences)

Answer:"""

        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )

        return response.choices[0].message.content.strip()

    async def suggest_job_titles(self, resume_text: str) -> list:
        """Suggest relevant job titles based on resume content."""
        prompt = f"""Based on this resume, suggest 8-10 job titles that would be a good fit for this candidate.
Consider their experience, skills, and career trajectory.

RESUME:
{resume_text[:3000]}

Return ONLY a JSON array of job title strings, ordered by relevance.
Include both their current level and potential growth roles.
Mix specific titles and broader categories.

Example format:
["Software Engineer", "Senior Software Engineer", "Full Stack Developer", "Technical Lead", "Engineering Manager"]

Return the JSON array now:"""

        try:
            response = await self._chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.5,
                max_tokens=300
            )
            
            result = json.loads(response.choices[0].message.content)
            # Handle both {"titles": [...]} and [...] formats
            if isinstance(result, list):
                return result[:10]
            elif isinstance(result, dict) and "titles" in result:
                return result["titles"][:10]
            elif isinstance(result, dict):
                # Try to find any list in the response
                for value in result.values():
                    if isinstance(value, list):
                        return value[:10]
            return []
        except Exception as e:
            print(f"[Kimi] Job title suggestion failed: {e}")
            return []


async def test_kimi():
    """Test the Kimi service."""
    optimizer = KimiResumeOptimizer()

    test_resume = """
    John Doe
    Software Engineer | john@email.com | San Francisco, CA | TS/SCI Clearance

    EXPERIENCE
    Senior Software Engineer at TechCorp (2020-2024)
    - Built distributed systems handling 1M+ requests/day using Python and Go
    - Led team of 5 engineers to deliver microservices platform
    - Reduced deployment time by 60% through CI/CD improvements

    Software Engineer at StartupXYZ (2018-2020)
    - Developed REST APIs serving 100K daily users
    - Implemented real-time data pipeline with Kafka

    SKILLS
    Python, Go, AWS, Kubernetes, PostgreSQL, Redis, Docker

    CLEARANCE
    TS/SCI with CI Polygraph (Active)
    """

    test_jd = """
    Senior Backend Engineer at CloudCo

    Requirements:
    - 5+ years backend development
    - Experience with cloud infrastructure (AWS/GCP)
    - Strong Python skills
    - Experience with distributed systems
    - Active TS/SCI clearance required
    """

    result = await optimizer.tailor_resume(test_resume, test_jd)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(test_kimi())
