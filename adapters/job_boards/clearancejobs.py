"""
ClearanceJobs.com Scraper

Specialized scraper for security clearance jobs.
Requires authentication and handles clearance level filtering.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin, quote_plus
import logging

from . import BaseJobBoardScraper, JobPosting, SearchCriteria

logger = logging.getLogger(__name__)


class ClearanceJobsScraper(BaseJobBoardScraper):
    """
    Scraper for ClearanceJobs.com - the leading security clearance job board.
    
    Features:
    - Login-required (session-based auth)
    - Clearance level filtering (Secret, TS, TS/SCI, Polygraph)
    - Agency detection (NSA, CIA, DoD, etc.)
    - Polygraph requirement flag
    - Special resume format handling for federal applications
    
    Note: Requires valid ClearanceJobs credentials.
    """
    
    BASE_URL = "https://www.clearancejobs.com"
    LOGIN_URL = f"{BASE_URL}/login"
    JOBS_URL = f"{BASE_URL}/jobs"
    
    # Clearance level mappings
    CLEARANCE_LEVELS = {
        'public_trust': 'Public Trust',
        'secret': 'Secret',
        'ts': 'Top Secret',
        'ts_sci': 'TS/SCI',
        'ts_sci_poly': 'TS/SCI with Polygraph',
        'doe_q': 'DOE Q',
        'doe_l': 'DOE L',
    }
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, 
                 session=None, cookies: Optional[Dict] = None):
        super().__init__(session)
        self.username = username
        self.password = password
        self.cookies = cookies or {}
        self.logged_in = False
        self.user_clearance = None  # Will be set after login
        
    def get_default_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': self.BASE_URL,
        }
        
    async def login(self) -> bool:
        """Authenticate with ClearanceJobs."""
        if not self.username or not self.password:
            logger.error("ClearanceJobs credentials not provided")
            return False
            
        try:
            # Get login page for CSRF token
            login_page = await self.fetch_text(self.LOGIN_URL)
            
            # Extract CSRF token
            csrf_match = re.search(r'name="csrf-token" content="([^"]+)"', login_page)
            csrf_token = csrf_match.group(1) if csrf_match else ""
            
            # Submit login
            login_data = {
                'username': self.username,
                'password': self.password,
                '_csrf': csrf_token,
            }
            
            async with self.session.post(
                self.LOGIN_URL,
                data=login_data,
                allow_redirects=True
            ) as response:
                if response.status == 200:
                    html = await response.text()
                    # Check if login succeeded
                    if 'logout' in html.lower() or 'my account' in html.lower():
                        self.logged_in = True
                        # Extract user clearance level from profile
                        self.user_clearance = self._extract_user_clearance(html)
                        logger.info(f"ClearanceJobs login successful. User clearance: {self.user_clearance}")
                        return True
                        
            logger.error("ClearanceJobs login failed")
            return False
            
        except Exception as e:
            logger.error(f"ClearanceJobs login error: {e}")
            return False
            
    def _extract_user_clearance(self, html: str) -> Optional[str]:
        """Extract user's clearance level from profile page."""
        clearance_match = re.search(
            r'class="[^"]*clearance[^"]*"[^>]*>([^<]+)</span>',
            html, re.IGNORECASE
        )
        if clearance_match:
            return clearance_match.group(1).strip()
        return None
        
    def get_ats_type(self, url: str) -> Optional[str]:
        """ClearanceJobs jobs may redirect to various ATS platforms."""
        if 'clearancejobs.com/job/' in url.lower():
            return 'clearancejobs'
        # Check for external ATS redirects
        if 'greenhouse.io' in url.lower():
            return 'greenhouse'
        elif 'jobs.lever.co' in url.lower():
            return 'lever'
        elif 'workday' in url.lower():
            return 'workday'
        return None
        
    def _build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        """Build ClearanceJobs search URL with filters."""
        params = []
        
        # Query
        if criteria.query:
            params.append(f"search={quote_plus(criteria.query)}")
            
        # Location
        if criteria.location:
            params.append(f"location={quote_plus(criteria.location)}")
            
        # Remote
        if criteria.remote_only:
            params.append("remote=true")
            
        # Clearance levels - use the highest requested or user's clearance
        clearance_levels = criteria.clearance_levels or []
        if self.user_clearance and self.user_clearance not in clearance_levels:
            clearance_levels.append(self.user_clearance)
            
        if clearance_levels:
            # Map to ClearanceJobs URL params
            clearance_params = []
            for level in clearance_levels:
                level_lower = level.lower().replace(' ', '_')
                if level_lower in self.CLEARANCE_LEVELS:
                    clearance_params.append(level_lower)
            if clearance_params:
                params.append(f"clearance={','.join(clearance_params)}")
                
        # Employment type
        if criteria.employment_type:
            emp_map = {
                'fulltime': 'full_time',
                'contract': 'contract',
                'parttime': 'part_time',
            }
            if criteria.employment_type.lower() in emp_map:
                params.append(f"employment={emp_map[criteria.employment_type.lower()]}")
                
        # Posted date
        if criteria.posted_within_days:
            params.append(f"posted={criteria.posted_within_days}")
            
        # Pagination
        if page > 1:
            params.append(f"page={page}")
            
        url = self.JOBS_URL
        if params:
            url += "?" + "&".join(params)
            
        return url
        
    def _parse_job_card(self, card_html: str) -> Optional[JobPosting]:
        """Parse a single job card from ClearanceJobs search results."""
        try:
            # Job ID
            job_id_match = re.search(r'data-job-id="(\d+)"', card_html)
            if not job_id_match:
                # Try URL pattern
                job_id_match = re.search(r'/job/(\d+)', card_html)
            if not job_id_match:
                return None
            job_id = job_id_match.group(1)
            
            # Title
            title_match = re.search(r'<a[^>]*class="[^"]*job-title[^"]*"[^>]*>([^<]+)</a>', card_html)
            if not title_match:
                title_match = re.search(r'<h[23][^>]*>([^<]+)</h[23]>', card_html)
            title = title_match.group(1).strip() if title_match else "Unknown"
            
            # Company
            company_match = re.search(r'class="[^"]*company[^"]*"[^>]*>([^<]+)</a>', card_html)
            company = company_match.group(1).strip() if company_match else "Unknown"
            
            # Location
            location_match = re.search(r'class="[^"]*location[^"]*"[^>]*>([^<]+)</span>', card_html)
            location = location_match.group(1).strip() if location_match else "Unknown"
            remote = 'remote' in location.lower() or 'telework' in location.lower()
            
            # Clearance level (often shown in card)
            clearance_match = re.search(
                r'class="[^"]*clearance[^"]*"[^>]*>([^<]+)</span>',
                card_html, re.IGNORECASE
            )
            clearance = clearance_match.group(1).strip() if clearance_match else None
            
            # Polygraph requirement
            poly_required = bool(re.search(r'polygraph|poly\s*required', card_html, re.IGNORECASE))
            if clearance and poly_required and 'poly' not in clearance.lower():
                clearance += " with Polygraph"
                
            # Posted date
            posted_match = re.search(r'class="[^"]*posted[^"]*"[^>]*>([^<]+)</span>', card_html)
            posted_str = posted_match.group(1).strip() if posted_match else ""
            posted_date = self._parse_posted_date(posted_str)
            
            # Build URLs
            job_url = f"{self.BASE_URL}/job/{job_id}"
            
            return JobPosting(
                id=f"cj_{job_id}",
                title=title,
                company=company,
                location=location,
                description="",  # Populated from detail page
                url=job_url,
                source='clearancejobs',
                posted_date=posted_date,
                clearance_required=clearance,
                remote=remote,
                easy_apply=False,  # ClearanceJobs usually redirects to ATS
                apply_url=job_url,
                raw_data={'polygraph_required': poly_required}
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse ClearanceJobs card: {e}")
            return None
            
    def _parse_posted_date(self, posted_str: str) -> Optional[datetime]:
        """Parse relative date strings."""
        posted_str = posted_str.lower().strip()
        
        if 'today' in posted_str or 'just posted' in posted_str:
            return datetime.now()
        elif 'yesterday' in posted_str:
            return datetime.now() - timedelta(days=1)
            
        match = re.search(r'(\d+)\s+(day|week|month|hour)s?\s+ago', posted_str)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            
            if unit == 'day':
                return datetime.now() - timedelta(days=num)
            elif unit == 'week':
                return datetime.now() - timedelta(weeks=num)
            elif unit == 'month':
                return datetime.now() - timedelta(days=num * 30)
            elif unit == 'hour':
                return datetime.now() - timedelta(hours=num)
                
        return None
        
    def _extract_agency(self, text: str) -> Optional[str]:
        """Extract government agency from job description."""
        text_lower = text.lower()
        
        agencies = {
            'nsa': 'NSA',
            'cia': 'CIA',
            'dod': 'DoD',
            'dhs': 'DHS',
            'fbi': 'FBI',
            'dea': 'DEA',
            'doj': 'DoJ',
            'department of defense': 'DoD',
            'department of homeland security': 'DHS',
            'defense intelligence agency': 'DIA',
            'national geospatial': 'NGA',
            'national reconnaissance': 'NRO',
        }
        
        for pattern, agency in agencies.items():
            if pattern in text_lower:
                return agency
                
        return None
        
    async def search(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Search ClearanceJobs for jobs matching criteria."""
        if not self.logged_in:
            success = await self.login()
            if not success:
                logger.error("Cannot search ClearanceJobs - login failed")
                return []
                
        jobs = []
        page = 1
        max_pages = (criteria.max_results // 25) + 1
        
        while len(jobs) < criteria.max_results and page <= max_pages:
            url = self._build_search_url(criteria, page)
            
            try:
                html = await self.fetch_text(url)
                
                # Parse job cards
                # ClearanceJobs uses various card structures
                card_patterns = [
                    r'<div[^>]*class="[^"]*job-card[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
                    r'<div[^>]*data-testid="job-listing"[^>]*>(.*?)</div>\s*</div>\s*</div>',
                    r'<article[^>]*class="[^"]*job[^"]*"[^>]*>(.*?)</article>',
                ]
                
                page_jobs = []
                for pattern in card_patterns:
                    cards = re.findall(pattern, html, re.DOTALL)
                    for card in cards:
                        job = self._parse_job_card(card)
                        if job and job.id not in [j.id for j in page_jobs]:
                            # Filter by clearance level if specified
                            if criteria.clearance_levels:
                                if job.clearance_required:
                                    job_clearance = job.clearance_required.lower()
                                    if not any(
                                        c.lower() in job_clearance or job_clearance in c.lower()
                                        for c in criteria.clearance_levels
                                    ):
                                        continue
                            page_jobs.append(job)
                            
                if not page_jobs:
                    break
                    
                jobs.extend(page_jobs)
                page += 1
                
                # Respect rate limits - be gentle with auth-required sites
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"ClearanceJobs search failed for page {page}: {e}")
                break
                
        # Enrich top jobs with details
        detail_limit = min(30, len(jobs))
        for job in jobs[:detail_limit]:
            try:
                await self._enrich_job_details(job)
            except Exception as e:
                logger.warning(f"Failed to enrich ClearanceJobs detail: {e}")
                
        return jobs[:criteria.max_results]
        
    async def _enrich_job_details(self, job: JobPosting):
        """Fetch full job description and detect external apply URL."""
        try:
            html = await self.fetch_text(job.url)
            
            # Extract description
            desc_match = re.search(
                r'<div[^>]*class="[^"]*job-description[^"]*"[^>]*>(.*?)</div>\s*</div>',
                html, re.DOTALL
            )
            if desc_match:
                description = desc_match.group(1)
                description = re.sub(r'<[^>]+>', ' ', description)
                description = re.sub(r'\s+', ' ', description).strip()
                job.description = description
                
            # Look for external apply link
            apply_match = re.search(
                r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*apply[^"]*"[^>]*>',
                html, re.IGNORECASE
            )
            if apply_match:
                external_url = apply_match.group(1)
                if external_url.startswith('http'):
                    job.apply_url = external_url
                    
            # Extract agency
            agency = self._extract_agency(job.description or "")
            if agency:
                job.raw_data['agency'] = agency
                
        except Exception as e:
            logger.warning(f"Failed to fetch ClearanceJobs details: {e}")


# For testing
if __name__ == "__main__":
    import asyncio
    import os
    
    async def test():
        username = os.getenv('CLEARANCEJOBS_USER')
        password = os.getenv('CLEARANCEJOBS_PASS')
        
        if not username or not password:
            print("Set CLEARANCEJOBS_USER and CLEARANCEJOBS_PASS env vars")
            return
            
        criteria = SearchCriteria(
            query="software engineer",
            location="Washington, DC",
            clearance_levels=['Secret', 'Top Secret'],
            max_results=10
        )
        
        async with ClearanceJobsScraper(username, password) as scraper:
            jobs = await scraper.search(criteria)
            print(f"Found {len(jobs)} clearance jobs")
            for job in jobs[:3]:
                print(f"\n{job.title} at {job.company}")
                print(f"  Location: {job.location}")
                print(f"  Clearance: {job.clearance_required}")
                print(f"  Agency: {job.raw_data.get('agency', 'Unknown')}")
                
    asyncio.run(test())
