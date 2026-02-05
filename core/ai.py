#!/usr/bin/env python3
"""
Unified AI Service Module

Provides a single interface for AI operations using Moonshot (Kimi) API.
Replaces ai/kimi_service.py and other scattered AI implementations.
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    """Response from AI service."""
    success: bool
    content: str
    parsed_data: Optional[Dict] = None
    error: Optional[str] = None
    tokens_used: Optional[int] = None
    duration_ms: float = 0.0


class UnifiedAIService:
    """
    Unified AI service using Moonshot API.
    
    This is the single entry point for all AI operations in the application.
    
    Example:
        from core.ai import UnifiedAIService
        
        ai = UnifiedAIService()
        
        # Simple completion
        response = await ai.complete("Summarize this job description: ...")
        
        # JSON extraction
        data = await ai.extract_json(
            text=job_description,
            schema={"skills": ["string"], "experience": "string"}
        )
        
        # Resume tailoring
        tailored = await ai.tailor_resume(resume_text, job_description)
    """
    
    DEFAULT_MODEL = "moonshot-v1-8k-vision-preview"
    DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """
        Initialize AI service.
        
        Args:
            api_key: Moonshot API key (or from MOONSHOT_API_KEY env)
            model: Model name to use
            base_url: API base URL
            max_retries: Max retries for failed requests
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        self.model = model
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout
        
        if not self.api_key:
            logger.warning("MOONSHOT_API_KEY not set")
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> AIResponse:
        """
        Get completion from AI.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            AIResponse with completion text
        """
        start_time = asyncio.get_event_loop().time()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens
                        },
                        timeout=self.timeout
                    ) as response:
                        data = await response.json()
                        
                        if "choices" in data:
                            content = data["choices"][0]["message"]["content"]
                            duration = (asyncio.get_event_loop().time() - start_time) * 1000
                            
                            return AIResponse(
                                success=True,
                                content=content,
                                tokens_used=data.get("usage", {}).get("total_tokens"),
                                duration_ms=duration
                            )
                        else:
                            error = data.get("error", {}).get("message", "Unknown error")
                            raise Exception(error)
                            
            except Exception as e:
                logger.warning(f"AI request failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                else:
                    return AIResponse(
                        success=False,
                        content="",
                        error=str(e),
                        duration_ms=(asyncio.get_event_loop().time() - start_time) * 1000
                    )
        
        return AIResponse(success=False, content="", error="Max retries exceeded")
    
    async def extract_json(
        self,
        text: str,
        schema: Dict[str, Any],
        instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract structured JSON data from text.
        
        Args:
            text: Text to extract from
            schema: JSON schema defining expected output
            instructions: Additional extraction instructions
            
        Returns:
            Extracted data as dictionary
        """
        schema_str = json.dumps(schema, indent=2)
        
        prompt = f"""Extract structured data from the following text according to this schema:

SCHEMA:
{schema_str}

TEXT:
{text}

{instructions or ''}

Respond with ONLY valid JSON matching the schema. No markdown, no explanation."""

        response = await self.complete(prompt, max_tokens=2000)
        
        if not response.success:
            logger.error(f"JSON extraction failed: {response.error}")
            return {}
        
        try:
            # Try direct parsing
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown
            content = response.content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                # Find JSON object
                start = content.find("{")
                end = content.rfind("}") + 1
                json_str = content[start:end] if start >= 0 and end > start else "{}"
            
            return json.loads(json_str)
    
    async def tailor_resume(
        self,
        resume_text: str,
        job_description: str,
        style: str = "professional"
    ) -> Dict[str, Any]:
        """
        Tailor resume for a specific job.
        
        Args:
            resume_text: Original resume text
            job_description: Job description to tailor for
            style: Writing style (professional, technical, creative)
            
        Returns:
            Tailored resume data
        """
        prompt = f"""Tailor this resume for the job description. 

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

STYLE: {style}

Instructions:
1. Identify key skills and experiences from the resume that match the job
2. Rephrase bullets to emphasize relevant achievements
3. DO NOT invent new experience - only rephrase existing content
4. Suggest a tailored summary statement

Respond with JSON:
{{
    "summary": "tailored professional summary",
    "highlighted_skills": ["skill1", "skill2"],
    "tailored_bullets": ["bullet1", "bullet2"],
    "keywords_to_add": ["keyword1", "keyword2"]
}}"""

        return await self.extract_json(
            text="",  # Not used, prompt contains everything
            schema={
                "summary": "string",
                "highlighted_skills": ["string"],
                "tailored_bullets": ["string"],
                "keywords_to_add": ["string"]
            },
            instructions=prompt
        )
    
    async def generate_cover_letter(
        self,
        resume_summary: str,
        job_title: str,
        company: str,
        job_description: str,
        tone: str = "professional"
    ) -> str:
        """Generate a cover letter."""
        prompt = f"""Write a cover letter for this job.

JOB: {job_title} at {company}
JOB DESCRIPTION:
{job_description}

CANDIDATE BACKGROUND:
{resume_summary}

TONE: {tone}

Instructions:
1. Keep it concise (250-400 words)
2. Highlight 2-3 most relevant achievements
3. Show enthusiasm for the specific role
4. DO NOT invent experience not in the background

Write only the cover letter text:"""

        response = await self.complete(prompt, max_tokens=1500)
        return response.content if response.success else ""
    
    async def parse_resume(self, resume_text: str) -> Dict[str, Any]:
        """Parse resume text into structured data."""
        schema = {
            "name": "string",
            "email": "string",
            "phone": "string",
            "location": "string",
            "summary": "string",
            "skills": ["string"],
            "experience": [
                {
                    "company": "string",
                    "title": "string",
                    "dates": "string",
                    "description": "string"
                }
            ],
            "education": [
                {
                    "school": "string",
                    "degree": "string",
                    "dates": "string"
                }
            ]
        }
        
        prompt = f"""Parse this resume into structured data:

RESUME:
{resume_text[:5000]}

Extract all relevant information."""

        return await self.extract_json(
            text=prompt,
            schema=schema
        )
    
    async def answer_question(
        self,
        question: str,
        context: str,
        profile: Dict[str, Any]
    ) -> str:
        """Answer an application question based on profile."""
        prompt = f"""Answer this job application question based on the candidate profile.

QUESTION: {question}

CONTEXT: {context}

CANDIDATE PROFILE:
{json.dumps(profile, indent=2)}

Instructions:
1. Answer truthfully based only on the profile
2. Be concise but complete
3. If the question asks about something not in the profile, answer based on general professional standards"""

        response = await self.complete(prompt, max_tokens=500)
        return response.content.strip() if response.success else ""


# Singleton instance
_ai_service: Optional[UnifiedAIService] = None


def get_ai_service() -> UnifiedAIService:
    """Get or create singleton AI service instance."""
    global _ai_service
    if _ai_service is None:
        _ai_service = UnifiedAIService()
    return _ai_service


def reset_ai_service():
    """Reset the singleton instance (for testing)."""
    global _ai_service
    _ai_service = None
