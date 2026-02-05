#!/usr/bin/env python3
"""
Direct ATS Scrapers - Bypass LinkedIn, scrape directly from company career sites.

Sources:
- Greenhouse (boards.greenhouse.io)
- Lever (jobs.lever.co)
- Workday (company.wd101.myworkdayjobs.com)
- SmartRecruiters
- Indeed (direct, not via LinkedIn)

This provides job diversity and reduces dependency on LinkedIn.
"""

import asyncio
import aiohttp
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import json
import ssl

logger = logging.getLogger(__name__)


@dataclass
class DirectJobPosting:
    """Job posting from direct ATS scrape."""
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    ats_type: str  # 'greenhouse', 'lever', 'workday', etc.
    company_url: str
    posted_date: Optional[str] = None
    employment_type: Optional[str] = None
    remote: bool = False


# Import expanded company lists
try:
    import sys
    sys.path.insert(0, '/Users/tech4/Downloads/botworkieslocsl/botworgies')
    from data.companies_greenhouse import ALL_GREENHOUSE_COMPANIES
    from data.companies_lever import ALL_LEVER_COMPANIES
    from data.companies_workday import ALL_WORKDAY_COMPANIES
except ImportError as e:
    logger.warning(f"Could not import company lists: {e}")
    ALL_GREENHOUSE_COMPANIES = []
    ALL_LEVER_COMPANIES = []
    ALL_WORKDAY_COMPANIES = []


class GreenhouseDirectScraper:
    """Scrape jobs directly from Greenhouse boards."""
    
    # Use expanded company list (200+ companies)
    COMPANIES = ALL_GREENHOUSE_COMPANIES if ALL_GREENHOUSE_COMPANIES else [
        # Fallback basic list
        'stripe', 'airbnb', 'doordash', 'instacart', 'robinhood', 'coinbase',
        'notion', 'figma', 'asana', 'monday', 'airtable',
        'mongodb', 'datadog', 'cloudflare', 'hashicorp', 'databricks',
        'vercel', 'linear', 'webflow', 'figma', 'loom',
    ]
    
    async def scrape_company(self, company: str, keywords: List[str]) -> List[DirectJobPosting]:
        """Scrape jobs from a single company's Greenhouse board."""
        jobs = []
        url = f"https://boards.greenhouse.io/{company}/jobs.json"
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=ssl_context)
            ) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return jobs
                    
                    data = await response.json()
                    
                    for job_data in data.get('jobs', []):
                        title = job_data.get('title', '').lower()
                        
                        # Filter by keywords
                        if not any(kw.lower() in title for kw in keywords):
                            continue
                        
                        job = DirectJobPosting(
                            id=f"gh_{company}_{job_data.get('id')}",
                            title=job_data.get('title', ''),
                            company=company.title(),
                            location=job_data.get('location', {}).get('name', 'Remote'),
                            url=job_data.get('absolute_url', ''),
                            description=job_data.get('content', '')[:500],
                            ats_type='greenhouse',
                            company_url=f"https://boards.greenhouse.io/{company}",
                        )
                        jobs.append(job)
                        
        except Exception as e:
            logger.debug(f"[GreenhouseDirect] {company} failed: {e}")
        
        return jobs
    
    async def search(self, keywords: List[str], max_jobs: int = 100) -> List[DirectJobPosting]:
        """Search across all Greenhouse companies."""
        logger.info(f"[GreenhouseDirect] Searching {len(self.COMPANIES)} companies...")
        
        all_jobs = []
        tasks = []
        
        for company in self.COMPANIES:
            task = self.scrape_company(company, keywords)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                all_jobs.extend(result)
        
        logger.info(f"[GreenhouseDirect] Found {len(all_jobs)} jobs")
        return all_jobs[:max_jobs]


