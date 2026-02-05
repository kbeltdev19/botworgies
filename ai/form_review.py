"""
AI-Powered Form Review System

Analyzes complex application forms and provides intelligent feedback,
suggestions for completion, and risk assessment before submission.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from adapters.base import JobPosting, UserProfile, Resume

logger = logging.getLogger(__name__)


@dataclass
class FormField:
    """Represents a detected form field."""
    name: str
    label: str
    type: str
    required: bool = False
    options: List[str] = field(default_factory=list)
    selector: str = ""
    value: str = ""
    confidence: float = 0.0


@dataclass
class FormReviewResult:
    """Result of AI form review."""
    can_auto_fill: bool
    missing_required_fields: List[str]
    custom_questions: List[Dict[str, Any]]
    risk_score: float  # 0-1, higher = more risky
    suggestions: List[str]
    recommended_action: str  # 'auto_submit', 'review', 'skip'
    filled_fields: List[FormField]
    screenshots: List[str]


class AIFormReviewer:
    """
    AI-powered form review system.
    
    Analyzes forms and decides whether to auto-submit or require human review.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.model = "moonshot-v1-8k"
    
    async def review_form(
        self,
        page_html: str,
        page_url: str,
        job: JobPosting,
        profile: UserProfile,
        filled_data: Dict[str, str]
    ) -> FormReviewResult:
        """
        Review a form and provide recommendations.
        
        Args:
            page_html: Current page HTML
            page_url: Page URL
            job: Job posting
            profile: User profile
            filled_data: Fields already filled
            
        Returns:
            FormReviewResult with recommendations
        """
        # Detect form fields
        fields = await self._detect_fields(page_html)
        
        # Check for custom questions
        custom_questions = self._extract_custom_questions(page_html)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(fields, custom_questions, filled_data)
        
        # Generate recommendations
        if risk_score < 0.3 and not custom_questions:
            action = "auto_submit"
        elif risk_score < 0.7:
            action = "review"
        else:
            action = "skip"
        
        # Generate suggestions
        suggestions = await self._generate_suggestions(
            fields, custom_questions, job, profile
        )
        
        return FormReviewResult(
            can_auto_fill=risk_score < 0.3 and not custom_questions,
            missing_required_fields=[f.name for f in fields if f.required and not f.value],
            custom_questions=custom_questions,
            risk_score=risk_score,
            suggestions=suggestions,
            recommended_action=action,
            filled_fields=[f for f in fields if f.value],
            screenshots=[]
        )
    
    async def _detect_fields(self, html: str) -> List[FormField]:
        """Detect all form fields in HTML."""
        # Use AI to detect fields
        prompt = f"""Analyze this HTML and extract all form fields.

HTML (truncated):
{html[:30000]}

For each field, extract:
- Field name/label
- Input type (text, email, file, select, etc.)
- Whether it's required
- Available options (for selects/radios)
- CSS selector

Respond in JSON:
{{
    "fields": [
        {{
            "name": "first_name",
            "label": "First Name",
            "type": "text",
            "required": true,
            "options": [],
            "selector": "input[name='firstName']"
        }},
        ...
    ]
}}
"""
        
        try:
            result = await self._call_ai(prompt)
            fields = []
            for f in result.get("fields", []):
                fields.append(FormField(
                    name=f.get("name", ""),
                    label=f.get("label", ""),
                    type=f.get("type", "text"),
                    required=f.get("required", False),
                    options=f.get("options", []),
                    selector=f.get("selector", ""),
                    confidence=f.get("confidence", 0.5)
                ))
            return fields
        except Exception as e:
            logger.error(f"Field detection failed: {e}")
            return []
    
    def _extract_custom_questions(self, html: str) -> List[Dict[str, Any]]:
        """Extract custom application questions."""
        import re
        
        questions = []
        
        # Look for question patterns
        patterns = [
            r'<label[^>]*>([^<]+(?:question|describe|explain|why|how)[^<]*)</label>',
            r'<div[^>]*class="[^"]*question[^"]*"[^>]*>([^<]+)</div>',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                questions.append({
                    "text": match.strip(),
                    "type": "text",
                    "requires_answer": True
                })
        
        return questions
    
    def _calculate_risk_score(
        self,
        fields: List[FormField],
        custom_questions: List[Dict],
        filled_data: Dict[str, str]
    ) -> float:
        """Calculate risk score for auto-submission."""
        score = 0.0
        
        # More fields = higher complexity = higher risk
        score += min(len(fields) * 0.02, 0.3)
        
        # Custom questions = high risk
        score += len(custom_questions) * 0.2
        
        # Missing required fields = high risk
        missing_required = sum(1 for f in fields if f.required and not filled_data.get(f.name))
        score += missing_required * 0.15
        
        # File uploads = medium risk
        file_fields = sum(1 for f in fields if f.type == "file")
        score += file_fields * 0.05
        
        return min(score, 1.0)
    
    async def _generate_suggestions(
        self,
        fields: List[FormField],
        custom_questions: List[Dict],
        job: JobPosting,
        profile: UserProfile
    ) -> List[str]:
        """Generate completion suggestions."""
        suggestions = []
        
        # Check for common missing fields
        important_fields = ["first_name", "last_name", "email", "phone", "resume"]
        for field_name in important_fields:
            if not any(f.name == field_name and f.value for f in fields):
                suggestions.append(f"Missing {field_name} - ensure this is filled")
        
        # Custom question suggestions
        if custom_questions:
            suggestions.append(f"Found {len(custom_questions)} custom questions requiring answers")
            
            # Use AI to suggest answers
            for q in custom_questions[:3]:  # Limit to first 3
                answer = await self._suggest_answer(q["text"], job, profile)
                suggestions.append(f"Q: {q['text'][:50]}...\n   Suggested: {answer[:100]}...")
        
        # Role-specific suggestions
        if "senior" in job.title.lower() and profile.years_experience < 5:
            suggestions.append("Warning: Job requires senior-level but profile shows < 5 years experience")
        
        return suggestions
    
    async def _suggest_answer(self, question: str, job: JobPosting, profile: UserProfile) -> str:
        """Use AI to suggest an answer to a custom question."""
        prompt = f"""Answer this job application question based on the candidate's profile.

Question: {question}

Job: {job.title} at {job.company}
Candidate Profile:
- Name: {profile.first_name} {profile.last_name}
- Experience: {profile.years_experience} years
- Custom Answers: {profile.custom_answers}

Provide a concise, professional answer (2-3 sentences max).
"""
        
        try:
            result = await self._call_ai(prompt)
            return result.get("answer", "")
        except:
            return "[Unable to generate suggestion]"
    
    async def _call_ai(self, prompt: str) -> dict:
        """Call AI API."""
        import aiohttp
        import os
        
        api_key = self.api_key or os.getenv("MOONSHOT_API_KEY")
        if not api_key:
            raise ValueError("No API key available")
        
        url = "https://api.moonshot.cn/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an expert job application assistant. Provide helpful, accurate responses."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                
                # Try to parse as JSON
                try:
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    return json.loads(content.strip())
                except:
                    return {"answer": content.strip()}


class ReviewModeManager:
    """
    Manages AI review mode for campaigns.
    
    Instead of auto-submitting, this pauses and asks for human review
    when risk score is high.
    """
    
    def __init__(self, output_dir: str = "campaign_output/reviews"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reviewer = AIFormReviewer()
    
    async def review_and_decide(
        self,
        page_html: str,
        page_url: str,
        job: JobPosting,
        profile: UserProfile,
        filled_data: Dict[str, str],
        screenshot_path: str
    ) -> Dict[str, Any]:
        """
        Review form and decide whether to proceed.
        
        Returns:
            Dict with 'action' ('submit', 'skip', 'pause') and 'reason'
        """
        # Get AI review
        review = await self.reviewer.review_form(
            page_html, page_url, job, profile, filled_data
        )
        
        # Save review report
        report_path = self._save_review_report(job, review, screenshot_path)
        
        # Decide action
        if review.recommended_action == "auto_submit":
            return {
                "action": "submit",
                "reason": "Low risk, no custom questions",
                "review": review,
                "report_path": report_path
            }
        elif review.recommended_action == "skip":
            return {
                "action": "skip",
                "reason": f"High risk score: {review.risk_score:.2f}",
                "review": review,
                "report_path": report_path
            }
        else:
            # Pause for human review
            return {
                "action": "pause",
                "reason": "Requires human review",
                "review": review,
                "report_path": report_path,
                "instructions": self._generate_instructions(review)
            }
    
    def _save_review_report(
        self,
        job: JobPosting,
        review: FormReviewResult,
        screenshot_path: str
    ) -> str:
        """Save review report to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{job.company.replace(' ', '_')}_{job.id}_{timestamp}.json"
        path = self.output_dir / filename
        
        report = {
            "job": {
                "title": job.title,
                "company": job.company,
                "url": job.url
            },
            "review": {
                "can_auto_fill": review.can_auto_fill,
                "risk_score": review.risk_score,
                "missing_fields": review.missing_required_fields,
                "custom_questions": review.custom_questions,
                "suggestions": review.suggestions,
                "recommended_action": review.recommended_action
            },
            "screenshot": screenshot_path,
            "timestamp": timestamp
        }
        
        path.write_text(json.dumps(report, indent=2))
        return str(path)
    
    def _generate_instructions(self, review: FormReviewResult) -> str:
        """Generate human-readable instructions."""
        instructions = []
        
        instructions.append("=" * 60)
        instructions.append("FORM REQUIRES MANUAL REVIEW")
        instructions.append("=" * 60)
        instructions.append("")
        
        if review.missing_required_fields:
            instructions.append("Missing Required Fields:")
            for field in review.missing_required_fields:
                instructions.append(f"  - {field}")
            instructions.append("")
        
        if review.custom_questions:
            instructions.append(f"Custom Questions ({len(review.custom_questions)} found):")
            for i, q in enumerate(review.custom_questions[:5], 1):
                instructions.append(f"  {i}. {q['text'][:80]}...")
            instructions.append("")
        
        if review.suggestions:
            instructions.append("AI Suggestions:")
            for suggestion in review.suggestions:
                instructions.append(f"  • {suggestion}")
            instructions.append("")
        
        instructions.append("Options:")
        instructions.append("  1. Type 'SUBMIT' to approve and submit")
        instructions.append("  2. Type 'SKIP' to skip this application")
        instructions.append("  3. Type 'EDIT' to pause and manually edit")
        instructions.append("")
        
        return "\n".join(instructions)


# Usage example
async def test_review_mode():
    """Test the review mode."""
    from adapters.base import JobPosting, UserProfile, PlatformType
    
    manager = ReviewModeManager()
    
    job = JobPosting(
        id="test123",
        platform=PlatformType.WORKDAY,
        title="Software Engineer",
        company="TestCorp",
        location="Remote",
        url="https://testcorp.com/jobs/123"
    )
    
    profile = UserProfile(
        first_name="Test",
        last_name="User",
        email="test@example.com",
        phone="555-1234",
        years_experience=5
    )
    
    html = """
    <form>
        <input name="firstName" required />
        <input name="lastName" required />
        <input type="email" name="email" required />
        <textarea name="coverLetter" placeholder="Why do you want to work here?"></textarea>
        <label>Describe a challenging project you worked on</label>
        <textarea name="projectExperience"></textarea>
    </form>
    """
    
    result = await manager.review_and_decide(
        html, job.url, job, profile, {}, "/tmp/screenshot.png"
    )
    
    print(f"Action: {result['action']}")
    print(f"Reason: {result['reason']}")
    if 'instructions' in result:
        print(f"\n{result['instructions']}")


if __name__ == "__main__":
    import asyncio
    # asyncio.run(test_review_mode())
    print("AI Form Review module ready")
