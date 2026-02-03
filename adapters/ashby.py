"""
Ashby Adapter - Tier 1 (API-Based)
High-growth startups use Ashby. Simple GraphQL/JSON API.
"""

import aiohttp
import asyncio
import json
import re
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


# Popular companies using Ashby
DEFAULT_ASHBY_COMPANIES = [
    "anthropic",
    "cursor",
    "linear",
    "rayshift",
    "arc",
    "persona",
    "mainframe",
    "luminous",
    "semgrep",
    "hightouch",
]


class AshbyAdapter(JobPlatformAdapter):
    """
    Ashby job board adapter.
    Uses public GraphQL API - no browser needed.
    """
    
    platform = PlatformType.ASHBY
    tier = "api"
    
    # Ashby GraphQL endpoint
    API_URL = "https://jobs.ashbyhq.com/api/non-user-graphql"
    
    def __init__(self, browser_manager=None, companies: List[str] = None):
        super().__init__(browser_manager)
        self.companies = companies or DEFAULT_ASHBY_COMPANIES
        self._session = None
    
    async def _get_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)",
                    "Content-Type": "application/json",
                }
            )
        return self._session
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search Ashby job boards across multiple companies."""
        session = await self._get_session()
        all_jobs = []
        
        query_lower = " ".join(criteria.roles).lower()
        
        for company in self.companies:
            try:
                # Ashby uses GraphQL for job listings
                graphql_query = {
                    "operationName": "ApiJobBoardWithTeams",
                    "variables": {"organizationHostedJobsPageName": company},
                    "query": """
                        query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
                            jobBoard: jobBoardByHostedJobsPageName(
                                organizationHostedJobsPageName: $organizationHostedJobsPageName
                            ) {
                                title
                                teams {
                                    id
                                    name
                                    parentTeamId
                                }
                                jobPostings {
                                    id
                                    title
                                    teamId
                                    locationId
                                    employmentType
                                    createdAt
                                    externalLink
                                    isListed
                                }
                                locations {
                                    id
                                    name
                                }
                            }
                        }
                    """
                }
                
                async with session.post(
                    self.API_URL,
                    json=graphql_query,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        continue
                    
                    data = await resp.json()
                    job_board = data.get("data", {}).get("jobBoard", {})
                    
                    if not job_board:
                        continue
                    
                    # Build location lookup
                    locations = {
                        loc["id"]: loc["name"] 
                        for loc in job_board.get("locations", [])
                    }
                    
                    # Build team lookup
                    teams = {
                        team["id"]: team["name"]
                        for team in job_board.get("teams", [])
                    }
                    
                    for posting in job_board.get("jobPostings", []):
                        if not posting.get("isListed"):
                            continue
                        
                        title = posting.get("title", "").lower()
                        
                        # Filter by role keywords
                        if not any(kw.lower() in title for kw in criteria.roles):
                            continue
                        
                        location_id = posting.get("locationId")
                        location = locations.get(location_id, "")
                        location_lower = location.lower()
                        
                        # Filter by location if specified
                        if criteria.locations:
                            if not any(
                                loc.lower() in location_lower or 
                                "remote" in location_lower or
                                "remote" in loc.lower() and "remote" in location_lower
                                for loc in criteria.locations
                            ):
                                continue
                        
                        team_id = posting.get("teamId")
                        team = teams.get(team_id, "")
                        
                        job_url = posting.get("externalLink") or f"https://jobs.ashbyhq.com/{company}/{posting['id']}"
                        
                        all_jobs.append(JobPosting(
                            id=f"ashby_{company}_{posting['id']}",
                            platform=self.platform,
                            title=posting.get("title", ""),
                            company=company.replace("-", " ").title(),
                            location=location,
                            url=job_url,
                            description=f"Team: {team}",
                            easy_apply=True,
                            remote="remote" in location_lower,
                            job_type=posting.get("employmentType", "full-time").lower()
                        ))
                
                await asyncio.sleep(0.2)
                
            except Exception as e:
                print(f"[Ashby] Error fetching {company}: {e}")
                continue
        
        print(f"[Ashby] Found {len(all_jobs)} jobs across {len(self.companies)} companies")
        return all_jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details from Ashby."""
        session = await self._get_session()
        
        # Extract company and job ID from URL
        # Format: https://jobs.ashbyhq.com/{company}/{id}
        parts = job_url.rstrip("/").split("/")
        job_id = parts[-1]
        company = parts[-3] if len(parts) >= 3 else "unknown"
        
        # Fetch job details via GraphQL
        graphql_query = {
            "operationName": "ApiJobPosting",
            "variables": {
                "jobPostingId": job_id,
                "organizationHostedJobsPageName": company
            },
            "query": """
                query ApiJobPosting($jobPostingId: String!, $organizationHostedJobsPageName: String!) {
                    jobPosting: jobPostingById(
                        id: $jobPostingId
                        organizationHostedJobsPageName: $organizationHostedJobsPageName
                    ) {
                        id
                        title
                        descriptionHtml
                        employmentType
                        location {
                            name
                        }
                        team {
                            name
                        }
                        publishedAt
                    }
                }
            """
        }
        
        async with session.post(self.API_URL, json=graphql_query) as resp:
            if resp.status != 200:
                raise Exception(f"Job not found: {job_url}")
            
            data = await resp.json()
            posting = data.get("data", {}).get("jobPosting", {})
            
            if not posting:
                raise Exception(f"Job not found: {job_url}")
            
            location = posting.get("location", {}).get("name", "")
            
            return JobPosting(
                id=f"ashby_{company}_{job_id}",
                platform=self.platform,
                title=posting.get("title", ""),
                company=company.replace("-", " ").title(),
                location=location,
                url=job_url,
                description=posting.get("descriptionHtml", ""),
                easy_apply=True,
                remote="remote" in location.lower(),
                job_type=posting.get("employmentType", "full-time").lower()
            )
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """Apply to Ashby job."""
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message=f"Apply at: {job.url}",
            external_url=job.url
        )


async def test_ashby():
    """Test Ashby adapter."""
    from .base import SearchConfig
    
    adapter = AshbyAdapter()
    
    criteria = SearchConfig(
        roles=["software engineer", "engineer", "developer"],
        locations=["Remote"],
        posted_within_days=30
    )
    
    try:
        jobs = await adapter.search_jobs(criteria)
        print(f"\nFound {len(jobs)} jobs:")
        for job in jobs[:10]:
            print(f"  - {job.title} at {job.company} ({job.location})")
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(test_ashby())
