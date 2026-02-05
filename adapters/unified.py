#!/usr/bin/env python3
"""
Unified Platform Adapter

A single adapter that uses Stagehand to handle all job platforms.
This replaces multiple platform-specific adapters.

The adapter uses AI to:
1. Detect platform type from URL
2. Navigate and interact with job pages
3. Extract job details
4. Fill and submit application forms
"""

import os
import asyncio
import logging
from typing import List, Optional
from datetime import datetime

from core import (
    JobPlatformAdapter,
    PlatformType,
    JobPosting,
    ApplicationResult,
    ApplicationStatus,
    UserProfile,
    Resume,
    SearchConfig,
    UnifiedBrowserManager,
    UnifiedAIService,
    detect_platform_from_url,
)

# Stagehand agent schemas (optional - for type-safe agent calls)
try:
    from stagehand.schemas import AgentConfig, AgentExecuteOptions, AgentProvider
    STAGEHAND_AGENT_AVAILABLE = True
except ImportError:
    STAGEHAND_AGENT_AVAILABLE = False

logger = logging.getLogger(__name__)


class UnifiedPlatformAdapter(JobPlatformAdapter):
    """
    Universal adapter for all job platforms using Stagehand AI.
    
    This adapter replaces platform-specific adapters by using AI to:
    - Understand page structure
    - Extract job information
    - Navigate application forms
    - Fill and submit applications
    
    Example:
        from adapters.unified import UnifiedPlatformAdapter
        
        adapter = UnifiedPlatformAdapter(user_profile=profile)
        
        # Check if can handle URL
        if await adapter.can_handle(job_url):
            job = await adapter.get_job_details(job_url)
            result = await adapter.apply(job, resume)
    """
    
    platform = PlatformType.EXTERNAL  # Handles any platform
    
    def __init__(
        self,
        user_profile: UserProfile,
        browser_manager: Optional[UnifiedBrowserManager] = None,
        ai_service: Optional[UnifiedAIService] = None
    ):
        super().__init__(user_profile, browser_manager, ai_service)
        self._session = None
        self._page = None
    
    async def can_handle(self, url: str) -> bool:
        """Can handle any job-related URL."""
        job_indicators = [
            "/jobs", "/careers", "/apply", "/job",
            "greenhouse", "lever", "workday", "indeed",
            "linkedin.com/jobs", "dice.com", "ziprecruiter"
        ]
        return any(indicator in url.lower() for indicator in job_indicators)
    
    async def search_jobs(self, config: SearchConfig) -> List[JobPosting]:
        """
        Search for jobs using jobspy or external APIs.
        
        Note: For searching, we use the jobspy library or APIs rather than
        browser automation for efficiency.
        """
        # This would integrate with jobspy or APIs
        # For now, return empty list - search is typically done via APIs
        logger.info("Search not implemented in unified adapter - use jobspy adapter")
        return []
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """
        Extract job details from any job posting URL using Stagehand.
        
        Args:
            job_url: URL of the job posting
            
        Returns:
            JobPosting with extracted details
        """
        await self._ensure_session()
        
        logger.info(f"Extracting job details from: {job_url}")
        
        # Navigate to job page
        await self._page.goto(job_url)
        await asyncio.sleep(2)  # Let page load
        
        # Use Stagehand to extract job details
        extraction = await self._page.extract(
            instruction="""Extract job details including:
            - Job title
            - Company name  
            - Location
            - Job description
            - Salary range if available
            - Requirements/qualifications
            - Remote/hybrid/onsite status
            """,
            schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "description": {"type": "string"},
                    "salary_range": {"type": "string"},
                    "requirements": {"type": "string"},
                    "is_remote": {"type": "boolean"}
                },
                "required": ["title", "company"]
            }
        )
        
        data = extraction if isinstance(extraction, dict) else {}
        
        # Detect platform type
        platform = detect_platform_from_url(job_url)
        
        job = JobPosting(
            id=f"{platform.value}_{hash(job_url) % 10000000}",
            platform=platform,
            title=data.get("title", "Unknown Title"),
            company=data.get("company", "Unknown Company"),
            location=data.get("location", "Unknown Location"),
            url=job_url,
            description=data.get("description"),
            salary_range=data.get("salary_range"),
            remote=data.get("is_remote", False),
            requirements=data.get("requirements"),
        )
        
        self._log(f"Extracted job: {job.title} at {job.company}")
        return job
    
    async def apply(self, job: JobPosting, resume: Resume) -> ApplicationResult:
        """
        Apply to a job using Stagehand AI agent.

        Uses Stagehand's agent API (act/observe/extract) to navigate forms,
        fill fields, and submit the application autonomously.

        Args:
            job: Job posting to apply to
            resume: Resume to use

        Returns:
            ApplicationResult with status
        """
        await self._ensure_session()

        logger.info(f"Applying to: {job.title} at {job.company}")

        try:
            # Navigate to job
            await self._page.goto(job.url)
            await asyncio.sleep(2)

            # Look for apply button
            observe_result = await self._page.observe(
                instruction="Find the apply button or link to start the application"
            )

            if observe_result and len(observe_result) > 0:
                await self._page.act(observe_result[0])
                await asyncio.sleep(3)  # Wait for form to load
            else:
                await self._page.act("click the apply button")

            # Build applicant context for the agent
            applicant_info = f"""Applicant Information:
- Name: {self.profile.full_name}
- Email: {self.profile.email}
- Phone: {self.profile.phone}
- Location: {self.profile.location}
- LinkedIn: {getattr(self.profile, 'linkedin_url', 'N/A') or 'N/A'}

Resume path: {resume.file_path}

Instructions:
1. Fill all required fields with the applicant info above
2. Upload the resume if a file upload field is present
3. Answer any screening questions truthfully based on the profile
4. Submit the application when all required fields are complete"""

            # Use Stagehand agent API if available, otherwise fall back to act() calls
            if STAGEHAND_AGENT_AVAILABLE and self._session and self._session.stagehand:
                stagehand = self._session.stagehand
                agent = stagehand.agent(
                    provider="openai",
                    model=os.getenv("STAGEHAND_MODEL_NAME", "gpt-4o"),
                    instructions=applicant_info,
                )
                result = await agent.execute(
                    instruction="Complete and submit this job application form",
                    max_steps=int(os.getenv("MAX_APPLICATION_STEPS", "25")),
                )
            else:
                # Fallback: use page.act() with detailed instructions
                await self._page.act(
                    f"Fill out this job application form. {applicant_info}"
                )
                await asyncio.sleep(2)
                await self._page.act("Submit the application form")

            # Check for confirmation
            content = await self._page.content()
            success_indicators = [
                "thank you", "application submitted", "successfully submitted",
                "we have received", "confirmation", "your application"
            ]

            success = any(ind in content.lower() for ind in success_indicators)

            # Try to extract confirmation number
            import re
            conf_match = re.search(r'confirmation[\s#:]+([A-Z0-9\-]+)', content, re.I)
            confirmation_id = conf_match.group(1) if conf_match else None

            if success:
                self._log(f"Application submitted! Confirmation: {confirmation_id}")
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message="Application submitted successfully",
                    confirmation_id=confirmation_id,
                    submitted_at=datetime.now()
                )
            else:
                self._log("Could not verify successful submission")
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message="Application may have been submitted - verification inconclusive",
                    submitted_at=datetime.now()
                )

        except Exception as e:
            logger.error(f"Application failed: {e}")
            return ApplicationResult(
                status=ApplicationStatus.FAILED,
                message=f"Application failed: {e}",
                error=str(e)
            )
    
    async def _ensure_session(self):
        """Ensure browser session exists."""
        if not self._session:
            if not self.browser:
                self.browser = UnifiedBrowserManager()
                await self.browser.init()
            
            self._session = await self.browser.create_session()
            self._page = self._session.page
    
    async def close(self):
        """Close the adapter and cleanup."""
        if self._session:
            if self.browser:
                await self.browser.close_session(self._session.session_id)
            self._session = None
            self._page = None


# Factory function
def create_adapter(
    platform: Optional[PlatformType] = None,
    user_profile: Optional[UserProfile] = None
) -> JobPlatformAdapter:
    """
    Factory function to create appropriate adapter.
    
    Args:
        platform: Optional platform type hint
        user_profile: User profile for applications
        
    Returns:
        JobPlatformAdapter instance
    """
    profile = user_profile or UserProfile(
        first_name="",
        last_name="",
        email="",
        phone=""
    )
    
    # For now, always return the unified adapter
    # Platform-specific adapters can be added back if needed
    return UnifiedPlatformAdapter(user_profile=profile)
