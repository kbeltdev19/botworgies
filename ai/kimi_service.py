#!/usr/bin/env python3
"""
Kimi (Moonshot) AI Service - Compatibility Layer

Provides KimiResumeOptimizer used by API/tests, backed by Moonshot's
OpenAI-compatible chat completions API.
"""

import os
import re
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class _ChoiceMessage:
    content: str


@dataclass
class _Choice:
    message: _ChoiceMessage


@dataclass
class _ChatCompletionResponse:
    choices: List[_Choice]


def _safe_json_loads(text: str) -> Any:
    """Parse JSON from text with relaxed extraction."""
    text = text.strip()
    if not text:
        return None

    # Direct JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip code fences
    if "```" in text:
        # Try json fenced block first
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        else:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()

    # Extract JSON object/array from content
    obj_start = text.find("{")
    arr_start = text.find("[")
    if arr_start != -1 and (obj_start == -1 or arr_start < obj_start):
        start = arr_start
        end = text.rfind("]") + 1
    else:
        start = obj_start
        end = text.rfind("}") + 1

    if start != -1 and end > start:
        snippet = text[start:end]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return None

    return None


class KimiResumeOptimizer:
    """
    Moonshot (Kimi) AI service wrapper.

    Methods:
      - parse_resume
      - tailor_resume
      - generate_cover_letter
      - answer_application_question
      - suggest_job_titles
      - suggest_job_search_config
    """

    # Keep Moonshot/Kimi model configuration independent from Stagehand's MODEL_NAME.
    DEFAULT_MODEL = os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k-vision-preview")
    DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries

        self.system_prompt = (
            "You are a careful resume assistant. "
            "Be truthful and accurate. "
            "Do not fabricate, hallucinate, or invent experience, skills, companies, dates, or credentials. "
            "Only use information explicitly present in the provided resume text. "
            "If something is missing, leave it blank or say 'unknown'."
        )

    async def _chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> _ChatCompletionResponse:
        """Call Moonshot chat completions API."""
        if not self.api_key:
            raise RuntimeError("MOONSHOT_API_KEY not configured")

        last_error = None
        for attempt in range(self.max_retries):
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                    ) as resp:
                        data = await resp.json()
                        content = data["choices"][0]["message"]["content"]
                        return _ChatCompletionResponse(
                            choices=[_Choice(message=_ChoiceMessage(content=content))]
                        )
            except Exception as e:
                last_error = e
                await asyncio.sleep(1 + attempt)

        raise RuntimeError(f"Moonshot request failed: {last_error}")

    async def parse_resume(self, resume_text: str) -> Dict[str, Any]:
        """Parse resume text into structured data."""
        schema = {
            "contact": {
                "name": "string",
                "email": "string",
                "phone": "string",
                "linkedin": "string",
                "location": "string",
                "website": "string",
            },
            "summary": "string",
            "skills": ["string"],
            "experience": [
                {
                    "company": "string",
                    "title": "string",
                    "dates": "string",
                    "location": "string",
                    "bullets": ["string"],
                }
            ],
            "education": [
                {
                    "school": "string",
                    "degree": "string",
                    "field": "string",
                    "dates": "string",
                    "gpa": "string",
                }
            ],
            "projects": [
                {
                    "name": "string",
                    "description": "string",
                    "technologies": ["string"],
                }
            ],
            "certifications": ["string"],
            "clearance": "string",
        }

        prompt = (
            "Parse the resume into JSON following this schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            "Resume:\n"
            f"{resume_text}\n\n"
            "Return ONLY valid JSON. Do not add fields not in the schema."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self._chat_completion(messages, max_tokens=2000)
            data = _safe_json_loads(response.choices[0].message.content) or {}
        except Exception as e:
            logger.warning(f"[Kimi] parse_resume failed: {e}")
            data = {}

        # Ensure keys exist
        data.setdefault("contact", {})
        data.setdefault("summary", "")
        data.setdefault("skills", [])
        data.setdefault("experience", [])
        data.setdefault("education", [])
        data.setdefault("projects", [])
        data.setdefault("certifications", [])
        data.setdefault("clearance", None)

        if not data.get("summary"):
            data["summary"] = await self.generate_summary(resume_text)

        return data

    async def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> str:
        """
        Generic text generation helper used by other modules (e.g., form intelligence).
        """
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt or self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        response = await self._chat_completion(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()

    async def generate_summary(self, resume_text: str) -> str:
        """Generate a professional summary from resume text."""
        prompt = (
            "Write a 2-3 sentence professional summary based only on this resume. "
            "Do not invent details.\n\n"
            f"{resume_text}\n\n"
            "Return only the summary text."
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        try:
            response = await self._chat_completion(messages, max_tokens=300)
            return response.choices[0].message.content.strip()
        except Exception:
            # Fallback: first 2-3 lines
            lines = [ln.strip() for ln in resume_text.splitlines() if ln.strip()]
            return " ".join(lines[:2])[:400]

    async def tailor_resume(
        self,
        resume_text: str,
        job_description: str,
        optimization_type: str = "balanced",
    ) -> Dict[str, Any]:
        """Tailor resume to a job description."""
        style = {
            "conservative": "minimal edits, preserve wording",
            "balanced": "moderate edits, highlight relevance",
            "aggressive": "strongly emphasize relevant achievements",
        }.get(optimization_type, "moderate edits")

        prompt = (
            "Tailor this resume for the job description.\n\n"
            "Instructions:\n"
            "1) Only rephrase or reorder existing content.\n"
            "2) DO NOT invent new experience, companies, dates, or skills.\n"
            "3) Provide a tailored summary and 3-6 tailored bullet points.\n"
            f"Optimization style: {style}\n\n"
            f"RESUME:\n{resume_text}\n\n"
            f"JOB DESCRIPTION:\n{job_description}\n\n"
            "Respond with JSON:\n"
            "{\n"
            '  "summary": "string",\n'
            '  "highlighted_skills": ["string"],\n'
            '  "tailored_bullets": ["string"],\n'
            '  "keywords_to_add": ["string"]\n'
            "}"
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self._chat_completion(messages, max_tokens=1200)
            data = _safe_json_loads(response.choices[0].message.content) or {}
        except Exception as e:
            logger.warning(f"[Kimi] tailor_resume failed: {e}")
            data = {}

        data.setdefault("summary", "")
        data.setdefault("highlighted_skills", [])
        data.setdefault("tailored_bullets", [])
        data.setdefault("keywords_to_add", [])
        return data

    async def generate_cover_letter(
        self,
        resume_summary: str,
        job_title: str,
        company_name: str,
        job_requirements: str,
        tone: str = "professional",
    ) -> str:
        """Generate a cover letter."""
        prompt = (
            "Write a concise cover letter (250-400 words).\n"
            "Use only the candidate background provided. Do not invent experience.\n\n"
            f"JOB TITLE: {job_title}\n"
            f"COMPANY: {company_name}\n"
            f"JOB REQUIREMENTS: {job_requirements}\n\n"
            f"CANDIDATE SUMMARY:\n{resume_summary}\n\n"
            f"TONE: {tone}\n\n"
            "Return only the cover letter text."
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        try:
            response = await self._chat_completion(messages, max_tokens=1200)
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"[Kimi] generate_cover_letter failed: {e}")
            return (
                f"Dear Hiring Manager,\n\n"
                f"I am excited to apply for the {job_title} role at {company_name}. "
                "Based on my background, I believe I can contribute meaningfully to this position.\n\n"
                f"Key qualifications:\n{resume_summary[:800]}\n\n"
                "Thank you for your time and consideration.\n"
            )

    async def answer_application_question(
        self,
        question: str,
        context: str = "",
        resume_context: Optional[str] = None,
        existing_answers: Optional[Dict[str, str]] = None,
    ) -> str:
        """Answer an application question truthfully based on provided context."""
        if resume_context and not context:
            context = resume_context

        prompt = (
            "Answer this job application question truthfully and concisely.\n"
            "Only use the provided context. If unknown, say 'Not specified'.\n\n"
            f"QUESTION: {question}\n\n"
            f"CONTEXT: {context}\n\n"
        )
        if existing_answers:
            prompt += f"KNOWN ANSWERS: {json.dumps(existing_answers)}\n\n"

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        try:
            response = await self._chat_completion(messages, max_tokens=300)
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"[Kimi] answer_application_question failed: {e}")
            return "Not specified"

    async def suggest_job_titles(self, resume_text: str, count: int = 10) -> List[Dict[str, Any]]:
        """Suggest job titles based on resume text."""
        prompt = (
            "Suggest job titles that fit this resume.\n"
            "Return a JSON array of objects with fields:\n"
            "title, relevance_score (0-100), reason, experience_level (entry|mid|senior|executive), keywords.\n\n"
            f"RESUME:\n{resume_text}\n\n"
            f"Return up to {count} suggestions."
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        try:
            response = await self._chat_completion(messages, max_tokens=800)
            data = _safe_json_loads(response.choices[0].message.content)
            if isinstance(data, list):
                return data[:count]
        except Exception as e:
            logger.warning(f"[Kimi] suggest_job_titles failed: {e}")

        # Fallback heuristic: extract likely titles from resume lines
        titles = []
        title_patterns = [
            r"(?:Senior|Lead|Principal|Staff|Junior)?\s*(?:Software|Data|Cloud|DevOps|Product|Project|Customer Success|Account)\s+(?:Engineer|Developer|Manager|Architect|Analyst)",
            r"(?:Full Stack|Backend|Frontend)\s+(?:Engineer|Developer)",
            r"Customer Success Manager",
            r"Solutions Architect",
        ]
        for pattern in title_patterns:
            for match in re.findall(pattern, resume_text, flags=re.I):
                title = re.sub(r"\s+", " ", match).strip()
                if title and title not in [t["title"] for t in titles]:
                    titles.append({
                        "title": title,
                        "relevance_score": 80,
                        "reason": "Matched role from resume text",
                        "experience_level": "mid",
                        "keywords": [],
                    })
                if len(titles) >= count:
                    break
            if len(titles) >= count:
                break

        return titles

    async def suggest_job_search_config(self, resume_text: str) -> Dict[str, Any]:
        """Suggest search config including roles, experience, salary, and keywords."""
        titles = await self.suggest_job_titles(resume_text, count=8)
        parsed = await self.parse_resume(resume_text)

        years_experience = _estimate_years_experience(parsed.get("experience", []))
        experience_level = _map_experience_level(years_experience)
        keywords = parsed.get("skills", [])[:20]

        suggested_roles = [t.get("title") for t in titles if t.get("title")]
        best_fit = titles[0] if titles else None

        salary_range = _estimate_salary_range(years_experience)

        return {
            "suggested_roles": suggested_roles,
            "titles_with_scores": titles,
            "experience_level": experience_level,
            "years_experience": years_experience,
            "salary_range": salary_range,
            "keywords": keywords,
            "best_fit": best_fit,
        }


def _estimate_years_experience(experience: List[Dict[str, Any]]) -> int:
    """Estimate years of experience from date ranges."""
    years = []
    for item in experience:
        dates = str(item.get("dates", ""))
        found = re.findall(r"(?:19|20)\d{2}", dates)
        years.extend([int(y) for y in found])
    if len(years) >= 2:
        return max(years) - min(years)
    if len(years) == 1:
        return max(0, (datetime.now().year - years[0]))
    return 0


def _map_experience_level(years: int) -> str:
    if years <= 2:
        return "entry"
    if years <= 5:
        return "mid"
    if years <= 8:
        return "senior"
    return "executive"


def _estimate_salary_range(years: int) -> Dict[str, Any]:
    # Simple heuristic, USD
    base = 50000 + (years * 8000)
    return {
        "min": int(base),
        "max": int(base * 1.3),
        "currency": "USD",
    }


_kimi_service: Optional[KimiResumeOptimizer] = None


def get_kimi_service() -> KimiResumeOptimizer:
    """Get singleton Kimi service."""
    global _kimi_service
    if _kimi_service is None:
        _kimi_service = KimiResumeOptimizer()
    return _kimi_service
