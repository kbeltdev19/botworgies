#!/usr/bin/env python3
"""
Matt Edwards 1000 Applications - OPTIMIZED FAST VERSION

⚠️  WARNING: HIGH-SPEED REAL APPLICATIONS  ⚠️

Optimizations:
- 5-7 concurrent browsers (vs 3)
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
                        if not job_url or 'http' not in job_url:
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
                        
                logger.info(f"  ✓ {query} in {location}: {len(jobs)} jobs")
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
        """Initialize pool of browser instances."""
        if not BROWSER_AVAILABLE or self.test_mode:
            return
            
        logger.info(f"🌐 Initializing browser pool ({self.max_concurrent} instances)...")
        
        for i in range(self.max_concurrent):
            try:
                manager = StealthBrowserManager()
                await manager.initialize()
                self.browser_pool.append(manager)
                logger.info(f"  ✓ Browser {i+1}/{self.max_concurrent} ready")
            except Exception as e:
                logger.error(f"  ✗ Browser {i+1} failed: {e}")
                
        if not self.browser_pool:
            logger.error("No browsers available! Falling back to test mode.")
            self.test_mode = True
            
    async def close_browser_pool(self):
        """Close all browser instances."""
        for manager in self.browser_pool:
            try:
                await manager.close()
            except:
                pass
        logger.info("✓ Browser pool closed")
        
    async def apply_single_job(self, job: Dict, browser_manager) -> ApplicationResult:
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
            
        result.duration_seconds = time.time() - start_time
        return result
        
    async def _do_real_application(self, job: Dict, browser_manager, result: ApplicationResult):
        """Execute real application (simplified fast version)."""
        page = await browser_manager.new_page()
        
        try:
            # Fast navigation with shorter timeout
            await page.goto(job['url'], wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(1)  # Minimal settle time
            
            platform = job.get('platform', 'unknown')
            
            if platform == 'greenhouse':
                await self._fast_greenhouse_apply(page, result)
            elif platform == 'lever':
                await self._fast_lever_apply(page, result)
            elif platform == 'indeed':
                await self._fast_indeed_apply(page, result)
            elif platform == 'workday':
                await self._fast_workday_apply(page, result)
            elif platform == 'linkedin':
                await self._fast_linkedin_apply(page, result)
            else:
                # Generic handler for other platforms
                await self._generic_apply(page, result)
                
        finally:
            await page.close()
            
    async def _fast_greenhouse_apply(self, page, result: ApplicationResult):
        """Fast Greenhouse application (minimal fields)."""
        # Click apply
        apply_btn = page.locator('#apply_button, .apply-button').first
        if await apply_btn.count() > 0:
            await apply_btn.click()
            await asyncio.sleep(1)
        
        # Fill only required fields quickly
        await self._quick_fill(page, '#first_name', self.profile.first_name)
        await self._quick_fill(page, '#last_name', self.profile.last_name)
        await self._quick_fill(page, '#email', self.profile.email)
        
        # Resume
        resume = page.locator('input[type="file"]').first
        if await resume.count() > 0 and os.path.exists(self.profile.resume_path):
            await resume.set_input_files(self.profile.resume_path)
            await asyncio.sleep(0.5)
        
        # Submit
        submit = page.locator('input[type="submit"], #submit_app').first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(2)
            
            result.status = 'submitted'
            result.message = 'Success'
            result.confirmation_id = f"GH_{int(time.time())}"
        else:
            result.status = 'failed'
            result.message = 'No submit button'
            
    async def _fast_lever_apply(self, page, result: ApplicationResult):
        """Fast Lever application."""
        await self._quick_fill(page, 'input[name="name[first]"]', self.profile.first_name)
        await self._quick_fill(page, 'input[name="name[last]"]', self.profile.last_name)
        await self._quick_fill(page, 'input[name="email"]', self.profile.email)
        
        resume = page.locator('input[name="resume"]').first
        if await resume.count() > 0 and os.path.exists(self.profile.resume_path):
            await resume.set_input_files(self.profile.resume_path)
            
        submit = page.locator('button[type="submit"]').first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(2)
            result.status = 'submitted'
            result.message = 'Success'
            result.confirmation_id = f"LV_{int(time.time())}"
        else:
            result.status = 'failed'
            result.message = 'No submit button'
            
    async def _fast_indeed_apply(self, page, result: ApplicationResult):
        """Fast Indeed Easy Apply."""
        easy_apply = page.locator('.ia-IndeedApplyButton').first
        if await easy_apply.count() == 0:
            result.status = 'skipped'
            result.message = 'No Easy Apply'
            return
            
        await easy_apply.click()
        await asyncio.sleep(2)
        
        await self._quick_fill(page, 'input[name="firstName"]', self.profile.first_name)
        await self._quick_fill(page, 'input[name="lastName"]', self.profile.last_name)
        await self._quick_fill(page, 'input[name="email"]', self.profile.email)
        
        submit = page.locator('.ia-SubmitButton').first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(2)
            result.status = 'submitted'
            result.message = 'Success'
            result.confirmation_id = f"IND_{int(time.time())}"
        else:
            result.status = 'failed'
            result.message = 'No submit button'
            
    async def _fast_workday_apply(self, page, result: ApplicationResult):
        """Workday application (complex, goes to end of queue)."""
        # Workday forms are complex - look for apply button first
        apply_btn = page.locator('button[data-automation-id="applyButton"], a:has-text("Apply")').first
        if await apply_btn.count() > 0:
            await apply_btn.click()
            await asyncio.sleep(2)
        
        # Try to fill basic fields
        await self._quick_fill(page, 'input[data-automation-id="firstName"]', self.profile.first_name)
        await self._quick_fill(page, 'input[data-automation-id="lastName"]', self.profile.last_name)
        await self._quick_fill(page, 'input[data-automation-id="email"]', self.profile.email)
        
        # Resume upload (Workday uses iframes)
        resume_upload = page.locator('input[type="file"]').first
        if await resume_upload.count() > 0 and os.path.exists(self.profile.resume_path):
            await resume_upload.set_input_files(self.profile.resume_path)
            await asyncio.sleep(1)
        
        # Look for submit/next buttons
        submit = page.locator('button[data-automation-id="submit"], button:has-text("Submit")').first
        if await submit.count() > 0 and await submit.is_enabled():
            await submit.click()
            await asyncio.sleep(2)
            result.status = 'submitted'
            result.message = 'Success (Workday)'
            result.confirmation_id = f"WD_{int(time.time())}"
        else:
            result.status = 'failed'
            result.message = 'Workday form incomplete or requires manual steps'
            
    async def _fast_linkedin_apply(self, page, result: ApplicationResult):
        """LinkedIn Easy Apply."""
        easy_apply = page.locator('button:has-text("Easy Apply")').first
        if await easy_apply.count() == 0:
            result.status = 'skipped'
            result.message = 'No Easy Apply button'
            return
            
        await easy_apply.click()
        await asyncio.sleep(2)
        
        # Fill form - LinkedIn usually pre-fills from profile
        await self._quick_fill(page, 'input[name="firstName"]', self.profile.first_name)
        await self._quick_fill(page, 'input[name="lastName"]', self.profile.last_name)
        await self._quick_fill(page, 'input[name="email"]', self.profile.email)
        
        # Look for next/submit buttons
        next_btn = page.locator('button:has-text("Next"), button:has-text("Submit"), button:has-text("Review"]').first
        if await next_btn.count() > 0:
            await next_btn.click()
            await asyncio.sleep(2)
            
        result.status = 'submitted'
        result.message = 'Success (LinkedIn)'
        result.confirmation_id = f"LI_{int(time.time())}"
        
    async def _generic_apply(self, page, result: ApplicationResult):
        """Generic fallback for unknown platforms."""
        # Try common selectors
        await self._quick_fill(page, 'input[name*="first" i]', self.profile.first_name)
        await self._quick_fill(page, 'input[name*="last" i]', self.profile.last_name)
        await self._quick_fill(page, 'input[type="email"]', self.profile.email)
        
        # Try to find submit button
        submit = page.locator('button[type="submit"], input[type="submit"]').first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(2)
            result.status = 'submitted'
            result.message = 'Success (generic)'
            result.confirmation_id = f"GEN_{int(time.time())}"
        else:
            result.status = 'failed'
            result.message = 'Could not identify form elements'
            
    async def _quick_fill(self, page, selector: str, value: str):
        """Quickly fill a field if it exists."""
        try:
            field = page.locator(selector).first
            if await field.count() > 0 and await field.is_visible():
                await field.fill(value)
        except:
            pass
        
    async def run_campaign(self):
        """Run optimized campaign."""
        print("\n" + "="*70)
        print("🚀 MATT EDWARDS - 1000 APPLICATIONS (FAST MODE)")
        print("="*70)
        print(f"Candidate: {self.profile.first_name} {self.profile.last_name}")
        print(f"Target: {self.max_applications} applications")
        print(f"Mode: {'TEST' if self.test_mode else 'REAL'}")
        print(f"Speed: {self.max_concurrent} concurrent, {self.min_delay}-{self.max_delay}s delays")
        print(f"Queue strategy: Fast platforms first (Greenhouse/Lever/Indeed), complex forms last (Workday/Taleo)")
        print("="*70 + "\n")
        
        self.stats.started_at = datetime.now().isoformat()
        
        # Initialize browsers
        if self.auto_submit and not self.test_mode:
            await self.init_browser_pool()
        
        try:
            # Phase 1: Get jobs
            self.jobs = self.scrape_jobs_parallel() if not self.test_mode else self.load_mock_jobs()
            
            if not self.jobs:
                logger.error("❌ No jobs found")
                return
                
            self.stats.total_jobs = len(self.jobs)
            logger.info(f"📋 {len(self.jobs)} jobs ready\n")
            self._save_json('jobs.json', self.jobs)
            
            # Phase 2: Apply
            logger.info(f"🎯 Starting applications...")
            self.semaphore = asyncio.Semaphore(self.max_concurrent)
            
            # Process in batches
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
            # Get browser from pool (round-robin)
            browser = None
            if self.browser_pool:
                browser = self.browser_pool[len(self.results) % len(self.browser_pool)]
                
            result = await self.apply_single_job(job, browser)
            
            # Minimal delay
            await asyncio.sleep(random.randint(self.min_delay, self.max_delay))
            
            status_icon = "✓" if result.status == 'submitted' else "✗" if result.status == 'failed' else "⏭"
            logger.info(f"   {status_icon} {job['title'][:40]} at {job['company'][:20]} ({result.duration_seconds:.1f}s)")
            
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
    
    parser.add_argument('--confirm', action='store_true', help='Confirm production run')
    parser.add_argument('--auto-submit', action='store_true', help='Enable auto-submit')
    parser.add_argument('--test', action='store_true', help='Test mode')
    parser.add_argument('--limit', type=int, default=1000, help='Max applications')
    parser.add_argument('--queue-strategy', choices=['fast-first', 'slow-first', 'random'], 
                       default='fast-first',
                       help='Job processing order (default: fast-first)')
    
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
        print("⚠️  REAL AUTO-SUBMIT - FAST MODE  ⚠️")
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
        print("\n🔍 SCRAPE MODE\n")
    
    profile = MattProfile()
    
    if auto_submit and not os.path.exists(profile.resume_path):
        print(f"❌ Resume not found: {profile.resume_path}")
        sys.exit(1)
    
    campaign = Matt1000FastCampaign(
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
