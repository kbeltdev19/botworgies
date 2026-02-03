"""
JobSpy integration for multi-platform job scraping.
Uses JobSpy library to scrape jobs from LinkedIn, Indeed, ZipRecruiter, Glassdoor, etc.

Documentation: https://github.com/speedyapply/JobSpy
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Try to import jobspy, provide helpful error if not installed
try:
    from jobspy import scrape_jobs
    JOBSY_AVAILABLE = True
except ImportError:
    JOBSY_AVAILABLE = False
    logger.warning("JobSpy not installed. Run: pip install python-jobspy")


@dataclass
class JobSpyConfig:
    """Configuration for JobSpy scraping."""
    site_name: List[str]  # linkedin, indeed, zip_recruiter, glassdoor, google
    search_term: str
    location: str = ""
    distance: int = 50  # miles
    job_type: str = ""  # fulltime, parttime, internship, contract
    proxies: List[str] = None
    ca_cert: str = None  # For proxy SSL
    is_remote: bool = False
    results_wanted: int = 100  # Jobs per site
    easy_apply: bool = False  # LinkedIn only
    description_format: str = "markdown"  # markdown, html
    offset: int = 0  # Pagination
    hours_old: int = 72  # Jobs posted within last X hours
    country_indeed: str = "usa"  # usa, uk, canada, etc.
    verbose: int = 0  # 0=none, 1=some, 2=all
    linkedin_fetch_description: bool = True
    linkedin_company_ids: List[int] = None


@dataclass
class ScrapedJob:
    """Standardized job format from JobSpy."""
    id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    date_posted: Optional[datetime]
    job_type: Optional[str]
    salary_source: Optional[str]
    interval: Optional[str]
    min_amount: Optional[float]
    max_amount: Optional[float]
    currency: Optional[str]
    is_remote: bool
    job_level: Optional[str]
    company_industry: Optional[str]
    company_url: Optional[str]
    company_logo: Optional[str]
    site: str  # Which site it came from
    emails: Optional[List[str]]
    
    # For our application tracking
    easy_apply: bool = False
    application_url: Optional[str] = None
    processed: bool = False
    processed_at: Optional[datetime] = None
    application_status: str = "pending"
    error_message: Optional[str] = None


class JobSpyScraper:
    """
    Multi-platform job scraper using JobSpy library.
    
    Supports:
    - LinkedIn
    - Indeed
    - ZipRecruiter
    - Glassdoor
    - Google Jobs
    """
    
    def __init__(self):
        if not JOBSY_AVAILABLE:
            raise ImportError(
                "JobSpy not installed. Install with: pip install python-jobspy"
            )
        self.last_scrape_results: List[ScrapedJob] = []
        self.scrape_stats = {
            "total_jobs": 0,
            "by_site": {},
            "by_location": {},
            "errors": []
        }
    
    async def scrape_jobs(
        self,
        config: JobSpyConfig,
        filter_salary_min: Optional[int] = None
    ) -> List[ScrapedJob]:
        """
        Scrape jobs using JobSpy.
        
        Args:
            config: JobSpy configuration
            filter_salary_min: Optional minimum salary filter
            
        Returns:
            List of standardized ScrapedJob objects
        """
        logger.info(f"Scraping jobs: {config.search_term} in {config.location}")
        
        # Run in thread pool since JobSpy is synchronous
        loop = asyncio.get_event_loop()
        
        try:
            jobs_df = await loop.run_in_executor(
                None,  # Default executor
                lambda: scrape_jobs(
                    site_name=config.site_name,
                    search_term=config.search_term,
                    location=config.location,
                    distance=config.distance,
                    job_type=config.job_type or None,
                    proxies=config.proxies,
                    ca_cert=config.ca_cert,
                    is_remote=config.is_remote,
                    results_wanted=config.results_wanted,
                    easy_apply=config.easy_apply,
                    description_format=config.description_format,
                    offset=config.offset,
                    hours_old=config.hours_old,
                    country_indeed=config.country_indeed,
                    verbose=config.verbose,
                    linkedin_fetch_description=config.linkedin_fetch_description,
                    linkedin_company_ids=config.linkedin_company_ids
                )
            )
            
            if jobs_df.empty:
                logger.info("No jobs found matching criteria")
                return []
            
            # Convert DataFrame to ScrapedJob objects
            jobs = self._convert_to_jobs(jobs_df, config)
            
            # Apply salary filter if specified
            if filter_salary_min:
                jobs = [j for j in jobs if self._meets_salary_requirement(j, filter_salary_min)]
            
            self.last_scrape_results = jobs
            self._update_stats(jobs)
            
            logger.info(f"Scraped {len(jobs)} jobs from {len(config.site_name)} sites")
            return jobs
            
        except Exception as e:
            logger.error(f"JobSpy scraping error: {e}")
            self.scrape_stats["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "config": config.__dict__
            })
            raise
    
    def _convert_to_jobs(
        self,
        jobs_df,
        config: JobSpyConfig
    ) -> List[ScrapedJob]:
        """Convert JobSpy DataFrame to ScrapedJob objects."""
        jobs = []
        
        for _, row in jobs_df.iterrows():
            try:
                job = ScrapedJob(
                    id=str(row.get('id', '')) or f"{row.get('site', 'unknown')}_{hash(str(row.get('title', '')))}",
                    title=str(row.get('title', '')),
                    company=str(row.get('company', 'Unknown')),
                    location=str(row.get('location', 'Remote')),
                    description=str(row.get('description', '')),
                    url=str(row.get('job_url', '')),
                    date_posted=self._parse_date(row.get('date_posted')),
                    job_type=str(row.get('job_type', '')) if pd.notna(row.get('job_type')) else None,
                    salary_source=str(row.get('salary_source', '')) if pd.notna(row.get('salary_source')) else None,
                    interval=str(row.get('interval', '')) if pd.notna(row.get('interval')) else None,
                    min_amount=float(row.get('min_amount')) if pd.notna(row.get('min_amount')) else None,
                    max_amount=float(row.get('max_amount')) if pd.notna(row.get('max_amount')) else None,
                    currency=str(row.get('currency', 'USD')) if pd.notna(row.get('currency')) else None,
                    is_remote=bool(row.get('is_remote', False)),
                    job_level=str(row.get('job_level', '')) if pd.notna(row.get('job_level')) else None,
                    company_industry=str(row.get('company_industry', '')) if pd.notna(row.get('company_industry')) else None,
                    company_url=str(row.get('company_url', '')) if pd.notna(row.get('company_url')) else None,
                    company_logo=str(row.get('company_logo', '')) if pd.notna(row.get('company_logo')) else None,
                    site=str(row.get('site', 'unknown')),
                    emails=None,  # Not provided by JobSpy
                    easy_apply=bool(row.get('easy_apply', False)) if 'easy_apply' in row else False
                )
                jobs.append(job)
            except Exception as e:
                logger.warning(f"Error converting job row: {e}")
                continue
        
        return jobs
    
    def _parse_date(self, date_val) -> Optional[datetime]:
        """Parse date from various formats."""
        if date_val is None or pd.isna(date_val):
            return None
        
        if isinstance(date_val, datetime):
            return date_val
        
        try:
            return pd.to_datetime(date_val)
        except:
            return None
    
    def _meets_salary_requirement(self, job: ScrapedJob, min_salary: int) -> bool:
        """Check if job meets minimum salary requirement."""
        if job.min_amount is None and job.max_amount is None:
            return True  # Include jobs without salary info
        
        # Check based on interval (yearly, hourly, etc.)
        if job.interval and 'hour' in job.interval.lower():
            # Convert hourly to yearly (2080 hours/year)
            hourly_min = job.min_amount or 0
            yearly_min = hourly_min * 2080
            return yearly_min >= min_salary
        else:
            # Assume yearly
            job_min = job.min_amount or 0
            return job_min >= min_salary
    
    def _update_stats(self, jobs: List[ScrapedJob]):
        """Update scraping statistics."""
        self.scrape_stats["total_jobs"] = len(jobs)
        self.scrape_stats["by_site"] = {}
        self.scrape_stats["by_location"] = {}
        
        for job in jobs:
            # By site
            site = job.site
            self.scrape_stats["by_site"][site] = self.scrape_stats["by_site"].get(site, 0) + 1
            
            # By location
            location = job.location
            self.scrape_stats["by_location"][location] = self.scrape_stats["by_location"].get(location, 0) + 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scraping statistics."""
        return self.scrape_stats
    
    def export_to_csv(self, filepath: str, jobs: List[ScrapedJob] = None):
        """Export jobs to CSV for analysis."""
        import csv
        
        jobs = jobs or self.last_scrape_results
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'id', 'title', 'company', 'location', 'description',
                'url', 'date_posted', 'job_type', 'min_amount', 'max_amount',
                'currency', 'is_remote', 'site', 'easy_apply', 'application_status'
            ])
            
            for job in jobs:
                writer.writerow([
                    job.id, job.title, job.company, job.location,
                    job.description[:500] + '...' if len(job.description) > 500 else job.description,
                    job.url, job.date_posted, job.job_type,
                    job.min_amount, job.max_amount, job.currency,
                    job.is_remote, job.site, job.easy_apply, job.application_status
                ])
        
        logger.info(f"Exported {len(jobs)} jobs to {filepath}")