class LeverDirectScraper:
    """Scrape jobs directly from Lever boards."""
    
    # Use expanded company list (150+ companies)
    COMPANIES = ALL_LEVER_COMPANIES if ALL_LEVER_COMPANIES else [
        # Fallback basic list
        'netlify', 'sentry', 'figma', 'notion', 'linear', 'raycast',
        'vercel', 'supabase', 'planetscale', 'render', 'fly',
        'twilio', 'segment', 'auth0', 'github',
    ]
    
    async def scrape_company(self, company: str, keywords: List[str]) -> List[DirectJobPosting]:
        """Scrape jobs from a Lever company."""
        jobs = []
        url = f"https://api.lever.co/v0/postings/{company}?mode=json"
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=ssl_context)
            ) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return jobs
                    
                    postings = await response.json()
                    
                    for posting in postings:
                        title = posting.get('text', '').lower()
                        
                        if not any(kw.lower() in title for kw in keywords):
                            continue
                        
                        job = DirectJobPosting(
                            id=f"lever_{company}_{posting.get('id')}",
                            title=posting.get('text', ''),
                            company=company.title(),
                            location=posting.get('categories', {}).get('location', 'Remote'),
                            url=posting.get('applyUrl', ''),
                            description=posting.get('description', '')[:500],
                            ats_type='lever',
                            company_url=f"https://jobs.lever.co/{company}",
                        )
                        jobs.append(job)
                        
        except Exception as e:
            logger.debug(f"[LeverDirect] {company} failed: {e}")
        
        return jobs
    
    async def search(self, keywords: List[str], max_jobs: int = 100) -> List[DirectJobPosting]:
        """Search across Lever companies."""
        logger.info(f"[LeverDirect] Searching {len(self.COMPANIES)} companies...")
        
        all_jobs = []
        tasks = [self.scrape_company(c, keywords) for c in self.COMPANIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                all_jobs.extend(result)
        
        logger.info(f"[LeverDirect] Found {len(all_jobs)} jobs")
        return all_jobs[:max_jobs]


class WorkdayDirectScraper:
    """Scrape jobs from Workday career sites."""
    
    # Use expanded company list (100+ companies)
    COMPANIES = ALL_WORKDAY_COMPANIES if ALL_WORKDAY_COMPANIES else [
        # Fallback basic list
        ('amazon', 'amazon.wd5.myworkdayjobs.com'),
        ('microsoft', 'microsoft.wd5.myworkdayjobs.com'),
        ('salesforce', 'salesforce.wd5.myworkdayjobs.com'),
        ('adobe', 'adobe.wd5.myworkdayjobs.com'),
        ('intuit', 'intuit.wd5.myworkdayjobs.com'),
        ('servicenow', 'servicenow.wd5.myworkdayjobs.com'),
    ]
    
    async def scrape_company(self, company: str, domain: str, keywords: List[str]) -> List[DirectJobPosting]:
        """Scrape jobs from a Workday site."""
        jobs = []
        
        # Workday uses a complex API - simplified version
        url = f"https://{domain}/wday/cxs/{company}/jobs"
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=ssl_context)
            ) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return jobs
                    
                    data = await response.json()
                    
                    for job_data in data.get('jobPostings', []):
                        title = job_data.get('title', '').lower()
                        
                        if not any(kw.lower() in title for kw in keywords):
                            continue
                        
                        job_id = job_data.get('bulletFields', [{}])[0].get('id', '')
                        
                        job = DirectJobPosting(
                            id=f"wd_{company}_{job_id}",
                            title=job_data.get('title', ''),
                            company=company.title(),
                            location=job_data.get('locationsText', 'Remote'),
                            url=f"https://{domain}/en-US/job/{job_id}",
                            description=job_data.get('jobDescription', '')[:500],
                            ats_type='workday',
                            company_url=f"https://{domain}",
                        )
                        jobs.append(job)
                        
        except Exception as e:
            logger.debug(f"[WorkdayDirect] {company} failed: {e}")
        
        return jobs
    
    async def search(self, keywords: List[str], max_jobs: int = 100) -> List[DirectJobPosting]:
        """Search across Workday companies."""
        logger.info(f"[WorkdayDirect] Searching {len(self.COMPANIES)} companies...")
        
        all_jobs = []
        tasks = []
        
        for company, domain in self.COMPANIES:
            task = self.scrape_company(company, domain, keywords)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                all_jobs.extend(result)
        
        logger.info(f"[WorkdayDirect] Found {len(all_jobs)} jobs")
        return all_jobs[:max_jobs]


class DirectScraperAggregator:
    """Aggregate jobs from all direct ATS sources."""
    
    def __init__(self):
        self.greenhouse = GreenhouseDirectScraper()
        self.lever = LeverDirectScraper()
        self.workday = WorkdayDirectScraper()
    
    async def search_all(
        self,
        keywords: List[str],
        max_per_source: int = 50
    ) -> List[DirectJobPosting]:
        """Search all direct ATS sources."""
        logger.info("[DirectScraper] Searching all ATS sources...")
        
        # Run all scrapers in parallel
        results = await asyncio.gather(
            self.greenhouse.search(keywords, max_per_source),
            self.lever.search(keywords, max_per_source),
            self.workday.search(keywords, max_per_source),
            return_exceptions=True
        )
        
        all_jobs = []
        for result in results:
            if isinstance(result, list):
                all_jobs.extend(result)
        
        # Remove duplicates by URL
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                unique_jobs.append(job)
        
        logger.info(f"[DirectScraper] Total unique jobs: {len(unique_jobs)}")
        return unique_jobs


# Convenience function
async def scrape_direct_jobs(
    keywords: List[str],
    max_per_source: int = 50
) -> List[DirectJobPosting]:
    """Quick function to scrape jobs from all direct ATS sources."""
    aggregator = DirectScraperAggregator()
    return await aggregator.search_all(keywords, max_per_source)
