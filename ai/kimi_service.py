"""
Kimi/Moonshot AI Service for resume optimization and cover letter generation.
Uses the Moonshot API (NOT .cn - your key only works on api.moonshot.ai)
"""

import json
import os
from typing import Optional
from openai import AsyncOpenAI

# Load API key
def load_moonshot_key():
    """Load from env var (Fly.io) or local file."""
    # Env var first (for Fly.io deployment)
    if os.getenv("MOONSHOT_API_KEY"):
        return os.getenv("MOONSHOT_API_KEY")
    
    # Local file fallback
    try:
        with open(os.path.expanduser("~/.clawdbot/secrets/tokens.env")) as f:
            for line in f:
                if line.startswith("MOONSHOT_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"')
    except FileNotFoundError:
        pass
    
    # Return None instead of raising - allows API to start
    return os.getenv("MOONSHOT_API_KEY", "")


class KimiResumeOptimizer:
    """Uses Kimi AI to tailor resumes and generate cover letters."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or load_moonshot_key()
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.moonshot.ai/v1"
        )
        self.model = "moonshot-v1-32k"  # Good balance of context and speed
    
    async def tailor_resume(
        self,
        resume_text: str,
        job_description: str,
        optimization_type: str = "balanced"  # aggressive, conservative, balanced
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

        response = await self.client.chat.completions.create(
            model=self.model,
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
        tone: str = "professional"  # professional, casual, enthusiastic
    ) -> str:
        """
        Generate personalized cover letter using resume facts + company research.
        """
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

        response = await self.client.chat.completions.create(
            model=self.model,
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
        """
        Answer screening questions using resume context.
        """
        existing_str = ""
        if existing_answers:
            # Check if user has pre-configured answer
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

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
    
    async def parse_resume(self, resume_text: str) -> dict:
        """
        Parse resume into structured format.
        """
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
    "certifications": ["cert1", "cert2"]
}}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        return json.loads(response.choices[0].message.content)


# Test function
async def test_kimi():
    optimizer = KimiResumeOptimizer()
    
    test_resume = """
    John Doe
    Software Engineer | john@email.com | San Francisco, CA
    
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
    """
    
    test_jd = """
    Senior Backend Engineer at CloudCo
    
    Requirements:
    - 5+ years backend development
    - Experience with cloud infrastructure (AWS/GCP)
    - Strong Python skills
    - Experience with distributed systems
    - Team leadership experience
    """
    
    result = await optimizer.tailor_resume(test_resume, test_jd)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_kimi())
