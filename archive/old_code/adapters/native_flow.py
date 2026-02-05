"""
Native Flow Handler

Handles job applications on platforms requiring native search + click flow:
- Indeed (search results → job card → apply)
- LinkedIn (search results → job card → Easy Apply)
- ZipRecruiter

These platforms require starting from search results, not direct URLs.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from .base import JobPosting, ApplicationResult, ApplicationStatus, UserProfile, Resume, SearchConfig

logger = logging.getLogger(__name__)


class NativeFlowHandler:
    """
    Handler for native flow platforms.
    Uses platform-specific adapters with proper search + apply flow.
    """
    
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager
        
    async def search_and_apply(
        self,
        platform: str,
        criteria: SearchConfig,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool = False,
        max_jobs: int = 50
    ) -> List[ApplicationResult]:
        """
        Search for jobs and apply to them.
        
        Args:
            platform: 'indeed' or 'linkedin'
            criteria: Search criteria
            resume: Resume to use
            profile: User profile
            auto_submit: Whether to auto-submit
            max_jobs: Maximum jobs to apply to
            
        Returns:
            List of ApplicationResults
        """
        logger.info(f"🔍 Native flow: Searching {platform} for jobs...")
        
        # Get platform adapter
        adapter = self._get_adapter(platform)
        if not adapter:
            logger.error(f"No adapter for platform: {platform}")
            return []
        
        # Search for jobs
        try:
            jobs = await adapter.search_jobs(criteria)
            logger.info(f"  Found {len(jobs)} jobs")
            
            # Filter to Easy Apply only
            easy_apply_jobs = [j for j in jobs if j.easy_apply]
            logger.info(f"  {len(easy_apply_jobs)} have Easy Apply")
            
            # Limit to max
            jobs_to_apply = easy_apply_jobs[:max_jobs]
            
        except Exception as e:
            logger.error(f"  Search failed: {e}")
            return []
        
        # Apply to each job
        results = []
        for i, job in enumerate(jobs_to_apply, 1):
            logger.info(f"\n  [{i}/{len(jobs_to_apply)}] {job.title} at {job.company}")
            
            try:
                result = await adapter.apply_to_job(
                    job=job,
                    resume=resume,
                    profile=profile,
                    auto_submit=auto_submit
                )
                results.append(result)
                
                if result.status == ApplicationStatus.SUBMITTED:
                    logger.info(f"    ✓ Submitted")
                elif result.status == ApplicationStatus.PENDING_REVIEW:
                    logger.info(f"    ⏸️  Pending review")
                else:
                    logger.info(f"    ✗ {result.message}")
                    
            except Exception as e:
                logger.error(f"    ✗ Error: {e}")
                results.append(ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=str(e)
                ))
            
            # Rate limiting between applications
            if i < len(jobs_to_apply):
                await asyncio.sleep(5)
        
        return results
        
    def _get_adapter(self, platform: str):
        """Get the appropriate adapter for a platform."""
        if platform == 'indeed':
            from .indeed import IndeedAdapter
            return IndeedAdapter(self.browser_manager)
        elif platform == 'linkedin':
            from .linkedin import LinkedInAdapter
            return LinkedInAdapter(self.browser_manager)
        elif platform == 'ziprecruiter':
            from .ziprecruiter import ZipRecruiterAdapter
            return ZipRecruiterAdapter(self.browser_manager)
        return None
        
    async def apply_to_single_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Apply to a single job (requires full navigation).
        
        For native flow platforms, we need to:
        1. Navigate to the job page
        2. Click apply button
        3. Handle the application modal/form
        """
        platform = self._detect_platform(job.url)
        adapter = self._get_adapter(platform)
        
        if not adapter:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"No adapter for {platform}"
            )
        
        return await adapter.apply_to_job(job, resume, profile, auto_submit)
        
    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()
        if 'indeed' in url_lower:
            return 'indeed'
        elif 'linkedin' in url_lower:
            return 'linkedin'
        elif 'ziprecruiter' in url_lower:
            return 'ziprecruiter'
        return 'unknown'


class IndeedNativeAdapter:
    """
    Standalone Indeed adapter for native flow.
    Can be used independently of the main router.
    """
    
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager
        self.base_url = "https://www.indeed.com/jobs"
        
    async def search_jobs(self, query: str, location: str, max_results: int = 50) -> List[JobPosting]:
        """Search Indeed for jobs."""
        from .indeed import IndeedAdapter
        
        adapter = IndeedAdapter(self.browser_manager)
        criteria = SearchConfig(
            roles=[query],
            locations=[location],
            posted_within_days=7
        )
        
        return await adapter.search_jobs(criteria)
        
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """Apply to a single Indeed job."""
        from .indeed import IndeedAdapter
        
        adapter = IndeedAdapter(self.browser_manager)
        return await adapter.apply_to_job(job, resume, profile, auto_submit=auto_submit)


class LinkedInNativeAdapter:
    """
    Standalone LinkedIn adapter for native flow.
    """
    
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager
        
    async def search_jobs(self, query: str, location: str, max_results: int = 50) -> List[JobPosting]:
        """Search LinkedIn for jobs."""
        from .linkedin import LinkedInAdapter
        
        adapter = LinkedInAdapter(self.browser_manager)
        criteria = SearchConfig(
            roles=[query],
            locations=[location],
            posted_within_days=7
        )
        
        return await adapter.search_jobs(criteria)
        
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """Apply to a single LinkedIn job."""
        from .linkedin import LinkedInAdapter
        
        adapter = LinkedInAdapter(self.browser_manager)
        return await adapter.apply_to_job(job, resume, profile, auto_submit=auto_submit)
