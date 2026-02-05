#!/usr/bin/env python3
"""
Exa AI Job Search - Semantic job discovery.

Uses Exa AI (exa.ai) for neural/semantic search to find:
1. Companies matching criteria
2. Job postings based on meaning, not just keywords
3. Career pages with open roles

Inspired by BrowserBase template: exa-browserbase
"""

import asyncio
import os
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredCompany:
    """Company discovered via Exa AI."""
    name: str
    url: str
    description: str = ""
    careers_url: str = ""
    relevance_score: float = 0.0


@dataclass
class DiscoveredJob:
    """Job discovered via Exa AI."""
    title: str
    company: str
    url: str
    description: str = ""
    location: str = ""
    posted_date: str = ""
    relevance_score: float = 0.0


class ExaJobSearch:
    """
    Semantic job search using Exa AI.
    
    Unlike keyword search (Indeed, LinkedIn), Exa uses neural embeddings
to find jobs based on semantic meaning and context.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('EXA_API_KEY')
        self.base_url = "https://api.exa.ai"
        
        if not self.api_key:
            logger.warning("EXA_API_KEY not set. Exa search will not work.")
    
    async def search_companies(
        self,
        query: str,
        num_results: int = 10,
        include_domains: Optional[List[str]] = None
    ) -> List[DiscoveredCompany]:
        """
        Search for companies using semantic query.
        
        Example queries:
        - "fast-growing SaaS companies in cybersecurity"
        - "AI startups hiring machine learning engineers"
        - "remote-first tech companies with good culture"
        """
        if not self.api_key:
            logger.error("Exa API key not configured")
            return []
        
        logger.info(f"[Exa] Searching companies: {query}")
        
        payload = {
            "query": query,
            "numResults": num_results,
            "type": "neural",  # Use neural/semantic search
            "useAutoprompt": True,  # Let Exa optimize the query
            "contents": {
                "text": True,
                "highlights": True
            }
        }
        
        if include_domains:
            payload["includeDomains"] = include_domains
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/search",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload
                ) as response:
                    if response.status != 200:
                        error = await response.text()
                        logger.error(f"[Exa] Search failed: {error}")
                        return []
                    
                    data = await response.json()
                    
                    companies = []
                    for result in data.get('results', []):
                        company = DiscoveredCompany(
                            name=self._extract_company_name(result.get('url', '')),
                            url=result.get('url', ''),
                            description=result.get('text', '')[:500],
                            relevance_score=result.get('score', 0)
                        )
                        companies.append(company)
                    
                    logger.info(f"[Exa] Found {len(companies)} companies")
                    return companies
                    
        except Exception as e:
            logger.error(f"[Exa] Search error: {e}")
            return []
    
    async def find_careers_pages(
        self,
        company_name: str,
        company_url: str
    ) -> str:
        """
        Find the careers/jobs page for a company.
        
        Uses Exa to search within the company's domain for career pages.
        """
        if not self.api_key:
            return ""
        
        # Extract domain
        domain = company_url.replace('https://', '').replace('http://', '').split('/')[0]
        
        query = f"{company_name} careers jobs hiring"
        
        payload = {
            "query": query,
            "numResults": 5,
            "includeDomains": [domain],
            "type": "neural"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/search",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload
                ) as response:
                    if response.status != 200:
                        return ""
                    
                    data = await response.json()
                    
                    for result in data.get('results', []):
                        url = result.get('url', '')
                        # Check if it's a careers/jobs page
                        if any(x in url.lower() for x in ['career', 'jobs', 'join', 'work']):
                            return url
                    
                    return ""
                    
        except Exception as e:
            logger.error(f"[Exa] Careers search error: {e}")
            return ""
    
    async def search_jobs(
        self,
        role_description: str,
        location: str = "remote",
        num_results: int = 20
    ) -> List[DiscoveredJob]:
        """
        Search for specific job postings.
        
        Uses semantic understanding to match jobs, not just keywords.
        
        Example:
        - "Senior backend engineer with Python and AWS experience"
        - "Product manager for B2B SaaS platform"
        - "DevOps engineer focused on Kubernetes and CI/CD"
        """
        if not self.api_key:
            logger.error("Exa API key not configured")
            return []
        
        logger.info(f"[Exa] Searching jobs: {role_description}")
        
        # Construct semantic query
        query = f"{role_description} jobs {location}"
        
        payload = {
            "query": query,
            "numResults": num_results,
            "type": "neural",
            "useAutoprompt": True,
            "contents": {
                "text": True
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/search",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload
                ) as response:
                    if response.status != 200:
                        return []
                    
                    data = await response.json()
                    
                    jobs = []
                    for result in data.get('results', []):
                        url = result.get('url', '')
                        
                        # Filter to likely job postings
                        if not self._is_likely_job_url(url):
                            continue
                        
                        job = DiscoveredJob(
                            title=self._extract_job_title(result.get('text', ''), url),
                            company=self._extract_company_from_url(url),
                            url=url,
                            description=result.get('text', '')[:500],
                            location=location,
                            relevance_score=result.get('score', 0)
                        )
                        jobs.append(job)
                    
                    logger.info(f"[Exa] Found {len(jobs)} jobs")
                    return jobs
                    
        except Exception as e:
            logger.error(f"[Exa] Job search error: {e}")
            return []
    
    def _extract_company_name(self, url: str) -> str:
        """Extract company name from URL."""
        try:
            domain = url.replace('https://', '').replace('http://', '').split('/')[0]
            parts = domain.replace('www.', '').split('.')
            if len(parts) >= 2:
                return parts[0].capitalize()
            return domain
        except:
            return "Unknown"
    
    def _extract_job_title(self, text: str, url: str) -> str:
        """Extract job title from text or URL."""
        # Try common patterns
        import re
        
        # Look for "Title at Company" or "Title | Company"
        patterns = [
            r'([A-Za-z\s]+)(?:\s+at\s+|\s*\|\s*|[\-–])\s*([A-Za-z\s]+)',
            r'(Senior|Staff|Principal|Lead)?\s*(Software|Engineer|Developer|Manager|Designer)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text[:200])
            if match:
                return match.group(0).strip()
        
        # Fallback to URL path
        if '/jobs/' in url or '/careers/' in url:
            parts = url.split('/')
            for part in reversed(parts):
                if part and '-' in part:
                    return part.replace('-', ' ').title()
        
        return "Unknown Position"
    
    def _extract_company_from_url(self, url: str) -> str:
        """Extract company from job URL."""
        # Check for common ATS patterns
        if 'greenhouse.io' in url:
            match = url.split('greenhouse.io/')
            if len(match) > 1:
                return match[1].split('/')[0].capitalize()
        elif 'lever.co' in url:
            return url.split('lever.co/')[1].split('/')[0].capitalize()
        elif 'workday.com' in url:
            return "Workday Company"
        
        return self._extract_company_name(url)
    
    def _is_likely_job_url(self, url: str) -> bool:
        """Check if URL is likely a job posting."""
        job_indicators = [
            'jobs', 'careers', 'job', 'position', 'opening',
            'greenhouse.io', 'lever.co', 'workday.com',
            'apply', 'hiring'
        ]
        
        url_lower = url.lower()
        return any(ind in url_lower for ind in job_indicators)


class HybridJobDiscovery:
    """
    Combines Exa AI semantic search with traditional job board scraping.
    
    Best of both worlds:
    - Exa: Discovers hidden opportunities, semantic matching
    - JobSpy: High-volume, structured data from major boards
    """
    
    def __init__(self):
        self.exa = ExaJobSearch()
        
    async def discover_jobs(
        self,
        role: str,
        skills: List[str],
        location: str = "remote",
        target_count: int = 50
    ) -> List[Dict]:
        """
        Discover jobs using multiple sources.
        
        Args:
            role: Target role (e.g., "Software Engineer")
            skills: Key skills (e.g., ["Python", "AWS", "React"])
            location: Job location
            target_count: Target number of jobs
        """
        all_jobs = []
        
        # Source 1: Exa AI semantic search
        logger.info("[Discovery] Searching with Exa AI...")
        semantic_query = f"{role} with {', '.join(skills)} experience {location}"
        exa_jobs = await self.exa.search_jobs(semantic_query, location, num_results=20)
        
        for job in exa_jobs:
            all_jobs.append({
                'title': job.title,
                'company': job.company,
                'url': job.url,
                'description': job.description,
                'location': job.location,
                'source': 'exa',
                'relevance': job.relevance_score
            })
        
        # Source 2: Traditional job boards (JobSpy)
        logger.info("[Discovery] Searching job boards...")
        try:
            from jobspy import scrape_jobs
            import pandas as pd
            
            search_term = f"{role} {' '.join(skills[:3])}"
            df = scrape_jobs(
                site_name=['indeed', 'zip_recruiter'],
                search_term=search_term,
                location=location,
                results_wanted=50,
                hours_old=72
            )
            
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    apply_url = row.get('job_url_direct')
                    if pd.notna(apply_url) and 'indeed.com/job' not in str(apply_url):
                        all_jobs.append({
                            'title': row['title'],
                            'company': row['company'] if pd.notna(row['company']) else 'Unknown',
                            'url': str(apply_url),
                            'description': str(row.get('description', ''))[:300],
                            'location': row.get('location', location),
                            'source': 'jobspy',
                            'relevance': 0.5
                        })
        except Exception as e:
            logger.warning(f"[Discovery] JobSpy error: {e}")
        
        # Deduplicate
        seen = set()
        unique = []
        for job in all_jobs:
            if job['url'] not in seen:
                seen.add(job['url'])
                unique.append(job)
        
        # Sort by relevance
        unique.sort(key=lambda x: x.get('relevance', 0), reverse=True)
        
        logger.info(f"[Discovery] Total unique jobs: {len(unique)}")
        return unique[:target_count]


# Test
async def test_exa():
    """Test Exa search."""
    search = HybridJobDiscovery()
    
    jobs = await search.discover_jobs(
        role="Software Engineer",
        skills=["Python", "AWS", "ServiceNow"],
        location="remote",
        target_count=20
    )
    
    print(f"Found {len(jobs)} jobs:\n")
    for job in jobs[:10]:
        print(f"  - {job['title']} @ {job['company']}")
        print(f"    Source: {job['source']}")
        print(f"    URL: {job['url'][:60]}...")
        print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_exa())