# For type checking
try:
    import pandas as pd
except ImportError:
    pd = None


class JobSpySearchBuilder:
    """Builder for creating JobSpy search configurations based on resume."""
    
    @staticmethod
    def for_kent_le() -> List[JobSpyConfig]:
        """
        Create search configs for Kent Le based on his resume.
        
        Profile:
        - Location: Auburn, AL (open to remote, hybrid, in-person)
        - Target: Client Success Manager, Sales, Account Management
        - Experience: ~3 years, Supply Chain background
        - Salary: $75k+
        - Skills: CRM, Salesforce, Data Analysis, Bilingual (Vietnamese)
        """
        configs = []
        
        # Base locations to search
        locations = [
            "Auburn, AL",
            "Atlanta, GA",
            "Birmingham, AL",
            "Remote"
        ]
        
        # Job titles based on resume
        job_titles = [
            "Client Success Manager",
            "Customer Success Manager",
            "Account Manager",
            "Sales Representative",
            "Business Development Representative",
            "Account Executive",
            "Sales Development Representative",
            "Customer Success Specialist",
            "Client Relationship Manager"
        ]
        
        # Sites to search
        sites = ["linkedin", "indeed", "zip_recruiter"]
        
        for location in locations:
            for title in job_titles:
                config = JobSpyConfig(
                    site_name=sites,
                    search_term=title,
                    location=location if location != "Remote" else "",
                    is_remote=(location == "Remote"),
                    results_wanted=50,  # Per site
                    hours_old=168,  # Last 7 days
                    job_type="fulltime",
                    linkedin_fetch_description=True,
                    description_format="markdown",
                    verbose=1
                )
                configs.append(config)
        
        return configs
    
    @staticmethod
    def estimate_jobs_available(configs: List[JobSpyConfig]) -> int:
        """Estimate total jobs that will be scraped."""
        total = 0
        for config in configs:
            total += config.results_wanted * len(config.site_name)
        return total


# Convenience function for testing
async def test_jobspy_scraper():
    """Test the JobSpy scraper with Kent Le's profile."""
    scraper = JobSpyScraper()
    
    # Create search configs for Kent
    configs = JobSpySearchBuilder.for_kent_le()
    
    print(f"Created {len(configs)} search configurations")
    print(f"Estimated jobs to scrape: {JobSpySearchBuilder.estimate_jobs_available(configs)}")
    
    # Test with first config only
    test_config = configs[0]
    print(f"\nTesting with: {test_config.search_term} in {test_config.location}")
    
    jobs = await scraper.scrape_jobs(test_config, filter_salary_min=75000)
    
    print(f"Found {len(jobs)} jobs")
    
    for job in jobs[:5]:
        print(f"\n- {job.title} @ {job.company}")
        print(f"  Location: {job.location} | Remote: {job.is_remote}")
        print(f"  Salary: ${job.min_amount} - ${job.max_amount} {job.currency}")
        print(f"  URL: {job.url[:80]}...")
    
    return scraper


if __name__ == "__main__":
    # Run test
    asyncio.run(test_jobspy_scraper())
