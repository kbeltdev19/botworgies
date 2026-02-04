#!/usr/bin/env python3
"""
BrowserBase Scraper - Uses BrowserBase for JavaScript-heavy job sites.

This scraper uses BrowserBase to scrape jobs from sites that:
- Use JavaScript to render job listings
- Have anti-bot protections
- Require browser interaction
"""

import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging
from datetime import datetime

from . import BaseJobBoardScraper, JobPosting, SearchCriteria

logger = logging.getLogger(__name__)


@dataclass
class ScrapingConfig:
    """Configuration for scraping a specific site."""
    name: str
    url_template: str
    job_selector: str
    title_selector: str
    company_selector: Optional[str] = None
    location_selector: Optional[str] = None
    link_selector: Optional[str] = None
    next_page_selector: Optional[str] = None
    use_proxy: bool = True


class BrowserBaseScraper(BaseJobBoardScraper):
    """
    Scraper using BrowserBase for browser-based job extraction.
    
    Supports sites that require JavaScript or have bot protection.
    """
    
    def __init__(self, browser_manager=None):
        super().__init__()
        self.name = "browserbase"
        self.browser_manager = browser_manager
        self._owns_manager = browser_manager is None
        
        # Site configurations
        self.configs = {
            'linkedin': ScrapingConfig(
                name='linkedin',
                url_template='https://www.linkedin.com/jobs/search?keywords={query}&location={location}',
                job_selector='.jobs-search__results-list li',
                title_selector='.base-search-card__title',
                company_selector='.base-search-card__subtitle',
                location_selector='.job-search-card__location',
                link_selector='a.base-card__full-link',
                use_proxy=True
            ),
            'indeed': ScrapingConfig(
                name='indeed',
                url_template='https://www.indeed.com/jobs?q={query}&l={location}',
                job_selector='[data-testid="jobTitle"]',
                title_selector='[data-testid="jobTitle"]',
                company_selector='[data-testid="company-name"]',
                location_selector='[data-testid="job-location"]',
                link_selector='a.jcs-JobTitle',
                use_proxy=True
            ),
        }
    
    def get_default_headers(self) -> Dict[str, str]:
        return {"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"}
    
    async def __aenter__(self):
        if self._owns_manager:
            from browser.stealth_manager import StealthBrowserManager
            self.browser_manager = StealthBrowserManager(prefer_local=False)
            await self.browser_manager.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._owns_manager and self.browser_manager:
            await self.browser_manager.close()
    
    async def search(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Search for jobs using BrowserBase."""
        if not self.browser_manager:
            logger.error("Browser manager not available")
            return []
        
        all_jobs = []
        seen_urls = set()
        
        # Try LinkedIn
        linkedin_jobs = await self._scrape_linkedin(criteria)
        for job in linkedin_jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                all_jobs.append(job)
        
        # Try Indeed
        indeed_jobs = await self._scrape_indeed(criteria)
        for job in indeed_jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                all_jobs.append(job)
        
        logger.info(f"[BrowserBase] Total unique jobs: {len(all_jobs)}")
        return all_jobs[:criteria.max_results]
    
    async def _scrape_linkedin(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Scrape LinkedIn jobs using BrowserBase."""
        config = self.configs['linkedin']
        jobs = []
        
        try:
            # Create browser session
            session = await self.browser_manager.create_stealth_session(
                'linkedin',
                use_proxy=config.use_proxy
            )
            page = session.page
            
            # Navigate to search URL
            search_url = config.url_template.format(
                query=criteria.query.replace(' ', '%20'),
                location=criteria.location.replace(' ', '%20')
            )
            
            logger.info(f"[BrowserBase] Scraping LinkedIn: {search_url}")
            await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)  # Wait for JS to render
            
            # Scroll to load more jobs
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
            
            # Extract jobs
            job_elements = await page.locator(config.job_selector).all()
            logger.info(f"[BrowserBase] Found {len(job_elements)} LinkedIn job elements")
            
            for i, element in enumerate(job_elements[:criteria.max_results]):
                try:
                    job = await self._parse_linkedin_job(element, criteria)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.debug(f"Failed to parse LinkedIn job {i}: {e}")
            
            logger.info(f"[BrowserBase] LinkedIn: {len(jobs)} jobs")
            
        except Exception as e:
            logger.warning(f"[BrowserBase] LinkedIn scraping failed: {e}")
        
        return jobs
    
    async def _parse_linkedin_job(self, element, criteria) -> Optional[JobPosting]:
        """Parse a LinkedIn job element."""
        try:
            title_elem = element.locator('.base-search-card__title').first
            title = await title_elem.text_content() if await title_elem.count() > 0 else ''
            
            company_elem = element.locator('.base-search-card__subtitle').first
            company = await company_elem.text_content() if await company_elem.count() > 0 else ''
            
            location_elem = element.locator('.job-search-card__location').first
            location = await location_elem.text_content() if await location_elem.count() > 0 else ''
            
            link_elem = element.locator('a.base-card__full-link').first
            url = await link_elem.get_attribute('href') if await link_elem.count() > 0 else ''
            
            if not title or not url:
                return None
            
            return JobPosting(
                id=f"linkedin_{abs(hash(url)) % 10000000}",
                title=title.strip(),
                company=company.strip() if company else 'Unknown',
                location=location.strip() if location else criteria.location,
                description='',  # Would need to visit job page
                url=url,
                source='linkedin',
                posted_date=datetime.now(),
                remote='remote' in location.lower(),
                easy_apply=False,
            )
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None
    
    async def _scrape_indeed(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Scrape Indeed jobs using BrowserBase."""
        config = self.configs['indeed']
        jobs = []
        
        try:
            session = await self.browser_manager.create_stealth_session(
                'indeed',
                use_proxy=config.use_proxy
            )
            page = session.page
            
            search_url = config.url_template.format(
                query=criteria.query.replace(' ', '+'),
                location=criteria.location.replace(' ', '+')
            )
            
            logger.info(f"[BrowserBase] Scraping Indeed: {search_url}")
            await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)
            
            # Extract jobs
            job_cards = await page.locator('[data-testid="jobTitle"]').all()
            logger.info(f"[BrowserBase] Found {len(job_cards)} Indeed job cards")
            
            for i, card in enumerate(job_cards[:criteria.max_results]):
                try:
                    # Get parent container
                    parent = card.locator('..').first
                    
                    title = await card.text_content() or ''
                    
                    company_elem = parent.locator('[data-testid="company-name"]').first
                    company = await company_elem.text_content() if await company_elem.count() > 0 else ''
                    
                    location_elem = parent.locator('[data-testid="job-location"]').first
                    location = await location_elem.text_content() if await location_elem.count() > 0 else ''
                    
                    link_elem = parent.locator('a').first
                    url = await link_elem.get_attribute('href') if await link_elem.count() > 0 else ''
                    
                    if not title:
                        continue
                    
                    jobs.append(JobPosting(
                        id=f"indeed_{abs(hash(url or title)) % 10000000}",
                        title=title.strip(),
                        company=company.strip() if company else 'Unknown',
                        location=location.strip() if location else criteria.location,
                        description='',
                        url=url if url.startswith('http') else f"https://indeed.com{url}",
                        source='indeed',
                        posted_date=datetime.now(),
                        remote='remote' in location.lower(),
                        easy_apply=True,
                    ))
                except Exception as e:
                    logger.debug(f"Failed to parse Indeed job {i}: {e}")
            
            logger.info(f"[BrowserBase] Indeed: {len(jobs)} jobs")
            
        except Exception as e:
            logger.warning(f"[BrowserBase] Indeed scraping failed: {e}")
        
        return jobs
    
    async def search_parallel(
        self,
        queries: List[str],
        locations: List[str],
        total_target: int = 1000
    ) -> List[JobPosting]:
        """Search multiple queries/locations in parallel using BrowserBase."""
        all_jobs = []
        seen_urls = set()
        
        for query in queries:
            if len(all_jobs) >= total_target:
                break
            
            for location in locations:
                if len(all_jobs) >= total_target:
                    break
                
                criteria = SearchCriteria(
                    query=query,
                    location=location,
                    max_results=(total_target - len(all_jobs)) // len(locations) + 10
                )
                
                try:
                    jobs = await self.search(criteria)
                    for job in jobs:
                        if job.url not in seen_urls:
                            seen_urls.add(job.url)
                            all_jobs.append(job)
                    
                    logger.info(f"[BrowserBase] Progress: {len(all_jobs)}/{total_target}")
                    
                except Exception as e:
                    logger.warning(f"[BrowserBase] Search failed for {query} in {location}: {e}")
                
                # Rate limiting between searches
                await asyncio.sleep(2)
        
        return all_jobs[:total_target]
    
    def get_ats_type(self, url: str) -> Optional[str]:
        """Detect ATS from URL."""
        url_lower = url.lower()
        if 'linkedin.com' in url_lower:
            return 'linkedin'
        elif 'indeed.com' in url_lower:
            return 'indeed'
        return None


# Convenience function
async def scrape_with_browserbase(
    queries: List[str],
    locations: List[str],
    total_target: int = 1000,
    browser_manager=None
) -> List[JobPosting]:
    """
    Scrape jobs using BrowserBase.
    
    Args:
        queries: Job titles to search
        locations: Locations
        total_target: Total jobs needed
        browser_manager: Optional existing browser manager
        
    Returns:
        List of JobPosting objects
    """
    if browser_manager:
        scraper = BrowserBaseScraper(browser_manager)
        return await scraper.search_parallel(queries, locations, total_target)
    else:
        async with BrowserBaseScraper() as scraper:
            return await scraper.search_parallel(queries, locations, total_target)
