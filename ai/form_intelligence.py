#!/usr/bin/env python3
"""
AI Form Intelligence - Smart answers for dynamic application questions.

Uses Kimi AI to:
1. Analyze form questions
2. Generate contextual answers based on profile + job description
3. Handle different question types intelligently
"""

import asyncio
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class FormIntelligence:
    """AI-powered form filling intelligence."""
    
    def __init__(self):
        self.kimi_service = None
        self.cache = {}  # Simple cache for repeated questions
    
    def _get_kimi(self):
        """Lazy load Kimi service."""
        if self.kimi_service is None:
            try:
                from .kimi_service import get_kimi_service
                self.kimi_service = get_kimi_service()
            except Exception as e:
                logger.warning(f"[FormIntelligence] Could not load Kimi: {e}")
        return self.kimi_service
    
    async def answer_question(
        self,
        question: str,
        question_type: str,  # 'text', 'select', 'radio', 'checkbox'
        options: List[str] = None,
        profile: Dict = None,
        job_description: str = None,
        context: Dict = None
    ) -> str:
        """
        Generate intelligent answer for an application question.
        
        Args:
            question: The question text
            question_type: Type of input expected
            options: Available options (for select/radio)
            profile: User profile information
            job_description: Job description for context
            context: Additional context (company, role, etc.)
            
        Returns:
            Generated answer
        """
        # Check cache
        cache_key = f"{question}_{hash(str(options))}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        kimi = self._get_kimi()
        if not kimi:
            return self._fallback_answer(question, question_type, options)
        
        try:
            # Build prompt
            prompt = self._build_prompt(
                question, question_type, options,
                profile, job_description, context
            )
            
            # Get AI response
            response = await kimi.generate_text(prompt, max_tokens=200)
            answer = response.strip()
            
            # Validate and clean answer
            answer = self._validate_answer(answer, question_type, options)
            
            # Cache result
            self.cache[cache_key] = answer
            
            return answer
            
        except Exception as e:
            logger.warning(f"[FormIntelligence] AI answer failed: {e}")
            return self._fallback_answer(question, question_type, options)
    
    def _build_prompt(
        self,
        question: str,
        question_type: str,
        options: List[str],
        profile: Dict,
        job_description: str,
        context: Dict
    ) -> str:
        """Build AI prompt for question answering."""
        
        prompt_parts = [
            "You are helping someone fill out a job application. Answer the question professionally and concisely.",
            "",
            f"Question: {question}",
            f"Question Type: {question_type}",
        ]
        
        if options:
            prompt_parts.append(f"Available Options: {', '.join(options)}")
        
        if profile:
            prompt_parts.append("")
            prompt_parts.append("Applicant Profile:")
            prompt_parts.append(f"- Name: {profile.get('first_name', '')} {profile.get('last_name', '')}")
            prompt_parts.append(f"- Experience: {profile.get('years_experience', '5+')} years")
            prompt_parts.append(f"- Skills: {profile.get('skills', 'relevant technical skills')}")
        
        if job_description:
            prompt_parts.append(f"")
            prompt_parts.append(f"Job Context: {job_description[:300]}...")
        
        if context:
            prompt_parts.append(f"")
            prompt_parts.append(f"Additional Context: {context}")
        
        prompt_parts.append(f"")
        prompt_parts.append(f"Instructions:")
        prompt_parts.append(f"1. Answer truthfully based on the profile")
        prompt_parts.append(f"2. Keep answers concise (1-2 sentences for text, exact option for select)")
        prompt_parts.append(f"3. For yes/no questions about eligibility: answer 'Yes' if qualified")
        prompt_parts.append(f"4. For salary questions: be reasonable and negotiable")
        prompt_parts.append(f"5. Match the tone of the job description")
        prompt_parts.append(f"")
        prompt_parts.append(f"Answer:")
        
        return "\n".join(prompt_parts)
    
    def _validate_answer(
        self,
        answer: str,
        question_type: str,
        options: List[str]
    ) -> str:
        """Validate and clean AI-generated answer."""
        
        answer = answer.strip()
        
        if question_type in ['select', 'radio'] and options:
            # Find closest matching option
            answer_lower = answer.lower()
            for option in options:
                if option.lower() in answer_lower or answer_lower in option.lower():
                    return option
            # Default to first non-empty option
            return options[0] if options else answer
        
        if question_type == 'checkbox':
            # Normalize yes/no for checkboxes
            if answer.lower() in ['yes', 'true', 'agree', 'confirm']:
                return 'yes'
            return 'no'
        
        # Text answers - limit length
        if len(answer) > 500:
            answer = answer[:497] + "..."
        
        return answer
    
    def _fallback_answer(
        self,
        question: str,
        question_type: str,
        options: List[str]
    ) -> str:
        """Generate fallback answer when AI is unavailable."""
        
        question_lower = question.lower()
        
        # Common question patterns
        if any(word in question_lower for word in ['authorized', 'legally', 'eligible', 'work in']):
            return 'Yes' if question_type in ['select', 'radio'] else 'I am legally authorized to work in the United States.'
        
        if any(word in question_lower for word in ['sponsor', 'sponsorship', 'visa']):
            if options:
                for opt in options:
                    if 'no' in opt.lower():
                        return opt
            return 'No'
        
        if any(word in question_lower for word in ['relocate', 'relocation']):
            return 'Open to discussion' if options else 'Willing to consider relocation for the right opportunity.'
        
        if any(word in question_lower for word in ['salary', 'compensation', 'pay']):
            return 'Negotiable' if options else 'Negotiable based on the total compensation package.'
        
        if any(word in question_lower for word in ['remote', 'hybrid', 'onsite']):
            return 'Flexible' if options else 'Flexible - open to remote, hybrid, or onsite depending on the role.'
        
        if any(word in question_lower for word in ['notice', 'start']):
            return '2 weeks' if options else 'Can start with 2 weeks notice.'
        
        if any(word in question_lower for word in ['veteran', 'disability', 'gender', 'race']):
            # Prefer not to answer for EEO questions
            if options:
                for opt in options:
                    if 'prefer' in opt.lower() or 'decline' in opt.lower() or 'not' in opt.lower():
                        return opt
            return 'Prefer not to answer'
        
        # Default answers
        if question_type == 'text':
            return 'See resume for details'
        
        if options:
            return options[0]
        
        return 'N/A'
    
    async def analyze_form_structure(
        self,
        html_content: str,
        url: str
    ) -> Dict[str, Any]:
        """
        Analyze form structure to identify fields and their purposes.
        
        Returns:
            Dictionary of field_id -> field_info
        """
        # This would use AI to analyze form HTML
        # For now, return empty - can be enhanced later
        return {}


# Pre-built answer templates for common questions
COMMON_ANSWERS = {
    'authorization': 'I am legally authorized to work in the United States.',
    'sponsorship': 'No',
    'relocate': 'Open to relocation for the right opportunity.',
    'remote': 'Flexible with remote, hybrid, or onsite arrangements.',
    'salary': 'Negotiable based on total compensation package.',
    'notice': '2 weeks',
    'experience_summary': lambda years: f"{years}+ years of relevant experience.",
}


# Singleton
_form_intelligence = None


def get_form_intelligence() -> FormIntelligence:
    """Get singleton FormIntelligence instance."""
    global _form_intelligence
    if _form_intelligence is None:
        _form_intelligence = FormIntelligence()
    return _form_intelligence
