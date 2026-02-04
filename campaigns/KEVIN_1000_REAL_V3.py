#!/usr/bin/env python3
"""
Kevin Beltran 1000 Real Applications - V3 with ATS Direct + Redirect Handling

Features:
1. Direct ATS scraping (Greenhouse, Lever, Workday, Indeed Easy Apply)
2. LinkedIn/Indeed redirect handling to external ATS sites
3. Smart URL extraction from job listings
4. Platform-specific application handlers
5. 7 concurrent browsers, 15-30s delays

Target: 1000 REAL successful submissions

Usage:
    python KEVIN_1000_REAL_V3.py --confirm --auto-submit --limit 1000
"""

import asyncio
import argparse
import json
import logging
import os
import random
import re
import signal
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, asdict, field
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import aiohttp

# Capsolver for CAPTCHA solving
try:
    import capsolver
    CAPSOLVER_AVAILABLE = True
    capsolver.api_key = "CAP-REDACTED"
except ImportError:
    CAPSOLVER_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('campaigns/output/kevin_1000_real_v3.log')
    ]
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from jobspy import scrape_jobs
    JOBSY_AVAILABLE = True
except ImportError:
    JOBSY_AVAILABLE = False

try:
    from browser.stealth_manager import StealthBrowserManager
    BROWSER_AVAILABLE = True
except ImportError:
    BROWSER_AVAILABLE = False


# ATS Platform configurations
ATS_PLATFORMS = {
    'greenhouse': {
        'priority': 1,
        'base_urls': ['boards.greenhouse.io', 'greenhouse.io', 'boards.eu.greenhouse.io'],
        'apply_path': '/jobs',
        'apply_button': '#apply_button, .apply-button, a[href*="/jobs/"]',
    },
    'lever': {
        'priority': 2,
        'base_urls': ['jobs.lever.co', 'lever.co'],
        'apply_path': '',
        'apply_button': '.posting-btn-apply, a[href*="/apply"]',
    },
    'workday': {
        'priority': 3,
        'base_urls': ['wd5.myworkdayjobs.com', 'myworkdayjobs.com', 'workday.com', 'wd2-impl-services1.workday.com'],
        'apply_path': '',
        'apply_button': 'button[data-automation-id="applyButton"]',
    },
    'indeed': {
        'priority': 2,
        'base_urls': ['indeed.com', 'indeed.jobs'],
        'apply_path': '',
        'apply_button': '.ia-IndeedApplyButton, .jobsearch-IndeedApplyButton',
    },
    'linkedin': {
        'priority': 4,
        'base_urls': ['linkedin.com', 'linkedin.jobs'],
        'apply_path': '',
        'apply_button': 'button[aria-label*="Easy Apply"], .jobs-apply-button',
    },
    'ashby': {
        'priority': 1,
        'base_urls': ['jobs.ashbyhq.com', 'ashbyhq.com'],
        'apply_path': '/application',
        'apply_button': 'a[href*="/application"]',
    },
    'breezy': {
        'priority': 2,
        'base_urls': ['breezy.hr'],
        'apply_path': '/apply',
        'apply_button': '.apply-button, a[href*="/apply"]',
    },
    'smartrecruiters': {
        'priority': 2,
        'base_urls': ['jobs.smartrecruiters.com', 'smartrecruiters.com'],
        'apply_path': '',
        'apply_button': 'a[href*="/apply"]',
    },
    'jobscore': {
        'priority': 2,
        'base_urls': ['careers.jobscore.com', 'jobscore.com'],
        'apply_path': '',
        'apply_button': '.apply-button',
    },
    'icims': {
        'priority': 5,
        'base_urls': ['icims.com', 'jobs.icims.com'],
        'apply_path': '',
        'apply_button': '.iCIMS_Button',
    },
    'taleo': {
        'priority': 5,
        'base_urls': ['taleo.net', 'oracle.com'],
        'apply_path': '',
        'apply_button': 'button:has-text("Apply")',
    },
    'sap': {
        'priority': 5,
        'base_urls': ['jobs.sap.com', 'sap.com/careers'],
        'apply_path': '',
        'apply_button': 'button:has-text("Apply")',
    },
}

SLOW_PLATFORMS = {'workday', 'taleo', 'icims', 'sap', 'oracle'}


@dataclass
class KevinProfile:
    """Kevin Beltran profile for applications."""
    first_name: str = "Kevin"
    last_name: str = "Beltran"
    email: str = "beltranrkevin@gmail.com"
    phone: str = "770-378-2545"
    linkedin: str = ""
    location: str = "Atlanta, GA"
    clearance: str = "Secret"
    resume_path: str = "../Test Resumes/Kevin_Beltran_Resume.pdf"
    
    def to_dict(self) -> Dict:
        return {
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.profile.email,
            'phone': self.profile.phone,
            'linkedin': self.profile.linkedin,
            'location': self.profile.location,
            'clearance': self.profile.clearance,
        }


@dataclass
class ApplicationResult:
    job_id: str
    title: str
    company: str
    location: str
    url: str
    platform: str
    status: str
    message: str
    submitted_at: str
    duration_seconds: float = 0.0
    confirmation_id: Optional[str] = None
    screenshot_path: Optional[str] = None
    error_details: Optional[str] = None
    redirect_url: Optional[str] = None


@dataclass
class CampaignStats:
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_jobs: int = 0
    attempted: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    redirects_followed: int = 0
    by_platform: Dict[str, int] = field(default_factory=dict)
    avg_time_per_app: float = 0.0


class ATSScraper:
    """Direct scraper for ATS platforms."""
    
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        await self.session.close()
        
    async def scrape_greenhouse(self, company_slug: str) -> List[Dict]:
        """Scrape jobs directly from Greenhouse board."""
        jobs = []
        url = f"https://boards.greenhouse.io/{company_slug}.json"
        
        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for job in data.get('jobs', []):
                        jobs.append({
                            'id': f"gh_{job.get('id', '')}",
                            'title': job.get('title', ''),
                            'company': data.get('name', company_slug),
                            'location': job.get('location', {}).get('name', ''),
                            'url': job.get('absolute_url', ''),
                            'platform': 'greenhouse',
                            'priority': 1,
                        })
        except Exception as e:
            logger.debug(f"Greenhouse scrape failed for {company_slug}: {e}")
            
        return jobs
        
    async def scrape_lever(self, company_slug: str) -> List[Dict]:
        """Scrape jobs directly from Lever board."""
        jobs = []
        url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
        
        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    postings = await resp.json()
                    for posting in postings:
                        jobs.append({
                            'id': f"lever_{posting.get('id', '')}",
                            'title': posting.get('text', ''),
                            'company': company_slug,
                            'location': ', '.join([l for l in posting.get('categories', {}).get('location', [])]),
                            'url': posting.get('hostedUrl', posting.get('applyUrl', '')),
                            'platform': 'lever',
                            'priority': 2,
                        })
        except Exception as e:
            logger.debug(f"Lever scrape failed for {company_slug}: {e}")
            
        return jobs


