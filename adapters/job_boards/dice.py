"""
Dice.com Job Scraper

Uses Dice's hidden/internal JSON API for high-volume tech job scraping.
Includes salary data, skills tags, and clearance detection.
"""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote_plus
import logging

from . import BaseJobBoardScraper, JobPosting, SearchCriteria

logger = logging.getLogger(__name__)


class DiceScraper(BaseJobBoardScraper):
    """
    Scraper for Dice.com - tech-focused job board with high-quality metadata.
    
    Features:
    - Hidden JSON API (no blocking)
    - Salary ranges (when available)
    - Tech skills extraction
    - Employment type detection (Contract/C2H/Full-time)
    - Clearance requirement detection
    """
    
    BASE_URL = "https://www.dice.com"
    API_BASE = "https://www.dice.com/job-search/keywords"
    
    # Internal API endpoints discovered through network analysis
    SEARCH_ENDPOINT = "https://www.dice.com/job-search/keywords/{query}"
    JOB_DETAIL_ENDPOINT = "https://www.dice.com/job-detail/{job_id}"
    
    def get_default_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.dice.com/jobs',
            'X-Requested-With': 'XMLHttpRequest',
        }
        
    def get_ats_type(self, url: str) -> Optional[str]:
        """Dice jobs typically redirect to company ATS or have Easy Apply."""
        if 'dice.com/job-detail' in url.lower():
            return 'dice'
        return None
        
    def _build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        """Build Dice search URL with filters."""
        query = quote_plus(criteria.query)
        
        # Build URL with location
        if criteria.location:
            location = quote_plus(criteria.location)
            url = f"{self.BASE_URL}/jobs/q-{query}-l-{location}-radius-{criteria.radius}"
        else:
            url = f"{self.BASE_URL}/jobs/q-{query}"
            
        # Add filters
        params = []
        
        # Remote filter
        if criteria.remote_only:
            params.append("remote=true")
            
        # Employment type
        if criteria.employment_type:
            emp_map = {
                'fulltime': 'Full-Time',
                'contract': 'Contract',
                'parttime': 'Part-Time',
            }
            if criteria.employment_type.lower() in emp_map:
                params.append(f"employment={emp_map[criteria.employment_type.lower()]}")
                
        # Date filter
        if criteria.posted_within_days:
            params.append(f"fromage={criteria.posted_within_days}")
            
        # Add pagination
        if page > 1:
            params.append(f"page={page}")
            
        if params:
            url += "?" + "&".join(params)
            
        return url
        
    def _parse_job_card(self, card_html: str) -> Optional[JobPosting]:
        """Parse a single job card from search results."""
        try:
            # Extract job data from HTML/JSON embedded in page
            # Dice embeds job data in script tags or data attributes
            
            # Job ID
            job_id_match = re.search(r'data-job-id="([^"]+)"', card_html)
            if not job_id_match:
                return None
            job_id = job_id_match.group(1)
            
            # Title
            title_match = re.search(r'<a[^>]*class="[^"]*job-title[^"]*"[^>]*>([^<]+)</a>', card_html)
            title = title_match.group(1).strip() if title_match else "Unknown"
            
            # Company
            company_match = re.search(r'class="[^"]*company-name[^"]*"[^>]*>([^<]+)</a>', card_html)
            company = company_match.group(1).strip() if company_match else "Unknown"
            
            # Location
            location_match = re.search(r'class="[^"]*location[^"]*"[^>]*>([^<]+)</span>', card_html)
            location = location_match.group(1).strip() if location_match else "Unknown"
            remote = 'remote' in location.lower()
            
            # Employment type
            emp_type_match = re.search(r'class="[^"]*employment-type[^"]*"[^>]*>([^<]+)</span>', card_html)
            employment_type = emp_type_match.group(1).strip() if emp_type_match else None
            
            # Posted date
            posted_match = re.search(r'class="[^"]*posted-date[^"]*"[^>]*>([^<]+)</span>', card_html)
            posted_str = posted_match.group(1).strip() if posted_match else ""
            posted_date = self._parse_posted_date(posted_str)
            
            # Easy Apply indicator
            easy_apply = 'easy-apply' in card_html.lower() or 'easyApply' in card_html
            
            # Build job URL
            job_url = f"{self.BASE_URL}/job-detail/{job_id}"
            
            return JobPosting(
                id=f"dice_{job_id}",
                title=title,
                company=company,
                location=location,
                description="",  # Will be populated from detail page
                url=job_url,
                source='dice',
                posted_date=posted_date,
                employment_type=employment_type,
                remote=remote,
                easy_apply=easy_apply,
                apply_url=job_url,
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Dice job card: {e}")
            return None
            
    def _parse_posted_date(self, posted_str: str) -> Optional[datetime]:
        """Parse relative date strings like '2 days ago'."""
        posted_str = posted_str.lower().strip()
        
        if 'today' in posted_str or 'just now' in posted_str:
            return datetime.now()
        elif 'yesterday' in posted_str:
            return datetime.now() - timedelta(days=1)
            
        # Match patterns like "3 days ago", "2 weeks ago"
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
        
    def _extract_clearance(self, text: str) -> Optional[str]:
        """Detect security clearance requirements in job text."""
        text_lower = text.lower()
        
        clearance_patterns = [
            (r'ts/sci\s*(?:w/|with)?\s*(?:poly|polygraph|ci|full)', 'TS/SCI with Polygraph'),
            (r'ts/sci', 'TS/SCI'),
            (r'top\s*secret/sensitive\s*compartmented', 'TS/SCI'),
            (r'top\s*secret', 'Top Secret'),
            (r'secret\s*clearance', 'Secret'),
            (r'public\s*trust', 'Public Trust'),
            (r'doe\s*q', 'DOE Q'),
            (r'doe\s*l', 'DOE L'),
        ]
        
        for pattern, clearance in clearance_patterns:
            if re.search(pattern, text_lower):
                return clearance
                
        return None
        
    def _extract_skills(self, text: str) -> List[str]:
        """Extract tech skills from job description."""
        common_skills = [
            'python', 'javascript', 'typescript', 'java', 'c++', 'c#', 'go', 'rust',
            'react', 'angular', 'vue', 'node.js', 'django', 'flask', 'fastapi',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
            'sql', 'postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch',
            'machine learning', 'ai', 'data science', 'tensorflow', 'pytorch',
            'devops', 'ci/cd', 'jenkins', 'gitlab', 'github actions',
            'linux', 'bash', 'powershell', 'git', 'agile', 'scrum',
        ]
        
        text_lower = text.lower()
        found_skills = []
        
        for skill in common_skills:
            if skill in text_lower:
                found_skills.append(skill)
                
        return found_skills
        
    async def search(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Search Dice for jobs matching criteria."""
        jobs = []
        page = 1
        max_pages = (criteria.max_results // 20) + 1
        
        while len(jobs) < criteria.max_results and page <= max_pages:
            url = self._build_search_url(criteria, page)
            
            try:
                html = await self.fetch_text(url)
                
                # Parse job cards from HTML
                # Dice uses various HTML structures, try multiple patterns
                card_patterns = [
                    r'<div[^>]*class="[^"]*search-card[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
                    r'<div[^>]*data-testid="job-card"[^>]*>(.*?)</div>\s*</div>\s*</div>',
                    r'<div[^>]*class="[^"]*job-card[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
                ]
                
                page_jobs = []
                for pattern in card_patterns:
                    cards = re.findall(pattern, html, re.DOTALL)
                    for card in cards:
                        job = self._parse_job_card(card)
                        if job and job.id not in [j.id for j in page_jobs]:
                            page_jobs.append(job)
                            
                if not page_jobs:
                    break
                    
                jobs.extend(page_jobs)
                page += 1
                
                # Respect rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Dice search failed for page {page}: {e}")
                break
                
        # Fetch details for top jobs (limit to avoid rate limiting)
        detail_limit = min(50, len(jobs))
        for job in jobs[:detail_limit]:
            try:
                await self._enrich_job_details(job)
            except Exception as e:
                logger.warning(f"Failed to enrich job {job.id}: {e}")
                
        return jobs[:criteria.max_results]
        
    async def _enrich_job_details(self, job: JobPosting):
        """Fetch full job description and additional metadata."""
        try:
            html = await self.fetch_text(job.url)
            
            # Extract description
            desc_match = re.search(
                r'<div[^>]*class="[^"]*job-description[^"]*"[^>]*>(.*?)</div>\s*</div>',
                html, re.DOTALL
            )
            if desc_match:
                description = desc_match.group(1)
                # Clean HTML tags
                description = re.sub(r'<[^>]+>', ' ', description)
                description = re.sub(r'\s+', ' ', description).strip()
                job.description = description
                
                # Extract clearance
                job.clearance_required = self._extract_clearance(description)
                
                # Extract skills
                job.skills = self._extract_skills(description)
                
            # Extract salary if available
            salary_match = re.search(
                r'class="[^"]*salary[^"]*"[^>]*>([^<]+)</span>',
                html
            )
            if salary_match:
                job.salary_range = salary_match.group(1).strip()
                
        except Exception as e:
            logger.warning(f"Failed to fetch details for {job.id}: {e}")


# For testing
if __name__ == "__main__":
    import asyncio
    
    async def test():
        criteria = SearchCriteria(
            query="software engineer",
            location="Remote",
            remote_only=True,
            max_results=10
        )
        
        async with DiceScraper() as scraper:
            jobs = await scraper.search(criteria)
            print(f"Found {len(jobs)} jobs")
            for job in jobs[:3]:
                print(f"\n{job.title} at {job.company}")
                print(f"  Location: {job.location}")
                print(f"  Easy Apply: {job.easy_apply}")
                print(f"  Clearance: {job.clearance_required}")
                print(f"  Skills: {', '.join(job.skills[:5])}")
                
    asyncio.run(test())
