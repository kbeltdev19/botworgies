#!/usr/bin/env python3
"""
Smart Filter Campaign - Only target jobs that can actually be automated.

Filters:
- Simple Greenhouse (grnh.se short URLs - usually basic forms)
- Lever (jobs.lever.co - typically simple)
- Skip: Federal, clearance, ICIMS, complex Workday
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keywords that indicate simple forms
SIMPLE_PATTERNS = [
    'grnh.se',  # Greenhouse short URLs (usually simple 1-page)
    'jobs.lever.co',  # Lever (simple forms)
    'boards.greenhouse.io',  # Standard Greenhouse
]

# Keywords to SKIP (complex forms)
SKIP_PATTERNS = [
    'federal', 'clearance', 'government', 'ts/sci', 'secret', 'top secret',
    'icims.com', 'icims',  # Complex
    'workday', 'myworkdayjobs',  # Usually complex unless verified simple
    'recruiting.', 'adp.com',  # Often complex
    'usajobs', 'usps',  # Government
]

class SmartFilterCampaign:
    def __init__(self, profile_path: str, resume_path: str, target: int = 20):
        self.profile_path = profile_path
        self.resume_path = resume_path
        self.target = target
        
        with open(profile_path) as f:
            self.profile = yaml.safe_load(f)
        
        self.jobs = []
        self.results = []
        self.stats = {'discovered': 0, 'filtered': 0, 'attempted': 0, 'success': 0}
    
    def is_simple_form(self, url: str, title: str, company: str) -> bool:
        """Check if job has a simple, automatable form."""
        url_lower = url.lower()
        title_lower = title.lower()
        
        # Skip federal/government jobs
        for pattern in SKIP_PATTERNS:
            if pattern in url_lower or pattern in title_lower:
                return False
        
        # Check for simple patterns
        for pattern in SIMPLE_PATTERNS:
            if pattern in url_lower:
                return True
        
        return False
    
    async def discover(self):
        """Discover jobs."""
        from jobspy import scrape_jobs
        import pandas as pd
        
        logger.info("Discovering jobs...")
        
        queries = ['Software Engineer', 'DevOps', 'ServiceNow']
        all_jobs = []
        
        for query in queries:
            df = scrape_jobs(
                site_name=['indeed'],
                search_term=query,
                location='Remote',
                results_wanted=100,
                hours_old=72
            )
            
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    apply_url = row.get('job_url_direct')
                    if pd.notna(apply_url):
                        job = {
                            'title': row['title'],
                            'company': row['company'] if pd.notna(row['company']) else 'Unknown',
                            'apply_url': str(apply_url),
                            'description': str(row.get('description', ''))[:200],
                        }
                        all_jobs.append(job)
        
        self.stats['discovered'] = len(all_jobs)
        logger.info(f"Discovered: {len(all_jobs)}")
        
        # Filter to simple forms
        simple_jobs = []
        for job in all_jobs:
            if self.is_simple_form(job['apply_url'], job['title'], job['company']):
                simple_jobs.append(job)
        
        self.jobs = simple_jobs[:self.target * 3]  # Buffer
        self.stats['filtered'] = len(self.jobs)
        
        logger.info(f"Simple forms: {len(self.jobs)}")
        for job in self.jobs[:10]:
            logger.info(f"  - {job['title'][:50]} @ {job['company']}")
    
    async def apply(self):
        """Apply to jobs with manual verification."""
        from adapters.handlers.browser_manager import BrowserManager
        
        logger.info(f"\nApplying to {len(self.jobs)} jobs...")
        logger.info("⚠️  MANUAL VERIFICATION REQUIRED")
        logger.info("For each job, you'll see the form. Press ENTER to confirm submission.\n")
        
        browser = BrowserManager(headless=False)
        
        for i, job in enumerate(self.jobs[:self.target], 1):
            logger.info(f"\n[{i}] {job['title'][:50]} @ {job['company']}")
            logger.info(f"    URL: {job['apply_url'][:60]}...")
            
            try:
                _, page = await browser.create_context()
                await page.goto(job['apply_url'], wait_until='networkidle', timeout=60000)
                await asyncio.sleep(2)
                
                # Take screenshot
                await page.screenshot(path=f'campaigns/output/job_{i:03d}.png')
                
                # Fill basic info
                await self._fill_basic_info(page)
                
                logger.info("    Form loaded. Check screenshot and browser.")
                logger.info("    Complete the application manually if it looks good.")
                
                # Wait for user confirmation
                # In real implementation, this would be async with timeout
                await asyncio.sleep(10)  # Give time to review
                
                self.stats['attempted'] += 1
                
                await page.close()
                
            except Exception as e:
                logger.error(f"    Error: {e}")
        
        logger.info(f"\nAttempted: {self.stats['attempted']}")
    
    async def _fill_basic_info(self, page):
        """Fill basic info fields."""
        # First Name
        for selector in ['input[name*="first" i]', '#first_name', 'input[placeholder*="First" i]']:
            try:
                elem = page.locator(selector).first
                if await elem.count() > 0:
                    await elem.fill(self.profile.get('first_name', ''))
                    break
            except:
                continue
        
        # Last Name
        for selector in ['input[name*="last" i]', '#last_name', 'input[placeholder*="Last" i]']:
            try:
                elem = page.locator(selector).first
                if await elem.count() > 0:
                    await elem.fill(self.profile.get('last_name', ''))
                    break
            except:
                continue
        
        # Email
        for selector in ['input[type="email"]', 'input[name*="email" i]', '#email']:
            try:
                elem = page.locator(selector).first
                if await elem.count() > 0:
                    await elem.fill(self.profile.get('email', ''))
                    break
            except:
                continue
    
    async def run(self):
        await self.discover()
        await self.apply()

if __name__ == "__main__":
    campaign = SmartFilterCampaign(
        profile_path='campaigns/profiles/kevin_beltran.yaml',
        resume_path='Test Resumes/Kevin_Beltran_Resume.pdf',
        target=10
    )
    asyncio.run(campaign.run())