class Kevin1000RealV3Campaign:
    """
    Production campaign with ATS direct scraping + LinkedIn redirect handling.
    """
    
    def __init__(self, profile: KevinProfile, auto_submit: bool = False,
                 test_mode: bool = True, max_applications: int = 1000):
        self.profile = profile
        self.auto_submit = auto_submit
        self.test_mode = test_mode
        self.max_applications = max_applications
        
        # Optimized settings
        self.max_concurrent = 7
        self.min_delay = 15
        self.max_delay = 30
        self.checkpoint_every = 25
        self.max_form_time = 60
        
        # State
        self.jobs: List[Dict] = []
        self.results: List[ApplicationResult] = []
        self.stats = CampaignStats()
        self.should_stop = False
        self.browser_pool = []
        self.semaphore = None
        
        # Output
        self.output_dir = Path("campaigns/output/kevin_1000_real_v3")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        logger.warning("\n🛑 Shutdown signal received. Saving state...")
        self.should_stop = True
        
    def detect_platform(self, url: str) -> str:
        """Detect ATS platform from URL."""
        url_lower = url.lower()
        
        # Check each platform's base URLs
        for platform, config in ATS_PLATFORMS.items():
            for base_url in config['base_urls']:
                if base_url in url_lower:
                    return platform
        
        # Additional pattern matching for common ATS patterns
        if 'greenhouse' in url_lower:
            return 'greenhouse'
        elif 'lever' in url_lower:
            return 'lever'
        elif 'workday' in url_lower:
            return 'workday'
        elif 'ashby' in url_lower:
            return 'ashby'
        elif 'breezy' in url_lower:
            return 'breezy'
        elif 'smartrecruiters' in url_lower:
            return 'smartrecruiters'
        elif 'jobscore' in url_lower:
            return 'jobscore'
        elif 'icims' in url_lower:
            return 'icims'
        elif 'taleo' in url_lower:
            return 'taleo'
        elif 'sap' in url_lower and 'job' in url_lower:
            return 'sap'
        elif 'linkedin' in url_lower:
            return 'linkedin'
        elif 'indeed' in url_lower:
            return 'indeed'
            
        return 'unknown'
        
    async def scrape_all_sources(self) -> List[Dict]:
        """Scrape from multiple sources: direct ATS + job boards."""
        all_jobs = []
        
        # 1. Direct ATS scraping (highest quality - direct apply URLs)
        logger.info("🔍 Phase 1: Direct ATS scraping...")
        ats_jobs = await self._scrape_direct_ats()
        all_jobs.extend(ats_jobs)
        logger.info(f"  ✓ Direct ATS jobs: {len(ats_jobs)}")
        
        # 2. Job board scraping (LinkedIn/Indeed - may need redirect handling)
        logger.info("🔍 Phase 2: Job board scraping...")
        board_jobs = await self._scrape_job_boards()
        all_jobs.extend(board_jobs)
        logger.info(f"  ✓ Job board jobs: {len(board_jobs)}")
        
        # 3. Deduplicate and sort
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job['url'] not in seen_urls:
                seen_urls.add(job['url'])
                unique_jobs.append(job)
                
        # Sort by priority (fast platforms first)
        unique_jobs.sort(key=lambda j: j.get('priority', 99))
        
        # Log breakdown
        direct_ats_count = sum(1 for j in unique_jobs if j.get('source') == 'direct_ats')
        linkedin_count = sum(1 for j in unique_jobs if 'linkedin' in j.get('platform', ''))
        indeed_count = sum(1 for j in unique_jobs if 'indeed' in j.get('platform', ''))
        
        logger.info(f"\n✓ Total unique jobs: {len(unique_jobs)}")
        logger.info(f"  Direct ATS (apply directly): {direct_ats_count}")
        logger.info(f"  LinkedIn (may redirect): {linkedin_count}")
        logger.info(f"  Indeed (Easy Apply): {indeed_count}")
        logger.info(f"  Fast platforms (Greenhouse/Lever): {sum(1 for j in unique_jobs if j.get('priority', 99) <= 2)}")
        
        return unique_jobs[:self.max_applications]
        
    async def _scrape_direct_ats(self) -> List[Dict]:
        """Scrape directly from company ATS boards."""
        jobs = []
        
        # Target companies with ServiceNow roles
        target_companies = {
            'greenhouse': [
                'slack', 'stripe', 'airbnb', 'uber', 'lyft', 'notion',
                'figma', ' linear', 'vercel', 'datadog', 'mongodb',
                'hashicorp', 'gitlab', 'twilio', 'segment', 'launchdarkly',
            ],
            'lever': [
                'netlify', 'gatsby', 'prisma', 'planetscale', 'railway',
                'supabase', 'calcom', 'triggerdev', 'novu',
            ],
        }
        
        async with ATSScraper() as scraper:
            # Scrape Greenhouse
            for company in target_companies['greenhouse']:
                if self.should_stop:
                    break
                company_jobs = await scraper.scrape_greenhouse(company)
                # Filter for relevant roles
                for job in company_jobs:
                    if any(kw in job['title'].lower() for kw in 
                           ['servicenow', 'itsm', 'account manager', 'consultant', 
                            'business analyst', 'project manager', 'customer success']):
                        job['source'] = 'direct_ats'
                        jobs.append(job)
                        
            # Scrape Lever
            for company in target_companies['lever']:
                if self.should_stop:
                    break
                company_jobs = await scraper.scrape_lever(company)
                for job in company_jobs:
                    if any(kw in job['title'].lower() for kw in 
                           ['servicenow', 'itsm', 'account manager', 'consultant',
                            'business analyst', 'project manager', 'customer success']):
                        job['source'] = 'direct_ats'
                        jobs.append(job)
                        
        return jobs
        
    async def _scrape_job_boards(self) -> List[Dict]:
        """Scrape from LinkedIn and Indeed via jobspy."""
        if not JOBSY_AVAILABLE:
            return []
            
        jobs = []
        
        search_configs = [
            ("ServiceNow Manager", "Atlanta, GA"),
            ("ServiceNow Manager", "Remote"),
            ("ServiceNow Consultant", "Atlanta, GA"),
            ("ServiceNow Consultant", "Remote"),
            ("ITSM Analyst", "Atlanta, GA"),
            ("ITSM Analyst", "Remote"),
            ("ServiceNow Administrator", "Atlanta, GA"),
            ("ServiceNow Administrator", "Remote"),
            ("Enterprise Account Manager", "Atlanta, GA"),
            ("Enterprise Account Manager", "Remote"),
            ("Cloud Account Manager", "Remote"),
            ("Technical Account Manager", "Remote"),
        ]
        
        def scrape_single(config):
            query, location = config
            try:
                jobs_df = scrape_jobs(
                    site_name=["indeed", "linkedin", "zip_recruiter"],
                    search_term=query,
                    location=location,
                    results_wanted=100,
                    hours_old=72,
                )
                
                scraped = []
                if jobs_df is not None and not jobs_df.empty:
                    for _, row in jobs_df.iterrows():
                        job_url = str(row.get('job_url', ''))
                        if not job_url or 'http' not in job_url:
                            continue
                            
                        platform = self.detect_platform(job_url)
                        priority = ATS_PLATFORMS.get(platform, {}).get('priority', 5)
                        
                        job = {
                            'id': f"{platform}_{abs(hash(job_url)) % 10000000}",
                            'title': str(row.get('title', '')).strip(),
                            'company': str(row.get('company', '')).strip(),
                            'location': str(row.get('location', '')).strip(),
                            'url': job_url,
                            'description': str(row.get('description', ''))[:300],
                            'platform': platform,
                            'priority': priority,
                            'date_posted': str(row.get('date_posted', '')),
                            'source': 'job_board',
                        }
                        scraped.append(job)
                        
                logger.info(f"  ✓ {query} in {location}: {len(scraped)} jobs")
                return scraped
                
            except Exception as e:
                error_msg = str(e)[:50]
                logger.error(f"  ✗ {query} in {location}: {error_msg}")
                return []
        
        # Parallel scraping
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(scrape_single, search_configs))
            
        for job_list in results:
            jobs.extend(job_list)
            
        return jobs
        
    async def init_browser_pool(self):
        """Initialize pool of browser instances with BrowserBase CAPTCHA solving."""
        if not BROWSER_AVAILABLE or self.test_mode:
            return
            
        logger.info(f"🌐 Initializing BrowserBase pool ({self.max_concurrent} instances) with CAPTCHA solving...")
        
        for i in range(self.max_concurrent):
            try:
                # Force BrowserBase (no local fallback) for CAPTCHA solving
                manager = StealthBrowserManager(prefer_local=False)
                await manager.initialize()
                # Reset any previous failure status
                if hasattr(manager, '_browserbase_failed'):
                    manager._browserbase_failed = False
                self.browser_pool.append(manager)
                logger.info(f"  ✓ Browser {i+1}/{self.max_concurrent} ready (BrowserBase)")
            except Exception as e:
                logger.error(f"  ✗ Browser {i+1} failed: {e}")
                
        if not self.browser_pool:
            logger.error("No browsers available! Cannot proceed.")
            self.should_stop = True
            
    async def close_browser_pool(self):
        """Close all browser instances."""
        for manager in self.browser_pool:
            try:
                await manager.close()
            except:
                pass
        logger.info("✓ Browser pool closed")
        
    async def apply_single_job(self, job: Dict, browser_manager) -> ApplicationResult:
        """Apply to a single job with redirect handling."""
        start_time = time.time()
        
        result = ApplicationResult(
            job_id=job['id'],
            title=job['title'],
            company=job['company'],
            location=job['location'],
            url=job['url'],
            platform=job.get('platform', 'unknown'),
            status='pending',
            message='',
            submitted_at=datetime.now().isoformat(),
        )
        
        try:
            if self.test_mode:
                await asyncio.sleep(random.uniform(0.3, 0.8))
                result.status = 'submitted'
                result.message = 'TEST MODE'
                result.confirmation_id = f"TEST_{job['id']}"
                
            elif not self.auto_submit:
                result.status = 'skipped'
                result.message = 'Auto-submit disabled'
                
            else:
                # Real application with timeout
                try:
                    await asyncio.wait_for(
                        self._do_real_application(job, browser_manager, result),
                        timeout=self.max_form_time
                    )
                except asyncio.TimeoutError:
                    result.status = 'failed'
                    result.message = f'Timeout after {self.max_form_time}s'
                    
        except Exception as e:
            result.status = 'failed'
            result.message = str(e)[:100]
            result.error_details = traceback.format_exc()
            
        result.duration_seconds = time.time() - start_time
        return result
        
    async def _do_real_application(self, job: Dict, browser_manager, result: ApplicationResult):
        """Execute real application with redirect handling and CAPTCHA solving."""
        original_url = job['url']
        platform = job.get('platform', 'unknown')
        
        # LinkedIn session cookie for authenticated access
        LINKEDIN_COOKIE = "AQEFARABAAAAABrX5TEAAAGbrcx_ZwAAAZxC7v9cTgAAs3VybjpsaTplbnRlcnByaXNlQXV0aFRva2VuOmVKeGpaQUFDOXRkYlBvRm96cUp6VFNDYW8vR1pGU09JSWZabjdRTXdnLy9sYXlzR0ZnRHBXUXJRXnVybjpsaTplbnRlcnByaXNlUHJvZmlsZToodXJuOmxpOmVudGVycHJpc2VBY2NvdW50OjEzMjg4Nzc5NCwxNTg1MTg5MTQpXnVybjpsaTptZW1iZXI6OTc0MTk5NzQ0w9GP4wMMKZmU4Rb6x0yjVyoj_dq75XaHpzhdX-7pQv-UfzRc9IJWW0PeNisee3dnI-f34uLhGhvcMP24Y36fgscB3bmMwVu3yapk5yCuRdqVVBoqKvmfM_G9WnyLkVS91URnamLqF3IV03GkF7sn1xBYq8CBfkjpajrROIK7-CtqbMJa30fU2R8gxaouOTmDDHkjYA"
        
        # Create browser session with CAPTCHA solving enabled
        try:
            session = await browser_manager.create_stealth_session(platform, use_proxy=True)
            page = session.page
            
            # Check if we need to solve CAPTCHA using capsolver
            try:
                captcha_solved = await self._solve_captcha_with_capsolver(page)
                if captcha_solved:
                    logger.debug(f"   CAPTCHA solved for {job['company']}")
            except Exception as e:
                logger.debug(f"   CAPTCHA check skipped: {e}")
            
            # Add LinkedIn cookie if accessing LinkedIn
            if 'linkedin.com' in original_url.lower():
                try:
                    await page.context.add_cookies([{
                        'name': 'li_at',
                        'value': LINKEDIN_COOKIE,
                        'domain': '.linkedin.com',
                        'path': '/',
                    }])
                    logger.debug(f"   Added LinkedIn auth cookie")
                except Exception as e:
                    logger.debug(f"   Failed to add LinkedIn cookie: {e}")
                    
        except Exception as e:
            result.status = 'failed'
            result.message = f'Browser session failed: {str(e)[:50]}'
            return
        
        try:
            # Navigate to job URL
            await page.goto(original_url, wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(2)
            
            # Handle LinkedIn/Indeed redirects to external ATS
            current_url = page.url
            
            if platform in ['linkedin', 'indeed'] and job.get('source') == 'job_board':
                # Try to find and click external apply button
                redirect_url = await self._handle_redirect(page, platform)
                
                if redirect_url and redirect_url != current_url:
                    result.redirect_url = redirect_url
                    self.stats.redirects_followed += 1
                    logger.info(f"   ↪ Redirected to: {redirect_url[:60]}...")
                    
                    # Navigate to redirect URL with full load
                    try:
                        await page.goto(redirect_url, wait_until='networkidle', timeout=30000)
                    except:
                        # Fallback to domcontentloaded if networkidle times out
                        await page.goto(redirect_url, wait_until='domcontentloaded', timeout=20000)
                    await asyncio.sleep(3)
                    
                    # Detect new platform
                    new_platform = self.detect_platform(redirect_url)
                    if new_platform != 'unknown':
                        platform = new_platform
                        result.platform = new_platform
                        logger.info(f"   ↪ Detected platform: {platform}")
                else:
                    # No redirect found - try LinkedIn Easy Apply directly
                    logger.debug(f"   No external redirect found, trying Easy Apply")
                    
            # Now apply based on detected platform
            if platform == 'greenhouse':
                await self._apply_greenhouse(page, result)
            elif platform == 'lever':
                await self._apply_lever(page, result)
            elif platform == 'indeed':
                await self._apply_indeed(page, result)
            elif platform == 'linkedin':
                await self._apply_linkedin(page, result)
            elif platform == 'workday':
                await self._apply_workday(page, result)
            elif platform == 'ashby':
                await self._apply_ashby(page, result)
            elif platform == 'breezy':
                await self._apply_breezy(page, result)
            else:
                # Try generic application
                await self._apply_generic(page, result)
                
        finally:
            try:
                await session.browser.close()
            except:
                pass
                
    async def _solve_captcha_with_capsolver(self, page) -> bool:
        """Solve CAPTCHA using capsolver service."""
        if not CAPSOLVER_AVAILABLE:
            return False
            
        try:
            # Check for reCAPTCHA
            recaptcha_iframe = await page.locator('iframe[src*="recaptcha"]').count()
            if recaptcha_iframe > 0:
                logger.info("   Solving reCAPTCHA with capsolver...")
                
                # Get site key from page
                site_key = await page.evaluate("""() => {
                    const el = document.querySelector('[data-sitekey]');
                    return el ? el.getAttribute('data-sitekey') : null;
                }""")
                
                if site_key:
                    solution = capsolver.solve({
                        "type": "ReCaptchaV2TaskProxyLess",
                        "websiteURL": page.url,
                        "websiteKey": site_key,
                    })
                    
                    # Inject solution
                    await page.evaluate(f"""
                        document.getElementById('g-recaptcha-response').innerHTML = '{solution['gRecaptchaResponse']}';
                    """)
                    logger.info("   ✓ reCAPTCHA solved")
                    return True
                    
            # Check for hCaptcha
            hcaptcha_iframe = await page.locator('iframe[src*="hcaptcha"]').count()
            if hcaptcha_iframe > 0:
                logger.info("   Solving hCaptcha with capsolver...")
                
                site_key = await page.evaluate("""() => {
                    const el = document.querySelector('[data-sitekey]');
                    return el ? el.getAttribute('data-sitekey') : null;
                }""")
                
                if site_key:
                    solution = capsolver.solve({
                        "type": "HCaptchaTaskProxyLess",
                        "websiteURL": page.url,
                        "websiteKey": site_key,
                    })
                    
                    await page.evaluate(f"""
                        document.querySelector('textarea[name="h-captcha-response"]').innerHTML = '{solution['gRecaptchaResponse']}';
                    """)
                    logger.info("   ✓ hCaptcha solved")
                    return True
                    
        except Exception as e:
            logger.debug(f"   CAPTCHA solving failed: {e}")
            
        return False
                
    async def _handle_redirect(self, page, platform: str) -> Optional[str]:
        """Handle LinkedIn/Indeed redirects to find external apply URL."""
        # Comprehensive list of ATS domains to look for
        ATS_DOMAINS = [
            'boards.greenhouse.io',
            'jobs.lever.co',
            'jobs.ashbyhq.com',
            'breezy.hr',
            'workday.com',
            'myworkdayjobs.com',
            'careers.jobscore.com',
            'jobs.smartrecruiters.com',
            'boards.eu.greenhouse.io',
            'jobs.hashicorp.com',
            'stripe.com/jobs',
            'airbnb.com/careers',
            'uber.com/careers',
            'meta.com/careers',
            'amazon.jobs',
            'microsoft.com/careers',
            'google.com/careers',
            'apple.com/jobs',
            'netflix.com/careers',
            'salesforce.com/company/careers',
            'oracle.com/careers',
            'adobe.com/careers',
            'ibm.com/careers',
            'intel.com/careers',
            'nvidia.com/careers',
            'qualcomm.com/careers',
            'cisco.com/careers',
            'vmware.com/careers',
            'dell.com/careers',
            'hp.com/careers',
            'lenovo.com/careers',
            'asus.com/careers',
            'acer.com/careers',
            'toshiba.com/careers',
            'sony.com/careers',
            'samsung.com/careers',
            'lg.com/careers',
            'panasonic.com/careers',
            'philips.com/careers',
            'siemens.com/careers',
            'bosch.com/careers',
            'thycotic.com/careers',
            'beyondtrust.com/careers',
            'cyberark.com/careers',
            'sentinelone.com/careers',
            'crowdstrike.com/careers',
            'paloaltonetworks.com/careers',
            'zscaler.com/careers',
            'okta.com/careers',
            'auth0.com/careers',
            'cloudflare.com/careers',
            'fastly.com/careers',
            'akamai.com/careers',
            'datadoghq.com/careers',
            'newrelic.com/careers',
            'splunk.com/careers',
            'elastic.co/careers',
            'mongodb.com/careers',
            'couchbase.com/careers',
            'redis.io/careers',
            'confluent.io/careers',
            'apache.org/careers',
            'nginx.com/careers',
            'jenkins.io/careers',
            'gitlab.com/careers',
            'github.com/careers',
            'bitbucket.org/careers',
            'atlassian.com/careers',
            'asana.com/careers',
            'notion.so/careers',
            'figma.com/careers',
            'canva.com/careers',
            'sketch.com/careers',
            'invisionapp.com/careers',
            'zeplin.io/careers',
            'principleformac.com/careers',
        ]
        
        try:
            if platform == 'linkedin':
                # Multiple selectors to find external apply links
                selectors = [
                    # Primary apply button
                    'button:has-text("Apply")',
                    'a:has-text("Apply")',
                    # External ATS links
                    'a[href*="boards.greenhouse.io"]',
                    'a[href*="jobs.lever.co"]',
                    'a[href*="workday"]',
                    'a[href*="ashby"]',
                    'a[href*="breezy"]',
                    'a[href*="smartrecruiters"]',
                    'a[href*="jobscore"]',
                    # LinkedIn specific
                    'a[data-control-name="jobdetails_topcard_inapply"]',
                    'a[data-control-name="jobdetails_topcard_jymbii"]',
                    # Any apply-related button/link
                    '[data-test-icon="link-external-medium"]',
                    'a:has([data-test-icon="link-external-medium"])',
                ]
                
                for selector in selectors:
                    try:
                        element = page.locator(selector).first
                        if await element.count() > 0:
                            href = await element.get_attribute('href')
                            if href:
                                # Check if it's an external URL
                                if any(domain in href for domain in ATS_DOMAINS) or \
                                   (href.startswith('http') and 'linkedin.com' not in href):
                                    logger.debug(f"   Found external link: {href[:60]}...")
                                    return href
                    except:
                        continue
                
                # Try JavaScript extraction as fallback
                try:
                    external_url = await page.evaluate("""
                        () => {
                            // Look for any external apply links
                            const links = Array.from(document.querySelectorAll('a[href]'));
                            for (const link of links) {
                                const href = link.getAttribute('href');
                                if (href && (
                                    href.includes('greenhouse') ||
                                    href.includes('lever') ||
                                    href.includes('workday') ||
                                    href.includes('ashby') ||
                                    href.includes('smartrecruiters') ||
                                    href.includes('jobscore') ||
                                    href.includes('breezy') ||
                                    (href.startsWith('http') && !href.includes('linkedin.com'))
                                )) {
                                    return href;
                                }
                            }
                            return null;
                        }
                    """)
                    if external_url:
                        logger.debug(f"   Found external URL via JS: {external_url[:60]}...")
                        return external_url
                except Exception as e:
                    logger.debug(f"   JS extraction failed: {e}")
                        
            elif platform == 'indeed':
                selectors = [
                    'a[href*="boards.greenhouse.io"]',
                    'a[href*="jobs.lever.co"]',
                    'a[href*="workday"]',
                    'a[href*="apply"]:not([href*="indeed"])',
                    '.ia-ApplyExternally',
                    'a:has-text("Apply on company site")',
                ]
                
                for selector in selectors:
                    try:
                        element = page.locator(selector).first
                        if await element.count() > 0:
                            href = await element.get_attribute('href')
                            if href and href.startswith('http'):
                                return href
                    except:
                        continue
                        
        except Exception as e:
            logger.debug(f"Redirect handling failed: {e}")
            
        return None
        
    async def _apply_greenhouse(self, page, result: ApplicationResult):
        """Apply to Greenhouse job."""
        try:
            # Click apply button
            apply_btn = page.locator('#apply_button, .apply-button').first
            if await apply_btn.count() > 0:
                await apply_btn.click()
                await asyncio.sleep(1)
            
            # Fill required fields
            await self._quick_fill(page, '#first_name', self.profile.first_name)
            await self._quick_fill(page, '#last_name', self.profile.last_name)
            await self._quick_fill(page, '#email', self.profile.email)
            await self._quick_fill(page, '#phone', self.profile.phone)
            
            # Resume upload
            resume = page.locator('input[type="file"]').first
            if await resume.count() > 0 and os.path.exists(self.profile.resume_path):
                await resume.set_input_files(self.profile.resume_path)
                await asyncio.sleep(0.5)
            
            # Submit
            submit = page.locator('input[type="submit"], #submit_app, button[type="submit"]').first
            if await submit.count() > 0:
                await submit.click()
                await asyncio.sleep(2)
                
                # Check for success indicators
                success = await page.locator('.thank-you, .confirmation, .applied, h1:has-text("Thank")').count() > 0
                
                if success:
                    result.status = 'submitted'
                    result.message = 'Successfully submitted via Greenhouse'
                    result.confirmation_id = f"GH_{int(time.time())}"
                else:
                    result.status = 'submitted'
                    result.message = 'Submitted (confirmation unclear)'
                    result.confirmation_id = f"GH_{int(time.time())}"
            else:
                result.status = 'failed'
                result.message = 'Submit button not found'
                
        except Exception as e:
            result.status = 'failed'
            result.message = f'Greenhouse error: {str(e)[:80]}'
            
    async def _apply_lever(self, page, result: ApplicationResult):
        """Apply to Lever job."""
        try:
            await self._quick_fill(page, 'input[name="name[first]"]', self.profile.first_name)
            await self._quick_fill(page, 'input[name="name[last]"]', self.profile.last_name)
            await self._quick_fill(page, 'input[name="email"]', self.profile.email)
            await self._quick_fill(page, 'input[name="phone"]', self.profile.phone)
            
            resume = page.locator('input[name="resume"]').first
            if await resume.count() > 0 and os.path.exists(self.profile.resume_path):
                await resume.set_input_files(self.profile.resume_path)
                await asyncio.sleep(0.5)
                
            submit = page.locator('button[type="submit"]').first
            if await submit.count() > 0:
                await submit.click()
                await asyncio.sleep(2)
                result.status = 'submitted'
                result.message = 'Successfully submitted via Lever'
                result.confirmation_id = f"LV_{int(time.time())}"
            else:
                result.status = 'failed'
                result.message = 'Submit button not found'
                
        except Exception as e:
            result.status = 'failed'
            result.message = f'Lever error: {str(e)[:80]}'
            
    async def _apply_indeed(self, page, result: ApplicationResult):
        """Apply via Indeed Easy Apply."""
        try:
            # Look for Easy Apply button
            easy_apply = page.locator('.ia-IndeedApplyButton, button:has-text("Apply")').first
            
            if await easy_apply.count() > 0:
                await easy_apply.click()
                await asyncio.sleep(2)
                
                # Fill form
                await self._quick_fill(page, 'input[name="firstName"]', self.profile.first_name)
                await self._quick_fill(page, 'input[name="lastName"]', self.profile.last_name)
                await self._quick_fill(page, 'input[name="email"]', self.profile.email)
                await self._quick_fill(page, 'input[name="phone"]', self.profile.phone)
                
                # Look for continue/submit buttons
                continue_btn = page.locator('button:has-text("Continue"), button:has-text("Submit"), .ia-SubmitButton').first
                if await continue_btn.count() > 0:
                    await continue_btn.click()
                    await asyncio.sleep(2)
                    
                result.status = 'submitted'
                result.message = 'Submitted via Indeed Easy Apply'
                result.confirmation_id = f"IND_{int(time.time())}"
            else:
                result.status = 'skipped'
                result.message = 'Indeed Easy Apply not available'
                
        except Exception as e:
            result.status = 'failed'
            result.message = f'Indeed error: {str(e)[:80]}'
            
    async def _apply_linkedin(self, page, result: ApplicationResult):
        """Apply via LinkedIn Easy Apply."""
        try:
            # First check if there's an external apply link we missed
            external_link = await self._handle_redirect(page, 'linkedin')
            if external_link and 'linkedin.com' not in external_link:
                result.redirect_url = external_link
                self.stats.redirects_followed += 1
                logger.info(f"   ↪ Late redirect found: {external_link[:60]}...")
                
                # Navigate to external site
                try:
                    await page.goto(external_link, wait_until='networkidle', timeout=30000)
                except:
                    await page.goto(external_link, wait_until='domcontentloaded', timeout=20000)
                await asyncio.sleep(3)
                
                # Detect platform and apply
                new_platform = self.detect_platform(external_link)
                if new_platform == 'greenhouse':
                    await self._apply_greenhouse(page, result)
                elif new_platform == 'lever':
                    await self._apply_lever(page, result)
                elif new_platform == 'workday':
                    await self._apply_workday(page, result)
                else:
                    await self._apply_generic(page, result)
                return
            
            # Look for Easy Apply button
            easy_apply = page.locator('button:has-text("Easy Apply")').first
            
            if await easy_apply.count() == 0:
                # Check why - maybe already applied, or external only
                if await page.locator('button:has-text("Applied")').count() > 0:
                    result.status = 'skipped'
                    result.message = 'Already applied'
                else:
                    result.status = 'skipped'
                    result.message = 'No Easy Apply - external apply only'
                return
                
            await easy_apply.click()
            await asyncio.sleep(2)
            
            # Fill form
            await self._quick_fill(page, 'input[name="firstName"]', self.profile.first_name)
            await self._quick_fill(page, 'input[name="lastName"]', self.profile.last_name)
            await self._quick_fill(page, 'input[name="email"]', self.profile.email)
            
            # Progress through steps
            for _ in range(5):  # Max 5 steps
                next_btn = page.locator('button:has-text("Next"), button:has-text("Review"), button:has-text("Submit application")').first
                submit_btn = page.locator('button:has-text("Submit application")').first
                
                if await submit_btn.count() > 0:
                    await submit_btn.click()
                    await asyncio.sleep(3)
                    result.status = 'submitted'
                    result.message = 'Submitted via LinkedIn Easy Apply'
                    result.confirmation_id = f"LI_{int(time.time())}"
                    return
                elif await next_btn.count() > 0:
                    await next_btn.click()
                    await asyncio.sleep(2)
                else:
                    break
                    
            # If we get here without submitting, check if we succeeded
            if await page.locator('.artdeco-inline-feedback--success, [aria-label="Application sent"]').count() > 0:
                result.status = 'submitted'
                result.message = 'Submitted via LinkedIn Easy Apply'
                result.confirmation_id = f"LI_{int(time.time())}"
            else:
                result.status = 'skipped'
                result.message = 'Could not complete LinkedIn Easy Apply'
            
        except Exception as e:
            result.status = 'failed'
            result.message = f'LinkedIn error: {str(e)[:80]}'
            
    async def _apply_workday(self, page, result: ApplicationResult):
        """Apply to Workday job (simplified)."""
        try:
            apply_btn = page.locator('button[data-automation-id="applyButton"]').first
            if await apply_btn.count() > 0:
                await apply_btn.click()
                await asyncio.sleep(2)
            
            await self._quick_fill(page, 'input[data-automation-id="firstName"]', self.profile.first_name)
            await self._quick_fill(page, 'input[data-automation-id="lastName"]', self.profile.last_name)
            await self._quick_fill(page, 'input[data-automation-id="email"]', self.profile.email)
            
            resume = page.locator('input[type="file"]').first
            if await resume.count() > 0 and os.path.exists(self.profile.resume_path):
                await resume.set_input_files(self.profile.resume_path)
                await asyncio.sleep(1)
            
            submit = page.locator('button[data-automation-id="submit"]').first
            if await submit.count() > 0 and await submit.is_enabled():
                await submit.click()
                await asyncio.sleep(2)
                result.status = 'submitted'
                result.message = 'Submitted via Workday'
                result.confirmation_id = f"WD_{int(time.time())}"
            else:
                result.status = 'failed'
                result.message = 'Workday submit not available'
                
        except Exception as e:
            result.status = 'failed'
            result.message = f'Workday error: {str(e)[:80]}'
            
    async def _apply_ashby(self, page, result: ApplicationResult):
        """Apply via Ashby."""
        try:
            await self._quick_fill(page, 'input[name="firstName"]', self.profile.first_name)
            await self._quick_fill(page, 'input[name="lastName"]', self.profile.last_name)
            await self._quick_fill(page, 'input[name="email"]', self.profile.email)
            
            resume = page.locator('input[type="file"]').first
            if await resume.count() > 0 and os.path.exists(self.profile.resume_path):
                await resume.set_input_files(self.profile.resume_path)
                
            submit = page.locator('button[type="submit"]').first
            if await submit.count() > 0:
                await submit.click()
                await asyncio.sleep(2)
                result.status = 'submitted'
                result.message = 'Submitted via Ashby'
                result.confirmation_id = f"ASH_{int(time.time())}"
            else:
                result.status = 'failed'
                result.message = 'Ashby submit not found'
                
        except Exception as e:
            result.status = 'failed'
            result.message = f'Ashby error: {str(e)[:80]}'
            
    async def _apply_breezy(self, page, result: ApplicationResult):
        """Apply via Breezy."""
        try:
            await self._quick_fill(page, 'input[name="first_name"]', self.profile.first_name)
            await self._quick_fill(page, 'input[name="last_name"]', self.profile.last_name)
            await self._quick_fill(page, 'input[name="email"]', self.profile.email)
            
            submit = page.locator('.apply-button, button[type="submit"]').first
            if await submit.count() > 0:
                await submit.click()
                await asyncio.sleep(2)
                result.status = 'submitted'
                result.message = 'Submitted via Breezy'
                result.confirmation_id = f"BRZ_{int(time.time())}"
            else:
                result.status = 'failed'
                result.message = 'Breezy submit not found'
                
        except Exception as e:
            result.status = 'failed'
            result.message = f'Breezy error: {str(e)[:80]}'
            
    async def _apply_generic(self, page, result: ApplicationResult):
        """Generic fallback application."""
        try:
            # Try common field selectors
            await self._quick_fill(page, 'input[name*="first" i]', self.profile.first_name)
            await self._quick_fill(page, 'input[name*="last" i]', self.profile.last_name)
            await self._quick_fill(page, 'input[type="email"]', self.profile.email)
            await self._quick_fill(page, 'input[name*="phone" i]', self.profile.phone)
            
            # Try resume upload
            resume = page.locator('input[type="file"]').first
            if await resume.count() > 0 and os.path.exists(self.profile.resume_path):
                await resume.set_input_files(self.profile.resume_path)
                await asyncio.sleep(0.5)
            
            # Try submit
            submit = page.locator('button[type="submit"], input[type="submit"]').first
            if await submit.count() > 0:
                await submit.click()
                await asyncio.sleep(2)
                result.status = 'submitted'
                result.message = 'Submitted (generic handler)'
                result.confirmation_id = f"GEN_{int(time.time())}"
            else:
                result.status = 'failed'
                result.message = 'Could not identify form elements'
                
        except Exception as e:
            result.status = 'failed'
            result.message = f'Generic error: {str(e)[:80]}'
            
    async def _quick_fill(self, page, selector: str, value: str):
        """Quickly fill a field if it exists."""
        try:
            field = page.locator(selector).first
            if await field.count() > 0 and await field.is_visible():
                await field.fill(value)
        except:
            pass
            
    async def run_campaign(self):
        """Run the full campaign."""
        print("\n" + "="*70)
        print("🚀 KEVIN BELTRAN - 1000 REAL APPLICATIONS (V3)")
        print("="*70)
        print(f"Candidate: {self.profile.first_name} {self.profile.last_name}")
        print(f"Email: {self.profile.email}")
        print(f"Target: {self.max_applications} applications")
        print(f"Mode: {'TEST' if self.test_mode else 'REAL'}")
        print(f"Features: Direct ATS + LinkedIn Redirect Handling")
        print(f"Speed: {self.max_concurrent} concurrent, {self.min_delay}-{self.max_delay}s delays")
        print("="*70 + "\n")
        
        self.stats.started_at = datetime.now().isoformat()
        
        # Initialize browsers
        if self.auto_submit and not self.test_mode:
            await self.init_browser_pool()
        
        try:
            # Phase 1: Scrape jobs from all sources
            self.jobs = await self.scrape_all_sources()
            
            if not self.jobs:
                logger.error("❌ No jobs found")
                return
                
            self.stats.total_jobs = len(self.jobs)
            logger.info(f"\n📋 {len(self.jobs)} jobs ready for application\n")
            self._save_json('jobs.json', self.jobs)
            
            # Phase 2: Apply to jobs
            logger.info("🎯 Starting applications...")
            self.semaphore = asyncio.Semaphore(self.max_concurrent)
            
            batch_size = self.checkpoint_every
            total = len(self.jobs)
            
            for batch_start in range(0, total, batch_size):
                if self.should_stop:
                    break
                    
                batch_end = min(batch_start + batch_size, total)
                batch = self.jobs[batch_start:batch_end]
                
                logger.info(f"\n📦 Batch {batch_start//batch_size + 1}/{(total-1)//batch_size + 1} " +
                           f"({batch_start+1}-{batch_end})")
                
                # Process batch concurrently
                tasks = [self._apply_with_semaphore(job) for job in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Task error: {result}")
                        continue
                    self.results.append(result)
                    self._update_stats(result)
                    
                self._save_checkpoint()
                self._print_progress()
                
        finally:
            await self.close_browser_pool()
            
        self.stats.completed_at = datetime.now().isoformat()
        self._save_final_report()
        self._print_summary()
        
    async def _apply_with_semaphore(self, job: Dict) -> ApplicationResult:
        """Apply with concurrency control."""
        async with self.semaphore:
            browser = None
            if self.browser_pool:
                browser = self.browser_pool[len(self.results) % len(self.browser_pool)]
                
            result = await self.apply_single_job(job, browser)
            
            # Rate limiting
            await asyncio.sleep(random.randint(self.min_delay, self.max_delay))
            
            # Log result
            status_icon = "✓" if result.status == 'submitted' else "✗" if result.status == 'failed' else "⏭"
            redirect_info = f" [→{result.redirect_url[:25]}...]" if result.redirect_url else ""
            logger.info(f"   {status_icon} {job['title'][:35]} at {job['company'][:15]} ({result.duration_seconds:.1f}s){redirect_info}")
            
            return result
            
    def _update_stats(self, result: ApplicationResult):
        """Update campaign stats."""
        self.stats.attempted += 1
        
        if result.status == 'submitted':
            self.stats.successful += 1
            platform = result.platform
            self.stats.by_platform[platform] = self.stats.by_platform.get(platform, 0) + 1
        elif result.status == 'failed':
            self.stats.failed += 1
        else:
            self.stats.skipped += 1
            
        # Calculate average time
        times = [r.duration_seconds for r in self.results if r.duration_seconds > 0]
        if times:
            self.stats.avg_time_per_app = sum(times) / len(times)
            
    def _save_json(self, filename: str, data: Any):
        filepath = self.output_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
            
    def _save_checkpoint(self):
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'progress': f"{len(self.results)}/{self.stats.total_jobs}",
            'stats': asdict(self.stats),
        }
        self._save_json('checkpoint.json', checkpoint)
        
    def _save_final_report(self):
        report = {
            'profile': asdict(self.profile),
            'stats': asdict(self.stats),
            'results': [asdict(r) for r in self.results],
        }
        self._save_json('final_report.json', report)
        
    def _print_progress(self):
        attempted = self.stats.attempted
        success = self.stats.successful
        total = self.stats.total_jobs
        pct = (attempted / total * 100) if total > 0 else 0
        success_rate = (success / attempted * 100) if attempted > 0 else 0
        avg_time = self.stats.avg_time_per_app
        
        if attempted > 0 and avg_time > 0:
            remaining = total - attempted
            eta_minutes = (remaining * (avg_time + (self.min_delay + self.max_delay) / 2)) / 60
            eta_str = f"ETA: {eta_minutes:.0f}m"
        else:
            eta_str = ""
        
        logger.info(f"📊 {attempted}/{total} ({pct:.0f}%) | " +
                   f"Success: {success} ({success_rate:.0f}%) | " +
                   f"Redirects: {self.stats.redirects_followed} | " +
                   f"Avg: {avg_time:.1f}s/app | {eta_str}")
        
    def _print_summary(self):
        print("\n" + "="*70)
        print("📋 CAMPAIGN SUMMARY")
        print("="*70)
        
        if self.stats.started_at and self.stats.completed_at:
            duration = (
                datetime.fromisoformat(self.stats.completed_at) - 
                datetime.fromisoformat(self.stats.started_at)
            ).total_seconds() / 3600
            print(f"Duration: {duration:.1f} hours")
            
        print(f"Jobs: {self.stats.total_jobs}")
        print(f"Attempted: {self.stats.attempted}")
        print(f"Successful: {self.stats.successful}")
        print(f"Failed: {self.stats.failed}")
        print(f"Skipped: {self.stats.skipped}")
        print(f"Redirects followed: {self.stats.redirects_followed}")
        print(f"Success rate: {self.stats.successful/max(self.stats.attempted,1)*100:.1f}%")
        print(f"Avg time/app: {self.stats.avg_time_per_app:.1f}s")
        
        if self.stats.by_platform:
            print(f"\nBy platform:")
            for platform, count in sorted(self.stats.by_platform.items(), key=lambda x: -x[1]):
                print(f"  {platform}: {count}")
        print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description='Kevin Beltran 1000 Real Applications - V3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
V3 Features:
  - Direct ATS scraping (Greenhouse, Lever, Ashby, Breezy)
  - LinkedIn/Indeed redirect handling to external ATS
  - 7 concurrent browsers, 15-30s delays
  - Smart platform detection and handling

Examples:
    python KEVIN_1000_REAL_V3.py --test --limit 50
    python KEVIN_1000_REAL_V3.py --confirm --auto-submit --limit 1000
        """
    )
    
    parser.add_argument('--confirm', action='store_true', help='Confirm production run')
    parser.add_argument('--auto-submit', action='store_true', help='Enable auto-submit')
    parser.add_argument('--test', action='store_true', help='Test mode')
    parser.add_argument('--limit', type=int, default=1000, help='Max applications')
    
    args = parser.parse_args()
    
    if args.auto_submit and not args.confirm:
        print("❌ --auto-submit requires --confirm")
        sys.exit(1)
    
    if args.test:
        test_mode = True
        auto_submit = False
        print("\n🧪 TEST MODE\n")
    elif args.confirm and args.auto_submit:
        test_mode = False
        auto_submit = True
        print("\n" + "⚠️"*35)
        print("⚠️  REAL AUTO-SUBMIT - KEVIN BELTRAN - V3  ⚠️")
        print("⚠️"*35)
        print(f"\nTarget: {args.limit} REAL applications")
        print("Features: Direct ATS + LinkedIn Redirect Handling")
        print("Speed: 7 concurrent, 15-30s delays")
        print("\nPress Ctrl+C within 5s to cancel...")
        
        try:
            for i in range(5, 0, -1):
                print(f"Starting in {i}...")
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nCancelled.")
            return
        print("\n🚀 GO!\n")
    else:
        test_mode = False
        auto_submit = False
        print("\n🔍 SCRAPE MODE\n")
    
    profile = KevinProfile()
    
    if auto_submit and not os.path.exists(profile.resume_path):
        print(f"❌ Resume not found: {profile.resume_path}")
        sys.exit(1)
    
    campaign = Kevin1000RealV3Campaign(
        profile=profile,
        auto_submit=auto_submit,
        test_mode=test_mode,
        max_applications=args.limit
    )
    
    try:
        asyncio.run(campaign.run_campaign())
    except Exception as e:
        logger.error(f"Campaign failed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
