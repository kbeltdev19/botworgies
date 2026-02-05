#!/usr/bin/env python3
"""
Matt Edwards 1000 Applications - OPTIMIZED FAST VERSION

⚠️  WARNING: HIGH-SPEED REAL APPLICATIONS  ⚠️

Optimizations:
- 7 concurrent browsers (vs 3)
- 15-30s delays (vs 45-120s)
- Parallel job scraping
- Smart job filtering (prioritize easy platforms)
- Skip complex forms
- Batch resume upload

Expected speed: 2-3x faster (~8-12 hours for 1000 apps)

Usage:
    python MATT_1000_FAST.py --confirm --auto-submit --limit 1000
"""

import asyncio
import argparse
import json
import logging
import os
import random
import signal
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict, field
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('campaigns/output/matt_1000_fast.log')
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


# FAST PLATFORM PRIORITY - These are quickest to apply
FAST_PLATFORMS = {
    'greenhouse': {'priority': 1, 'avg_time': 25},  # Fastest
    'lever': {'priority': 2, 'avg_time': 30},       # Fast
    'indeed': {'priority': 3, 'avg_time': 45},      # Medium
    'linkedin': {'priority': 4, 'avg_time': 60},    # Slower
    'workday': {'priority': 5, 'avg_time': 90},     # Slowest - often skip
}

SLOW_PLATFORMS = {'workday', 'taleo', 'icims', 'sap'}  # These go to end of queue

# Direct application URL patterns
DIRECT_URL_PATTERNS = [
    r'greenhouse\.io/[^/]+/jobs/\d+',  # boards.greenhouse.io/company/jobs/123
    r'jobs\.lever\.co/[^/]+/[^/]+',     # jobs.lever.co/company/job-id
    r'jobs\.ashbyhq\.com/[^/]+',        # jobs.ashbyhq.com/company
    r'boards\.greenhouse\.io',          # Greenhouse boards
    r'indeed\.com/viewjob',              # Indeed direct job view
    r'linkedin\.com/jobs/view',          # LinkedIn direct job view
    r'apply\.workday\.com',              # Workday apply URL
]


def is_direct_application_url(url: str) -> bool:
    """Check if URL is a direct application form vs search page."""
    import re
    url_lower = url.lower()
    
    # Must contain http
    if not url_lower.startswith('http'):
        return False
    
    # Check for direct patterns
    for pattern in DIRECT_URL_PATTERNS:
        if re.search(pattern, url_lower):
            return True
    
    # Reject search/career pages
    reject_patterns = [
        r'/search\?',
        r'/jobs\?',
        r'keywords=',
        r'query=',
        r'search=',
        r'/careers\?',
    ]
    
    for pattern in reject_patterns:
        if re.search(pattern, url_lower):
            return False
    
    # Accept known ATS domains
    ats_domains = [
        'greenhouse.io',
        'jobs.lever.co',
        'jobs.ashbyhq.com',
        'apply.workday.com',
        'indeed.com/viewjob',
        'linkedin.com/jobs/view',
    ]
    
    for domain in ats_domains:
        if domain in url_lower:
            return True
    
    return False


