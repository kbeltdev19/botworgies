"""
JobSpy Adapter - Multi-platform scraper integration
Wraps JobSpy to provide a unified interface compatible with other adapters.

Supports:
- LinkedIn
- Indeed
- ZipRecruiter
- Glassdoor
- Google Jobs

Requires Python 3.10+
"""

import asyncio
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)

# Import JobSpy components
try:
    from .jobspy_scraper import JobSpyScraper, JobSpyConfig
    JOBSY_AVAILABLE = True
except ImportError:
    JOBSY_AVAILABLE = False
    JobSpyScraper = None
    JobSpyConfig = None


class JobSpyAdapter(JobPlatformAdapter):
    """
    JobSpy multi-platform adapter.
    Scrapes jobs from LinkedIn, Indeed, ZipRecruiter, Glassdoor, and Google Jobs.
    
    Requires Python 3.10+ due to JobSpy dependencies.
    
    Usage:
        adapter = JobSpyAdapter()
        jobs = await adapter.search_jobs(criteria)
    """
    
    platform = PlatformType.EXTERNAL
    tier = "api"  # Uses APIs/scraping
    
    # Map our PlatformType to JobSpy site names
    SITE_MAPPING = {
        "linkedin": "linkedin",
        "indeed": "indeed",
        "ziprecruiter": "zip_recruiter",
        "glassdoor": "glassdoor",
        "google": "google",
    }
    
    def __init__(self, browser_manager=None, sites: List[str] = None):
        """
        Initialize JobSpy adapter.
        
        Args:
            browser_manager: Not used for JobSpy (API-based)
            sites: List of sites to search ["linkedin", "indeed", "zip_recruiter", "glassdoor", "google"]
        """
        super().__init__(browser_manager)
        
        if not JOBSY_AVAILABLE:
            raise ImportError(
                "JobSpy not available. Install Python 3.10+ and run: pip install python-jobspy\n"
                "See JOBSPY_SETUP.md for detailed instructions."
            )
        
        self.sites = sites or ["indeed", "linkedin"]
        self.scraper = JobSpyScraper()
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """
        Search for jobs using JobSpy across multiple platforms.
        
        Args:
            criteria: Search configuration
            
        Returns:
            List of JobPosting objects
        """
        # Map sites to JobSpy format
        site_names = []
        for site in self.sites:
            mapped = self.SITE_MAPPING.get(site.lower(), site.lower())
            site_names.append(mapped)
        
        # Build search term from roles
        search_term = " OR ".join(criteria.roles) if criteria.roles else "software engineer"
        
        # Determine location
        location = ""
        is_remote = False
        if criteria.locations:
            location = criteria.locations[0]
            if location.lower() == "remote":
                is_remote = True
                location = ""
        
        # Determine hours old from posted_within_days
        hours_old = criteria.posted_within_days * 24 if criteria.posted_within_days else 168
        
        # Create JobSpy config
        config = JobSpyConfig(
            site_name=site_names,
            search_term=search_term,
            location=location,
            is_remote=is_remote,
            results_wanted=100,
            hours_old=hours_old,
            easy_apply=criteria.easy_apply_only,
            description_format="markdown",
            linkedin_fetch_description=True,
            verbose=0
        )
        
        # Run scrape
        scraped_jobs = await self.scraper.scrape_jobs(config)
        
        # Convert to JobPosting format
        jobs = []
        for sj in scraped_jobs:
            # Determine platform from site
            platform_map = {
                "linkedin": PlatformType.LINKEDIN,
                "indeed": PlatformType.INDEED,
                "zip_recruiter": PlatformType.EXTERNAL,
                "glassdoor": PlatformType.EXTERNAL,
                "google": PlatformType.EXTERNAL,
            }
            platform = platform_map.get(sj.site, PlatformType.EXTERNAL)
            
            jobs.append(JobPosting(
                id=sj.id,
                platform=platform,
                title=sj.title,
                company=sj.company,
                location=sj.location,
                url=sj.url,
                description=sj.description,
                salary_range=f"${sj.min_amount} - ${sj.max_amount} {sj.currency}" if sj.min_amount and sj.max_amount else "",
                posted_date=sj.date_posted,
                easy_apply=sj.easy_apply,
                remote=sj.is_remote,
                job_type=sj.job_type or "full-time",
                source_platform=sj.site
            ))
        
        print(f"[JobSpy] Found {len(jobs)} jobs from {len(site_names)} sites")
        return jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """
        JobSpy returns full details in search, so this just returns a basic structure.
        For actual job details, you'd need to visit the URL.
        """
        return JobPosting(
            id=f"jobspy_{hash(job_url)}",
            platform=self.platform,
            title="See job posting",
            company="",
            location="",
            url=job_url,
            easy_apply=False
        )
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        JobSpy jobs require visiting the original site to apply.
        Returns external application link.
        """
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message=f"Apply at: {job.url}",
            external_url=job.url
        )
    
    def get_stats(self) -> dict:
        """Get scraping statistics from last search."""
        return self.scraper.get_stats()
    
    def export_results(self, filepath: str):
        """Export last search results to CSV."""
        self.scraper.export_to_csv(filepath)


async def test_jobspy_adapter():
    """Test JobSpy adapter."""
    from .base import SearchConfig
    
    if not JOBSY_AVAILABLE:
        print("JobSpy not available. Skipping test.")
        return
    
    adapter = JobSpyAdapter(sites=["indeed"])
    
    criteria = SearchConfig(
        roles=["software engineer"],
        locations=["Remote"],
        posted_within_days=7,
        easy_apply_only=False
    )
    
    try:
        jobs = await adapter.search_jobs(criteria)
        print(f"\nFound {len(jobs)} jobs:")
        for job in jobs[:5]:
            print(f"  - {job.title} @ {job.company}")
            print(f"    Location: {job.location} | Remote: {job.remote}")
            if job.salary_range:
                print(f"    Salary: {job.salary_range}")
        
        print(f"\nStats: {adapter.get_stats()}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_jobspy_adapter())
