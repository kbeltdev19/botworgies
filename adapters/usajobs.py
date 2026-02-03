"""
USAJobs Adapter - Federal Government Jobs
Official API for USAJobs.gov
"""

import aiohttp
import asyncio
import os
from typing import List, Optional
from datetime import datetime, timedelta
from urllib.parse import quote

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


class USAJobsAdapter(JobPlatformAdapter):
    """
    USAJobs.gov adapter for federal government jobs.
    Uses official REST API.
    
    API Docs: https://developer.usajobs.gov/
    
    Requires API key (get from https://developer.usajobs.gov/apirequest/Index)
    Set USAJOBS_API_KEY and USAJOBS_EMAIL in environment variables.
    """
    
    platform = PlatformType.USAJOBS
    tier = "api"
    
    API_URL = "https://data.usajobs.gov/api/search"
    
    def __init__(self, browser_manager=None, api_key: str = None, user_email: str = None):
        super().__init__(browser_manager)
        self.api_key = api_key or os.environ.get("USAJOBS_API_KEY")
        self.user_email = user_email or os.environ.get("USAJOBS_EMAIL")
        self._session = None
    
    async def _get_session(self):
        if not self._session:
            headers = {
                "User-Agent": f"JobBot/1.0 ({self.user_email or 'user@example.com'})",
                "Accept": "application/json",
            }
            if self.api_key:
                headers["Authorization-Key"] = self.api_key
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search USAJobs for federal positions."""
        session = await self._get_session()
        all_jobs = []
        
        query = " ".join(criteria.roles)
        location = criteria.locations[0] if criteria.locations else ""
        
        params = {
            "Keyword": query,
            "ResultsPerPage": "100",
            "Page": "1",
            "SortField": "OpenDate",
            "SortDirection": "Desc",
        }
        
        # Location
        if location and location.lower() != "remote":
            params["LocationName"] = location
        
        # Remote filter
        if "remote" in [loc.lower() for loc in criteria.locations]:
            params["PositionOfferingTypeCode"] = "15318"  # Remote/telework
        
        # Security clearance (from required_keywords)
        clearance_levels = {
            "secret": "1",
            "top secret": "2",
            "ts/sci": "3",
            "public trust": "4",
        }
        for kw in criteria.required_keywords:
            kw_lower = kw.lower()
            if kw_lower in clearance_levels:
                params["SecurityClearanceRequired"] = clearance_levels[kw_lower]
                break
        
        try:
            page = 1
            max_pages = 5
            
            while page <= max_pages:
                params["Page"] = str(page)
                
                async with session.get(
                    self.API_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        print(f"[USAJobs] API error: {resp.status}")
                        break
                    
                    data = await resp.json()
                    search_results = data.get("SearchResult", {})
                    items = search_results.get("SearchResultItems", [])
                    
                    if not items:
                        break
                    
                    for item in items:
                        descriptor = item.get("MatchedObjectDescriptor", {})
                        
                        title = descriptor.get("PositionTitle", "")
                        department = descriptor.get("DepartmentName", "")
                        agency = descriptor.get("OrganizationName", "")
                        company = f"{department} - {agency}" if agency != department else department
                        
                        # Location
                        locations = descriptor.get("PositionLocation", [])
                        location_str = ", ".join([
                            f"{loc.get('CityName', '')}, {loc.get('CountrySubDivisionCode', '')}"
                            for loc in locations
                        ]) if locations else "United States"
                        
                        # Dates
                        date_posted = None
                        date_str = descriptor.get("PublicationStartDate", "")
                        if date_str:
                            try:
                                date_posted = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            except ValueError:
                                pass
                        
                        # Filter by date
                        if criteria.posted_within_days and date_posted:
                            cutoff = datetime.now(date_posted.tzinfo) - timedelta(days=criteria.posted_within_days)
                            if date_posted < cutoff:
                                continue
                        
                        # Apply URL
                        apply_uri = descriptor.get("ApplyURI", [{}])[0]
                        url = apply_uri.get("URI", "") if apply_uri else ""
                        
                        # Description
                        description_parts = []
                        if descriptor.get("UserArea", {}).get("Details", {}).get("JobSummary"):
                            description_parts.append(descriptor["UserArea"]["Details"]["JobSummary"])
                        
                        # Requirements
                        requirements = descriptor.get("QualificationSummary", "")
                        
                        # Salary
                        salary_min = descriptor.get("PositionRemuneration", [{}])[0].get("MinimumRange", "")
                        salary_max = descriptor.get("PositionRemuneration", [{}])[0].get("MaximumRange", "")
                        salary_range = f"${salary_min} - ${salary_max}" if salary_min and salary_max else ""
                        
                        # Security clearance
                        clearance = ""
                        if descriptor.get("UserArea", {}).get("Details", {}).get("SecurityClearanceRequired"):
                            clearance = descriptor["UserArea"]["Details"]["SecurityClearanceRequired"]
                        
                        all_jobs.append(JobPosting(
                            id=f"usajobs_{item.get('MatchedObjectId', hash(title))}",
                            platform=self.platform,
                            title=title,
                            company=company,
                            location=location_str,
                            url=url,
                            description="\n".join(description_parts),
                            requirements=requirements,
                            salary_range=salary_range,
                            posted_date=date_posted,
                            easy_apply=False,
                            remote="remote" in location_str.lower() or any(
                                loc.get("Country", "") == "USA" and not loc.get("CityName")
                                for loc in locations
                            ),
                            clearance_required=clearance,
                            job_type="full-time"  # Most fed jobs are permanent
                        ))
                
                # Check for more pages
                result_count = search_results.get("SearchResultCountAll", 0)
                if len(all_jobs) >= result_count or len(items) < 100:
                    break
                
                page += 1
                await asyncio.sleep(0.5)
        
        except Exception as e:
            print(f"[USAJobs] Error: {e}")
        
        print(f"[USAJobs] Found {len(all_jobs)} jobs")
        return all_jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details from USAJobs."""
        # The API already returns full details, so this would just fetch by ID
        # For now, return a placeholder
        return JobPosting(
            id=f"usajobs_{hash(job_url)}",
            platform=self.platform,
            title="See job posting",
            company="U.S. Government",
            location="United States",
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
        """Apply to USAJobs position."""
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message=f"Federal application required at USAJobs.gov: {job.url}",
            external_url=job.url
        )


async def test_usajobs():
    """Test USAJobs adapter."""
    from .base import SearchConfig
    
    adapter = USAJobsAdapter()
    
    criteria = SearchConfig(
        roles=["software engineer", "information technology"],
        locations=["Washington, DC", "Remote"],
        posted_within_days=30
    )
    
    try:
        jobs = await adapter.search_jobs(criteria)
        print(f"\nFound {len(jobs)} jobs:")
        for job in jobs[:10]:
            print(f"  - {job.title}")
            print(f"    Company: {job.company}")
            print(f"    Location: {job.location}")
            if job.salary_range:
                print(f"    Salary: {job.salary_range}")
            if job.clearance_required:
                print(f"    Clearance: {job.clearance_required}")
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(test_usajobs())