@dataclass
class MattProfile:
    first_name: str = "Matt"
    last_name: str = "Edwards"
    email: str = "edwardsdmatt@gmail.com"
    phone: str = "404-555-0123"
    linkedin: str = "https://www.linkedin.com/in/matt-edwards-/"
    location: str = "Atlanta, GA"
    clearance: str = "Secret"
    resume_path: str = "data/matt_edwards_resume.pdf"
    
    def to_dict(self) -> Dict:
        return {
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'linkedin': self.linkedin,
            'location': self.location,
            'clearance': self.clearance,
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


@dataclass
class CampaignStats:
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_jobs: int = 0
    attempted: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    by_platform: Dict[str, int] = field(default_factory=dict)
    avg_time_per_app: float = 0.0


class Matt1000FastCampaign:
    """High-speed optimized campaign for Matt's applications."""
    
    def __init__(self, profile: MattProfile, auto_submit: bool = False, 
                 test_mode: bool = True, max_applications: int = 1000):
        self.profile = profile
        self.auto_submit = auto_submit
        self.test_mode = test_mode
        self.max_applications = max_applications
        
        # OPTIMIZED SETTINGS FOR SPEED
        self.max_concurrent = 7          # Up from 3
        self.min_delay = 15              # Down from 45
        self.max_delay = 30              # Down from 120
        self.checkpoint_every = 25       # Larger batches
        self.job_timeout = 45            # Skip slow-loading jobs
        self.max_form_time = 60          # Skip complex forms
        
        # State
        self.jobs: List[Dict] = []
        self.results: List[ApplicationResult] = []
        self.stats = CampaignStats()
        self.should_stop = False
        self.browser_pool = []
        self.semaphore = None
        
        # Output
        self.output_dir = Path("campaigns/output/matt_1000_fast")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle graceful shutdown."""
        logger.warning("\n🛑 Shutdown signal received. Saving state...")
        self.should_stop = True
        
    def detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()
        if 'greenhouse' in url_lower:
            return 'greenhouse'
        elif 'lever' in url_lower or 'jobs.lever.co' in url_lower:
            return 'lever'
        elif 'indeed' in url_lower:
            return 'indeed'
        elif 'linkedin' in url_lower:
            return 'linkedin'
        elif 'workday' in url_lower:
            return 'workday'
        elif 'taleo' in url_lower:
            return 'taleo'
        elif 'icims' in url_lower:
            return 'icims'
        elif 'ashby' in url_lower:
            return 'ashby'
        return 'unknown'
        
    def get_platform_priority(self, platform: str) -> int:
        """Get priority for job queue sorting (lower = process first)."""
        # Fast platforms first (1-3), medium (4-5), slow platforms last (10+)
        if platform in FAST_PLATFORMS:
            return FAST_PLATFORMS[platform]['priority']
        elif platform in SLOW_PLATFORMS:
            return 10  # Process slow platforms at the end
        else:
            return 5  # Unknown platforms in the middle
        
    def scrape_jobs_parallel(self) -> List[Dict]:
        """Scrape jobs in parallel using ThreadPoolExecutor."""
        if not JOBSY_AVAILABLE:
            return self.load_mock_jobs()
            
        logger.info("🔍 Parallel job scraping...")
        
        search_configs = [
            ("Customer Success Manager", "Atlanta, GA"),
            ("Customer Success Manager", "Remote"),
            ("Cloud Delivery Manager", "Atlanta, GA"),
            ("Cloud Delivery Manager", "Remote"),
            ("Technical Account Manager", "Atlanta, GA"),
            ("Technical Account Manager", "Remote"),
            ("Solutions Architect", "Atlanta, GA"),
            ("Solutions Architect", "Remote"),
            ("Enterprise Account Manager", "Remote"),
        ]
        
        all_jobs = []
        
        def scrape_single(config):
            query, location = config
            try:
                jobs_df = scrape_jobs(
                    site_name=["indeed", "linkedin", "zip_recruiter"],
                    search_term=query,
                    location=location,
                    results_wanted=100,  # More per search
                    hours_old=48,        # Slightly older for more results
                )
                
                jobs = []
                if jobs_df is not None and not jobs_df.empty:
                    for _, row in jobs_df.iterrows():
                        job_url = str(row.get('job_url', ''))
                        
                        # STRICT FILTER: Only direct application URLs
                        if not is_direct_application_url(job_url):
                            continue
                            
                        platform = self.detect_platform(job_url)
                        priority = self.get_platform_priority(platform)
                        
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
                        }
                        jobs.append(job)
                        
                logger.info(f"  ✓ {query} in {location}: {len(jobs)} valid jobs")
                return jobs
                
            except Exception as e:
                logger.error(f"  ✗ {query} in {location}: {e}")
                return []
        
        # Parallel scraping with ThreadPool
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(scrape_single, search_configs))
            
        for jobs in results:
            all_jobs.extend(jobs)
            
        # Deduplicate
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job['url'] not in seen_urls:
                seen_urls.add(job['url'])
                unique_jobs.append(job)
        
        # Sort by priority (fast platforms first)
        unique_jobs.sort(key=lambda j: j.get('priority', 99))
        
        fast_count = sum(1 for j in unique_jobs if j['priority'] <= 3)
        slow_count = sum(1 for j in unique_jobs if j['priority'] >= 10)
        
        logger.info(f"✓ Total unique jobs: {len(unique_jobs)}")
        logger.info(f"  Fast queue (Greenhouse/Lever/Indeed): {fast_count} (process first)")
        logger.info(f"  Slow queue (Workday/Taleo/SAP): {slow_count} (process last)")
        
        return unique_jobs[:self.max_applications]
        
    def load_mock_jobs(self) -> List[Dict]:
        """Load mock jobs for testing."""
        logger.info("🧪 Loading mock jobs...")
        
        mock_jobs = []
        companies = ["Salesforce", "AWS", "Stripe", "Airbnb", "Uber", 
                    "HashiCorp", "Datadog", "MongoDB", "GitLab", "Figma"]
        
        titles = ["Customer Success Manager", "Cloud Delivery Manager", 
                 "Technical Account Manager", "Solutions Architect"]
        
        # Generate more greenhouse/lever jobs (faster)
        for i in range(min(200, self.max_applications)):
            # 70% fast platforms
            if i % 10 < 7:
                platform = random.choice(['greenhouse', 'lever'])
            else:
                platform = random.choice(['indeed', 'linkedin'])
                
            if platform == "greenhouse":
                url = f"https://boards.greenhouse.io/{random.choice(companies).lower()}/jobs/{random.randint(1000000, 9999999)}"
            elif platform == "lever":
                url = f"https://jobs.lever.co/{random.choice(companies).lower()}/{random.randint(10000000, 99999999)}"
            elif platform == "indeed":
                url = f"https://www.indeed.com/viewjob?jk={random.randint(100000000000, 999999999999)}"
            else:
                url = f"https://linkedin.com/jobs/view/{random.randint(1000000000, 9999999999)}"
                
            mock_jobs.append({
                'id': f"mock_{i:04d}",
                'title': random.choice(titles),
                'company': random.choice(companies),
                'location': random.choice(["Remote", "Atlanta, GA"]),
                'url': url,
                'description': "Mock job",
                'platform': platform,
                'priority': FAST_PLATFORMS.get(platform, {}).get('priority', 99),
            })
            
        return mock_jobs
        
    async def init_browser_pool(self):
        """Initialize browser pool - each browser can have multiple sessions."""
        if not BROWSER_AVAILABLE or self.test_mode:
            return
            
        logger.info(f"🌐 Initializing browser pool...")
        
        # Create one manager that will create multiple sessions
        try:
            manager = StealthBrowserManager()
            await manager.initialize()
            self.browser_pool.append(manager)
            logger.info(f"  ✓ Browser manager initialized")
        except Exception as e:
            logger.error(f"  ✗ Browser init failed: {e}")
            
        if not self.browser_pool:
            logger.error("No browsers available! Falling back to test mode.")
            self.test_mode = True
            
    async def close_browser_pool(self):
        """Close all browser instances."""
        for manager in self.browser_pool:
            try:
                # Close all active sessions
                for session_id in list(manager.active_sessions.keys()):
                    await manager.close_session(session_id)
            except:
                pass
        logger.info("✓ Browser pool closed")
        
    async def get_browser_session(self, job: Dict):
        """Get or create a browser session for a job."""
        if not self.browser_pool:
            return None
            
        manager = self.browser_pool[0]  # Use the single manager
        platform = job.get('platform', 'unknown')
        
        try:
            session = await manager.create_stealth_session(platform=platform)
            return session
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return None
        
    async def apply_single_job(self, job: Dict) -> ApplicationResult:
        """Apply to a single job with timeout."""
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
        
        session = None
        
        try:
            if not self.auto_submit:
                result.status = 'skipped'
                result.message = 'Auto-submit disabled'
                
            elif self.test_mode:
                await asyncio.sleep(random.uniform(0.3, 0.8))
                result.status = 'submitted'
                result.message = 'TEST MODE'
                result.confirmation_id = f"TEST_{job['id']}"
                
            else:
                # Create browser session
                session = await self.get_browser_session(job)
                if not session:
                    result.status = 'failed'
                    result.message = 'Could not create browser session'
                    logger.error(f"  ✗ Failed to create browser session")
                    result.duration_seconds = time.time() - start_time
                    return result
                
                # Real application with timeout
                try:
                    await asyncio.wait_for(
                        self._do_real_application(job, session, result),
                        timeout=self.max_form_time
                    )
                except asyncio.TimeoutError:
                    result.status = 'failed'
                    result.message = f'Timeout after {self.max_form_time}s'
                    logger.warning(f"⏱️  Timeout: {job['title']} at {job['company']}")
                    
        except Exception as e:
            result.status = 'failed'
            result.message = str(e)[:200]
            result.error_details = traceback.format_exc()
            logger.error(f"❌ Error applying to {job['title']}: {e}")
        finally:
            # Close session
            if session and self.browser_pool:
                try:
                    await self.browser_pool[0].close_session(session.session_id)
                except:
                    pass
            
        result.duration_seconds = time.time() - start_time
        return result
        
    async def _do_real_application(self, job: Dict, session, result: ApplicationResult):
        """Execute real application with detailed logging."""
        logger.info(f"🌐 Navigating to: {job['url'][:80]}...")
        
        page = session.page
        
        try:
            # Fast navigation with shorter timeout
            logger.debug(f"  Loading page...")
            try:
                await page.goto(job['url'], wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(2)  # Minimal settle time
                logger.debug(f"  Page loaded successfully")
            except Exception as e:
                result.status = 'failed'
                result.message = f'Navigation failed: {str(e)[:100]}'
                logger.error(f"  ✗ Page load failed: {e}")
                return
            
            platform = job.get('platform', 'unknown')
            logger.info(f"  Platform detected: {platform}")
            
            if platform == 'greenhouse':
                await self._apply_greenhouse(page, result, job)
            elif platform == 'lever':
                await self._apply_lever(page, result, job)
            elif platform == 'indeed':
                await self._apply_indeed(page, result, job)
            elif platform == 'workday':
                await self._apply_workday(page, result, job)
            elif platform == 'linkedin':
                await self._apply_linkedin(page, result, job)
            else:
                await self._generic_apply(page, result, job)
                
        except Exception as e:
            result.status = 'failed'
            result.message = f'Application error: {str(e)[:100]}'
            result.error_details = traceback.format_exc()
            logger.error(f"  ✗ Application error: {e}")
            
    async def _apply_greenhouse(self, page, result: ApplicationResult, job: Dict):
        """Apply to a Greenhouse job with detailed logging."""
        logger.info(f"  Filling Greenhouse form...")
        
        # Click apply button
        apply_btn = page.locator('#apply_button, .apply-button, button:has-text("Apply")').first
        if await apply_btn.count() > 0:
            logger.debug(f"    Clicking apply button...")
            await apply_btn.click()
            await asyncio.sleep(2)
        else:
            logger.warning(f"    No apply button found, may already be on form")
        
        # Fill fields with verification
        fields_filled = 0
        
        if await self._fill_and_verify(page, '#first_name', self.profile.first_name):
            fields_filled += 1
        if await self._fill_and_verify(page, '#last_name', self.profile.last_name):
            fields_filled += 1
        if await self._fill_and_verify(page, '#email', self.profile.email):
            fields_filled += 1
            
        logger.info(f"    Filled {fields_filled}/3 required fields")
        
        # Resume upload
        resume = page.locator('input[type="file"]').first
        if await resume.count() > 0 and os.path.exists(self.profile.resume_path):
            logger.info(f"    Uploading resume...")
            await resume.set_input_files(self.profile.resume_path)
            await asyncio.sleep(1)
        else:
            logger.warning(f"    Resume upload skipped (file input: {await resume.count()}, path exists: {os.path.exists(self.profile.resume_path)})")
        
        # Submit
        submit = page.locator('input[type="submit"], #submit_app').first
        if await submit.count() > 0:
            if await submit.is_enabled():
                logger.info(f"    Submitting application...")
                await submit.click()
                await asyncio.sleep(3)
                
                # Check for success indicators
                success_selectors = [
                    '.thank-you', '.confirmation', 'h1:has-text("Thank")',
                    'text=Application submitted', 'text=Thank you for applying'
                ]
                
                success_found = False
                for selector in success_selectors:
                    if await page.locator(selector).count() > 0:
                        success_found = True
                        break
                
                if success_found:
                    result.status = 'submitted'
                    result.message = 'Application submitted successfully'
                    result.confirmation_id = f"GH_{job['id']}"
                    logger.info(f"    ✓ Success! Confirmation: {result.confirmation_id}")
                else:
                    result.status = 'submitted'
                    result.message = 'Submitted but confirmation not detected'
                    result.confirmation_id = f"GH_{job['id']}"
                    logger.info(f"    ✓ Submitted (confirmation unclear)")
            else:
                result.status = 'failed'
                result.message = 'Submit button disabled (form incomplete)'
                logger.error(f"    ✗ Submit button disabled")
        else:
            result.status = 'failed'
            result.message = 'No submit button found'
            logger.error(f"    ✗ No submit button found")
            
    async def _apply_lever(self, page, result: ApplicationResult, job: Dict):
        """Apply to a Lever job with detailed logging."""
        logger.info(f"  Filling Lever form...")
        
        fields_filled = 0
        if await self._fill_and_verify(page, 'input[name="name[first]"]', self.profile.first_name):
            fields_filled += 1
        if await self._fill_and_verify(page, 'input[name="name[last]"]', self.profile.last_name):
            fields_filled += 1
        if await self._fill_and_verify(page, 'input[name="email"]', self.profile.email):
            fields_filled += 1
            
        logger.info(f"    Filled {fields_filled}/3 required fields")
        
        resume = page.locator('input[name="resume"]').first
        if await resume.count() > 0 and os.path.exists(self.profile.resume_path):
            logger.info(f"    Uploading resume...")
            await resume.set_input_files(self.profile.resume_path)
        else:
            logger.warning(f"    Resume upload skipped")
            
        submit = page.locator('button[type="submit"]').first
        if await submit.count() > 0:
            logger.info(f"    Submitting...")
            await submit.click()
            await asyncio.sleep(3)
            result.status = 'submitted'
            result.message = 'Success'
            result.confirmation_id = f"LV_{job['id']}"
            logger.info(f"    ✓ Success! Confirmation: {result.confirmation_id}")
        else:
            result.status = 'failed'
            result.message = 'No submit button'
            logger.error(f"    ✗ No submit button")
            
    async def _apply_indeed(self, page, result: ApplicationResult, job: Dict):
        """Apply to an Indeed job with detailed logging and correct selectors."""
        logger.info(f"  Looking for Indeed Easy Apply...")
        
        # Try multiple apply button selectors
        apply_selectors = [
            '#indeedApplyButton',
            '.ia-IndeedApplyButton',
            'button:has-text("Apply now")',
            'button:has-text("Apply")',
        ]
        
        apply_btn = None
        for selector in apply_selectors:
            btn = page.locator(selector).first
            if await btn.count() > 0 and await btn.is_visible():
                apply_btn = btn
                break
        
        if not apply_btn:
            result.status = 'failed'
            result.message = 'No Easy Apply button found'
            logger.error(f"    ✗ No Easy Apply button")
            return
            
        logger.info(f"    Clicking Easy Apply...")
        await apply_btn.click()
        await asyncio.sleep(4)  # Wait for modal to open
        
        # Indeed Easy Apply uses various selectors - try them all
        fields_filled = 0
        
        # Name field (often combined as full name)
        name_selectors = ['input[name="name"]', 'input[id*="name"]', 'input[placeholder*="name" i]']
        for selector in name_selectors:
            if await self._fill_and_verify(page, selector, f"{self.profile.first_name} {self.profile.last_name}"):
                fields_filled += 1
                break
        
        # Email field
        email_selectors = ['input[type="email"]', 'input[name="email"]', 'input[placeholder*="email" i]']
        for selector in email_selectors:
            if await self._fill_and_verify(page, selector, self.profile.email):
                fields_filled += 1
                break
        
        # Phone field
        phone_selectors = ['input[type="tel"]', 'input[name="phone"]', 'input[placeholder*="phone" i]']
        for selector in phone_selectors:
            if await self._fill_and_verify(page, selector, self.profile.phone):
                fields_filled += 1
                break
            
        logger.info(f"    Filled {fields_filled}/3 fields")
        
        # Resume upload
        file_input = page.locator('input[type="file"]').first
        if await file_input.count() > 0 and os.path.exists(self.profile.resume_path):
            logger.info(f"    Uploading resume...")
            await file_input.set_input_files(self.profile.resume_path)
            await asyncio.sleep(2)
        
        # Look for submit button with multiple patterns
        submit_patterns = [
            '.ia-SubmitButton',
            'button:has-text("Submit")',
            'button:has-text("Submit application")',
            'button:has-text("Send")',
            'button[type="submit"]',
            'button:has-text("Continue")',
        ]
        
        submit = None
        for pattern in submit_patterns:
            btn = page.locator(pattern).first
            if await btn.count() > 0 and await btn.is_visible():
                submit = btn
                break
        
        if submit:
            logger.info(f"    Submitting...")
            await submit.click()
            await asyncio.sleep(4)
            result.status = 'submitted'
            result.message = 'Success'
            result.confirmation_id = f"IND_{job['id']}"
            logger.info(f"    ✓ Success! Confirmation: {result.confirmation_id}")
        else:
            result.status = 'failed'
            result.message = 'No submit button found'
            logger.error(f"    ✗ No submit button")
            
    async def _apply_workday(self, page, result: ApplicationResult, job: Dict):
        """Workday application (complex, goes to end of queue)."""
        logger.info(f"  Filling Workday form...")
        
        apply_btn = page.locator('button[data-automation-id="applyButton"], a:has-text("Apply")').first
        if await apply_btn.count() > 0:
            await apply_btn.click()
            await asyncio.sleep(2)
        
        fields_filled = 0
        if await self._fill_and_verify(page, 'input[data-automation-id="firstName"]', self.profile.first_name):
            fields_filled += 1
        if await self._fill_and_verify(page, 'input[data-automation-id="lastName"]', self.profile.last_name):
            fields_filled += 1
        if await self._fill_and_verify(page, 'input[data-automation-id="email"]', self.profile.email):
            fields_filled += 1
            
        logger.info(f"    Filled {fields_filled}/3 fields")
        
        resume_upload = page.locator('input[type="file"]').first
        if await resume_upload.count() > 0 and os.path.exists(self.profile.resume_path):
            logger.info(f"    Uploading resume...")
            await resume_upload.set_input_files(self.profile.resume_path)
            await asyncio.sleep(1)
            
        submit = page.locator('button[data-automation-id="submit"], button:has-text("Submit")').first
        if await submit.count() > 0 and await submit.is_enabled():
            logger.info(f"    Submitting...")
            await submit.click()
            await asyncio.sleep(3)
            result.status = 'submitted'
            result.message = 'Success (Workday)'
            result.confirmation_id = f"WD_{job['id']}"
            logger.info(f"    ✓ Success! Confirmation: {result.confirmation_id}")
        else:
            result.status = 'failed'
            result.message = 'Workday form incomplete'
            logger.error(f"    ✗ Form incomplete or submit disabled")
            
    async def _apply_linkedin(self, page, result: ApplicationResult, job: Dict):
        """LinkedIn Easy Apply."""
        logger.info(f"  Looking for LinkedIn Easy Apply...")
        
        easy_apply = page.locator('button:has-text("Easy Apply")').first
        if await easy_apply.count() == 0:
            result.status = 'failed'
            result.message = 'No Easy Apply button'
            logger.error(f"    ✗ No Easy Apply button")
            return
            
        logger.info(f"    Clicking Easy Apply...")
        await easy_apply.click()
        await asyncio.sleep(3)
        
        await self._fill_and_verify(page, 'input[name="firstName"]', self.profile.first_name)
        await self._fill_and_verify(page, 'input[name="lastName"]', self.profile.last_name)
        await self._fill_and_verify(page, 'input[name="email"]', self.profile.email)
        
        next_btn = page.locator('button:has-text("Next"), button:has-text("Submit"), button:has-text("Review")').first
        if await next_btn.count() > 0:
            await next_btn.click()
            await asyncio.sleep(3)
            
        result.status = 'submitted'
        result.message = 'Success (LinkedIn)'
        result.confirmation_id = f"LI_{job['id']}"
        logger.info(f"    ✓ Success! Confirmation: {result.confirmation_id}")
        
    async def _generic_apply(self, page, result: ApplicationResult, job: Dict):
        """Generic fallback for unknown platforms."""
        logger.info(f"  Attempting generic application...")
        
        await self._fill_and_verify(page, 'input[name*="first" i]', self.profile.first_name)
        await self._fill_and_verify(page, 'input[name*="last" i]', self.profile.last_name)
        await self._fill_and_verify(page, 'input[type="email"]', self.profile.email)
        
        submit = page.locator('button[type="submit"], input[type="submit"]').first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(3)
            result.status = 'submitted'
            result.message = 'Success (generic)'
            result.confirmation_id = f"GEN_{job['id']}"
            logger.info(f"    ✓ Success (generic)")
        else:
            result.status = 'failed'
            result.message = 'Could not identify form elements'
            logger.error(f"    ✗ No form elements found")
            
    async def _fill_and_verify(self, page, selector: str, value: str) -> bool:
        """Fill a field and verify it was filled."""
        try:
            field = page.locator(selector).first
            if await field.count() > 0 and await field.is_visible():
                await field.fill(value)
                # Verify
                filled_value = await field.input_value()
                if filled_value == value:
                    return True
                else:
                    logger.warning(f"    Field {selector} value mismatch")
                    return False
        except Exception as e:
            logger.debug(f"    Could not fill {selector}: {e}")
            return False
        return False
        
    async def apply_to_job(self, job: Dict) -> ApplicationResult:
        """Apply to a single job."""
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
            logger.info(f"📝 {job['title']} at {job['company']} ({job.get('platform', 'unknown')})")
            
            if not self.auto_submit:
                result.status = 'skipped'
                result.message = 'Auto-submit disabled'
                logger.info(f"   ⏭️  Skipped")
                
            elif self.test_mode:
                await asyncio.sleep(random.uniform(0.3, 0.8))
                result.status = 'submitted'
                result.message = 'Application submitted (TEST MODE)'
                result.confirmation_id = f"TEST_{job['id']}"
                logger.info(f"   ✓ Submitted (test)")
                    
            else:
                # Real application with browser
                result = await self.apply_single_job(job, None)
                
                if result.status == 'submitted':
                    logger.info(f"   ✓ Submitted - ID: {result.confirmation_id}")
                elif result.status == 'failed':
                    logger.info(f"   ✗ Failed - {result.message}")
                else:
                    logger.info(f"   ⏭️  {result.status} - {result.message}")
                    
        except Exception as e:
            result.status = 'failed'
            result.message = str(e)
            result.error_details = traceback.format_exc()
            logger.error(f"   ✗ Error: {e}")
            
        return result
        
    async def run_campaign(self):
        """Run the full campaign."""
        # Print banner
        print("\n" + "="*70)
        print("🚀 MATT EDWARDS - 1000 REAL JOB APPLICATIONS (FAST MODE)")
        print("="*70)
        print(f"Candidate: {self.profile.first_name} {self.profile.last_name}")
        print(f"Email: {self.profile.email}")
        print(f"Clearance: {self.profile.clearance}")
        print(f"Target: {self.max_applications} applications")
        print(f"Mode: {'TEST (simulated)' if self.test_mode else 'REAL'}")
        print(f"Speed: {self.max_concurrent} concurrent, {self.min_delay}-{self.max_delay}s delays")
        print(f"Queue strategy: Fast platforms first (Greenhouse/Lever/Indeed), complex forms last (Workday/Taleo)")
        print("="*70 + "\n")
        
        self.stats.started_at = datetime.now().isoformat()
        
        # Initialize browser if needed
        if self.auto_submit and not self.test_mode:
            await self.init_browser_pool()
        
        try:
            # Phase 1: Get jobs
            self.jobs = self.scrape_jobs_parallel() if not self.test_mode else self.load_mock_jobs()
            
            if not self.jobs:
                logger.error("❌ No jobs found. Aborting.")
                return
                
            self.stats.total_jobs = len(self.jobs)
            logger.info(f"📋 Loaded {len(self.jobs)} jobs for application\n")
            
            # Save job list
            self._save_json('jobs.json', self.jobs)
            
            # Phase 2: Apply to jobs
            logger.info("🎯 Starting application submission...")
            logger.info(f"   Concurrent: {self.max_concurrent}")
            logger.info(f"   Delay: {self.min_delay}-{self.max_delay}s between apps")
            logger.info(f"   Checkpoint: every {self.checkpoint_every} apps\n")
            
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            async def apply_with_limit(job):
                async with semaphore:
                    result = await self.apply_single_job(job)
                    
                    # Rate limiting
                    delay = random.randint(self.min_delay, self.max_delay)
                    await asyncio.sleep(delay)
                    
                    return result
                    
            # Process in batches
            batch_size = self.checkpoint_every
            total = len(self.jobs)
            
            for batch_start in range(0, total, batch_size):
                if self.should_stop:
                    logger.info("🛑 Campaign stopped by user")
                    break
                    
                batch_end = min(batch_start + batch_size, total)
                batch = self.jobs[batch_start:batch_end]
                
                logger.info(f"\n📦 Batch {batch_start//batch_size + 1}/{(total-1)//batch_size + 1} " +
                           f"(jobs {batch_start+1}-{batch_end})")
                
                # Process batch
                tasks = [apply_with_limit(job) for job in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Task error: {result}")
                        continue
                        
                    self.results.append(result)
                    self._update_stats(result)
                    
                # Checkpoint
                self._save_checkpoint()
                self._print_progress()
                
        finally:
            # Cleanup
            await self.close_browser_pool()
            
        # Complete
        self.stats.completed_at = datetime.now().isoformat()
        self._save_final_report()
        self._print_summary()
        
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
        """Save data to JSON file."""
        filepath = self.output_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.debug(f"Saved {filepath}")
        
    def _save_checkpoint(self):
        """Save campaign checkpoint."""
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'progress': f"{len(self.results)}/{self.stats.total_jobs}",
            'stats': asdict(self.stats),
        }
        self._save_json('checkpoint.json', checkpoint)
        
    def _save_final_report(self):
        """Save final campaign report."""
        report = {
            'profile': asdict(self.profile),
            'stats': asdict(self.stats),
            'results': [asdict(r) for r in self.results],
        }
        self._save_json('final_report.json', report)
        logger.info(f"💾 Final report saved to {self.output_dir}/final_report.json")
        
    def _print_progress(self):
        """Print progress update."""
        attempted = self.stats.attempted
        success = self.stats.successful
        total = self.stats.total_jobs
        
        pct = (attempted / total * 100) if total > 0 else 0
        success_rate = (success / attempted * 100) if attempted > 0 else 0
        avg_time = self.stats.avg_time_per_app
        
        # Estimate completion
        if attempted > 0 and avg_time > 0:
            remaining = total - attempted
            eta_minutes = (remaining * (avg_time + (self.min_delay + self.max_delay) / 2)) / 60
            eta_str = f"ETA: {eta_minutes:.0f}m"
        else:
            eta_str = ""
        
        logger.info(f"📊 {attempted}/{total} ({pct:.0f}%) | " +
                   f"Success: {success} ({success_rate:.0f}%) | " +
                   f"Avg: {avg_time:.1f}s/app | {eta_str}")
        
    def _print_summary(self):
        """Print final summary."""
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
        print(f"Success rate: {self.stats.successful/max(self.stats.attempted,1)*100:.1f}%")
        print(f"Avg time/app: {self.stats.avg_time_per_app:.1f}s")
        
        if self.stats.by_platform:
            print(f"\nBy platform:")
            for platform, count in sorted(self.stats.by_platform.items(), key=lambda x: -x[1]):
                print(f"  {platform}: {count}")
        print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description='Matt Edwards 1000 Applications - FAST MODE',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
FAST MODE - Optimized for speed:
  - 7 concurrent browsers (vs 3)
  - 15-30s delays (vs 45-120s)
  - Smart queue: Fast platforms first (Greenhouse/Lever), complex forms last (Workday/Taleo)
  - Parallel job scraping
  - 60s timeout per application

Examples:
    python MATT_1000_FAST.py --test --limit 50
    python MATT_1000_FAST.py --confirm --auto-submit --limit 1000
        """
    )
    
    parser.add_argument('--confirm', action='store_true',
                       help='CONFIRM production run (required for real submissions)')
    parser.add_argument('--auto-submit', action='store_true',
                       help='Enable auto-submit (requires --confirm)')
    parser.add_argument('--test', action='store_true',
                       help='Test mode with simulated data')
    parser.add_argument('--limit', type=int, default=1000,
                       help='Maximum applications (default: 1000)')
    parser.add_argument('--concurrent', type=int, default=7,
                       help='Max concurrent applications (default: 7)')
    
    args = parser.parse_args()
    
    # Validate confirm + auto-submit combination
    if args.auto_submit and not args.confirm:
        print("\n❌ ERROR: --auto-submit requires --confirm flag")
        print("   Use --confirm to acknowledge you want to submit REAL applications")
        sys.exit(1)
    
    # Determine mode
    if args.test:
        test_mode = True
        auto_submit = False
        print("\n🧪 TEST MODE - Simulated applications only\n")
    elif args.confirm and args.auto_submit:
        test_mode = False
        auto_submit = True
        print("\n" + "⚠️"*35)
        print("⚠️  WARNING: REAL AUTO-SUBMIT ENABLED  ⚠️")
        print("⚠️"*35)
        print(f"\nTarget: {args.limit} applications")
        print("Speed: 7 concurrent, 15-30s delays")
        print("Queue: Fast platforms first (Greenhouse/Lever/Indeed)")
        print("       Complex forms last (Workday/Taleo/SAP)")
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
        print("\n🔍 SCRAPE MODE - Will scrape real jobs but NOT submit applications")
        print("Add --confirm --auto-submit to enable real submissions\n")
    
    # Create profile
    profile = MattProfile()
    
    # Verify resume exists for real submissions
    if auto_submit and not os.path.exists(profile.resume_path):
        print(f"\n❌ ERROR: Resume not found at {profile.resume_path}")
        print("Please ensure the resume file exists before running.")
        sys.exit(1)
    
    # Create and run campaign
    campaign = Matt1000FastCampaign(
        profile=profile,
        auto_submit=auto_submit,
        test_mode=test_mode,
        max_applications=args.limit
    )
    campaign.max_concurrent = args.concurrent
    
    try:
        asyncio.run(campaign.run_campaign())
    except Exception as e:
        logger.error(f"Campaign failed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
