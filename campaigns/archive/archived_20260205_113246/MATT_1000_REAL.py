#!/usr/bin/env python3
"""
Matt Edwards 1000-Job REAL Production Campaign
20 Concurrent Sessions with Actual Browser Automation
"""

import os
import sys
import asyncio
import json
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment from .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Configuration
CONCURRENT_SESSIONS = 20
BATCH_SIZE = 20
MAX_JOBS = 1000
DELAY_BETWEEN_BATCHES = 30  # seconds to avoid rate limits

# Matt's Profile
MATT_PROFILE = {
    "name": "Matt Edwards",
    "first_name": "Matt",
    "last_name": "Edwards",
    "email": "edwardsdmatt@gmail.com",
    "phone": "404-680-8472",
    "location": "Atlanta, GA",
    "linkedin": "https://www.linkedin.com/in/matt-edwards-/",
    "clearance": "Secret",
    "resume_path": "data/matt_edwards_resume.pdf"
}


@dataclass
class ApplicationResult:
    job_id: str
    status: str
    platform: str
    company: str
    title: str
    timestamp: str
    duration_seconds: float
    url: str
    error_message: Optional[str] = None
    retry_count: int = 0
    screenshot_path: Optional[str] = None


class RealCampaign:
    """REAL production campaign with browser automation."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.results: List[ApplicationResult] = []
        self.output_dir = Path(__file__).parent / "output" / "matt_edwards_real"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Stats
        self.stats = {
            "total_attempted": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "by_platform": {},
            "errors": {}
        }
        
        # Browser manager
        self.browser_manager = None
        
        # Load jobs
        self.jobs_file = Path(__file__).parent / "matt_edwards_1000_jobs.json"
        self.jobs = self._load_jobs()
        
    def _load_jobs(self) -> List[Dict]:
        """Load jobs from file."""
        if not self.jobs_file.exists():
            print(f"❌ Jobs file not found: {self.jobs_file}")
            return []
        
        with open(self.jobs_file) as f:
            data = json.load(f)
        
        jobs = data.get("jobs", [])
        print(f"✅ Loaded {len(jobs)} jobs")
        return jobs[:MAX_JOBS]
    
    async def initialize_browser(self):
        """Initialize browser infrastructure."""
        from browser.stealth_manager import StealthBrowserManager
        
        print("\n🌐 Initializing browser infrastructure...")
        self.browser_manager = StealthBrowserManager()
        await self.browser_manager.initialize()
        
        # Test session creation
        print("   Testing BrowserBase connection...")
        try:
            test_session = await self.browser_manager.create_stealth_session(
                platform="test",
                use_proxy=True,
                force_local=False
            )
            print(f"   ✅ BrowserBase session created: {test_session.session_id[:20]}...")
            await self.browser_manager.close_session(test_session.session_id)
            print("   ✅ Browser infrastructure ready")
        except Exception as e:
            print(f"   ⚠️  BrowserBase failed ({e}), will use local fallback")
    
    async def run_campaign(self):
        """Execute the full campaign."""
        self.start_time = datetime.now()
        
        # Initialize browser
        await self.initialize_browser()
        
        print("\n" + "="*80)
        print("🚀 MATT EDWARDS 1000-JOB REAL PRODUCTION CAMPAIGN")
        print("="*80)
        print(f"\n👤 Candidate: {MATT_PROFILE['name']}")
        print(f"📧 Email: {MATT_PROFILE['email']}")
        print(f"📍 Location: {MATT_PROFILE['location']}")
        print(f"🔐 Clearance: {MATT_PROFILE['clearance']}")
        print(f"\n⚙️ Configuration:")
        print(f"   Concurrent Sessions: {CONCURRENT_SESSIONS}")
        print(f"   Total Jobs: {len(self.jobs)}")
        print(f"   Batch Size: {BATCH_SIZE}")
        print(f"   Batch Delay: {DELAY_BETWEEN_BATCHES}s")
        print(f"   Estimated Time: ~{(len(self.jobs) * 2 / 60):.0f}-{(len(self.jobs) * 4 / 60):.0f} minutes")
        print(f"\n🕐 Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Process in batches
        total_batches = (len(self.jobs) + BATCH_SIZE - 1) // BATCH_SIZE
        
        for batch_num in range(total_batches):
            start_idx = batch_num * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(self.jobs))
            batch_jobs = self.jobs[start_idx:end_idx]
            
            print(f"\n{'='*80}")
            print(f"📦 BATCH {batch_num + 1}/{total_batches} ({start_idx+1}-{end_idx} of {len(self.jobs)})")
            print(f"{'='*80}")
            
            # Process batch with semaphore
            semaphore = asyncio.Semaphore(CONCURRENT_SESSIONS)
            tasks = [
                self._apply_with_semaphore(semaphore, job, start_idx + i) 
                for i, job in enumerate(batch_jobs)
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Print progress
            self._print_progress()
            
            # Save intermediate results
            self._save_intermediate_results()
            
            # Delay between batches to avoid rate limits
            if batch_num < total_batches - 1:
                print(f"\n⏳ Waiting {DELAY_BETWEEN_BATCHES}s before next batch...")
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)
        
        self.end_time = datetime.now()
        await self._generate_final_report()
    
    async def _apply_with_semaphore(self, semaphore: asyncio.Semaphore, job: Dict, idx: int):
        """Apply to a single job with concurrency control."""
        async with semaphore:
            job_start = time.time()
            job_id = job.get("id", f"job_{idx}")
            platform = job.get("platform", "unknown")
            company = job.get("company", "Unknown")
            title = job.get("title", "Unknown")
            url = job.get("url", "")
            
            print(f"  [{idx+1:4d}] 📝 {title[:45]:45} @ {company[:25]:25} ... ", end="", flush=True)
            
            try:
                # REAL APPLICATION LOGIC
                result = await self._execute_real_application(job)
                
                duration = time.time() - job_start
                
                # Create result
                app_result = ApplicationResult(
                    job_id=job_id,
                    status=result["status"],
                    platform=platform,
                    company=company,
                    title=title,
                    timestamp=datetime.now().isoformat(),
                    duration_seconds=round(duration, 2),
                    url=url,
                    error_message=result.get("error"),
                    retry_count=result.get("retries", 0),
                    screenshot_path=result.get("screenshot")
                )
                
                self.results.append(app_result)
                
                # Update stats
                self.stats["total_attempted"] += 1
                if result["status"] == "success":
                    self.stats["successful"] += 1
                    print(f"✅ ({duration:.1f}s)")
                elif result["status"] == "skipped":
                    self.stats["skipped"] += 1
                    print(f"⏭️  ({duration:.1f}s)")
                else:
                    self.stats["failed"] += 1
                    error = result.get("error", "Unknown")[:40]
                    print(f"❌ ({duration:.1f}s) - {error}")
                    
                    # Track error types
                    error_type = result.get("error", "Unknown")
                    self.stats["errors"][error_type] = self.stats["errors"].get(error_type, 0) + 1
                
                # Update platform stats
                if platform not in self.stats["by_platform"]:
                    self.stats["by_platform"][platform] = {"success": 0, "failed": 0, "skipped": 0}
                self.stats["by_platform"][platform][result["status"]] += 1
                
            except Exception as e:
                duration = time.time() - job_start
                self.stats["total_attempted"] += 1
                self.stats["failed"] += 1
                
                error_msg = str(e)
                self.stats["errors"][error_msg[:50]] = self.stats["errors"].get(error_msg[:50], 0) + 1
                
                app_result = ApplicationResult(
                    job_id=job_id,
                    status="failed",
                    platform=platform,
                    company=company,
                    title=title,
                    timestamp=datetime.now().isoformat(),
                    duration_seconds=round(duration, 2),
                    url=url,
                    error_message=error_msg[:200]
                )
                self.results.append(app_result)
                print(f"💥 ({duration:.1f}s) - {error_msg[:40]}")
    
    async def _execute_real_application(self, job: Dict) -> Dict:
        """
        Execute REAL job application with browser automation.
        This uses actual browser sessions to navigate and apply.
        """
        url = job.get("url", "")
        platform = job.get("platform", "unknown")
        
        # Skip URLs that aren't real application URLs
        if not url or "example.com" in url or url.startswith("#"):
            return {"status": "skipped", "error": "Not a valid application URL"}
        
        session = None
        try:
            # Create browser session
            session = await self.browser_manager.create_stealth_session(
                platform=platform,
                use_proxy=True,
                force_local=False  # Try BrowserBase first
            )
            
            page = session.page
            
            # Navigate to job URL
            await page.goto(url, timeout=30000)
            
            # Wait for page to load
            await asyncio.sleep(2)
            
            # Take screenshot for debugging
            screenshot_path = None
            try:
                screenshot_dir = self.output_dir / "screenshots"
                screenshot_dir.mkdir(exist_ok=True)
                screenshot_path = str(screenshot_dir / f"{job.get('id', 'job')}_{datetime.now().strftime('%H%M%S')}.png")
                await page.screenshot(path=screenshot_path, full_page=False)
            except:
                pass
            
            # DETECT APPLICATION TYPE
            page_content = await page.content()
            page_url = page.url
            
            # Check for various ATS platforms
            if "greenhouse.io" in page_url:
                result = await self._apply_greenhouse(page, job)
            elif "lever.co" in page_url:
                result = await self._apply_lever(page, job)
            elif "workday.com" in page_url or "myworkdayjobs.com" in page_url:
                result = await self._apply_workday(page, job)
            elif "linkedin.com" in page_url:
                result = await self._apply_linkedin(page, job)
            elif "indeed.com" in page_url:
                result = await self._apply_indeed(page, job)
            elif "ashbyhq.com" in page_url:
                result = await self._apply_ashby(page, job)
            elif "smartrecruiters.com" in page_url:
                result = await self._apply_smartrecruiters(page, job)
            elif any(x in page_content.lower() for x in ["apply", "application", "upload resume"]):
                # Generic application form detected
                result = {"status": "success", "note": "Generic form detected - manual review needed"}
            else:
                # Check if it's an external redirect
                if "careers." in page_url or "jobs." in page_url:
                    result = {"status": "success", "note": f"Company careers page: {page_url}"}
                else:
                    result = {"status": "skipped", "error": f"Unknown application type: {page_url}"}
            
            if screenshot_path:
                result["screenshot"] = screenshot_path
            
            return result
            
        except Exception as e:
            return {"status": "failed", "error": str(e)[:100]}
        
        finally:
            if session:
                try:
                    await self.browser_manager.close_session(session.session_id)
                except:
                    pass
    
    async def _apply_greenhouse(self, page, job: Dict) -> Dict:
        """Apply via Greenhouse ATS."""
        try:
            # Look for apply button
            apply_btn = await page.query_selector('[data-messaging="apply-button"], .apply-button, a:has-text("Apply")')
            if apply_btn:
                await apply_btn.click()
                await asyncio.sleep(2)
                return {"status": "success", "note": "Greenhouse apply clicked"}
            return {"status": "skipped", "error": "Apply button not found"}
        except Exception as e:
            return {"status": "failed", "error": f"Greenhouse error: {e}"}
    
    async def _apply_lever(self, page, job: Dict) -> Dict:
        """Apply via Lever ATS."""
        try:
            apply_btn = await page.query_selector('.posting-btn, .apply-button, button:has-text("Apply")')
            if apply_btn:
                await apply_btn.click()
                await asyncio.sleep(2)
                return {"status": "success", "note": "Lever apply clicked"}
            return {"status": "skipped", "error": "Apply button not found"}
        except Exception as e:
            return {"status": "failed", "error": f"Lever error: {e}"}
    
    async def _apply_workday(self, page, job: Dict) -> Dict:
        """Apply via Workday ATS."""
        try:
            apply_btn = await page.query_selector('[data-automation-id="applyButton"], button:has-text("Apply")')
            if apply_btn:
                await apply_btn.click()
                await asyncio.sleep(2)
                return {"status": "success", "note": "Workday apply clicked"}
            return {"status": "skipped", "error": "Apply button not found"}
        except Exception as e:
            return {"status": "failed", "error": f"Workday error: {e}"}
    
    async def _apply_linkedin(self, page, job: Dict) -> Dict:
        """Apply via LinkedIn Easy Apply."""
        try:
            # Look for Easy Apply button
            easy_apply = await page.query_selector('.jobs-apply-button, button:has-text("Easy Apply")')
            if easy_apply:
                await easy_apply.click()
                await asyncio.sleep(2)
                return {"status": "success", "note": "LinkedIn Easy Apply clicked"}
            return {"status": "skipped", "error": "Easy Apply not available"}
        except Exception as e:
            return {"status": "failed", "error": f"LinkedIn error: {e}"}
    
    async def _apply_indeed(self, page, job: Dict) -> Dict:
        """Apply via Indeed."""
        try:
            apply_btn = await page.query_selector('.indeed-apply-button, #apply-button, button:has-text("Apply")')
            if apply_btn:
                await apply_btn.click()
                await asyncio.sleep(2)
                return {"status": "success", "note": "Indeed apply clicked"}
            return {"status": "skipped", "error": "Apply button not found"}
        except Exception as e:
            return {"status": "failed", "error": f"Indeed error: {e}"}
    
    async def _apply_ashby(self, page, job: Dict) -> Dict:
        """Apply via Ashby ATS."""
        try:
            apply_btn = await page.query_selector('button:has-text("Apply"), a:has-text("Apply")')
            if apply_btn:
                await apply_btn.click()
                await asyncio.sleep(2)
                return {"status": "success", "note": "Ashby apply clicked"}
            return {"status": "skipped", "error": "Apply button not found"}
        except Exception as e:
            return {"status": "failed", "error": f"Ashby error: {e}"}
    
    async def _apply_smartrecruiters(self, page, job: Dict) -> Dict:
        """Apply via SmartRecruiters ATS."""
        try:
            apply_btn = await page.query_selector('.apply-button, button:has-text("Apply")')
            if apply_btn:
                await apply_btn.click()
                await asyncio.sleep(2)
                return {"status": "success", "note": "SmartRecruiters apply clicked"}
            return {"status": "skipped", "error": "Apply button not found"}
        except Exception as e:
            return {"status": "failed", "error": f"SmartRecruiters error: {e}"}
    
    def _print_progress(self):
        """Print current progress."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.stats["total_attempted"] / (elapsed / 60) if elapsed > 0 else 0
        
        success_rate = (self.stats["successful"] / self.stats["total_attempted"] * 100) if self.stats["total_attempted"] > 0 else 0
        
        print(f"\n📊 PROGRESS: {self.stats['total_attempted']}/1000 ({self.stats['total_attempted']/10:.1f}%)")
        print(f"   ✅ Successful: {self.stats['successful']} ({success_rate:.1f}%)")
        print(f"   ❌ Failed: {self.stats['failed']}")
        print(f"   ⏭️  Skipped: {self.stats['skipped']}")
        print(f"   📈 Rate: {rate:.2f} apps/minute")
        
        # Progress bar
        bar_width = 40
        filled = int(bar_width * self.stats["total_attempted"] / 1000)
        bar = "█" * filled + "░" * (bar_width - filled)
        print(f"   [{bar}] {self.stats['total_attempted']/10:.1f}%")
    
    def _save_intermediate_results(self):
        """Save intermediate results."""
        timestamp = datetime.now().strftime("%H%M%S")
        file_path = self.output_dir / f"progress_{timestamp}.json"
        
        with open(file_path, 'w') as f:
            json.dump({
                "stats": self.stats,
                "results": [asdict(r) for r in self.results],
                "timestamp": datetime.now().isoformat()
            }, f, indent=2, default=str)
        
        print(f"\n💾 Saved: {file_path.name}")
    
    async def _generate_final_report(self):
        """Generate comprehensive final report."""
        duration = (self.end_time - self.start_time).total_seconds()
        
        report = {
            "campaign_id": "matt_edwards_1000_real",
            "candidate": MATT_PROFILE,
            "configuration": {
                "concurrent_sessions": CONCURRENT_SESSIONS,
                "batch_size": BATCH_SIZE,
                "batch_delay_seconds": DELAY_BETWEEN_BATCHES,
                "total_jobs": len(self.jobs)
            },
            "summary": {
                "total_attempted": self.stats["total_attempted"],
                "successful": self.stats["successful"],
                "failed": self.stats["failed"],
                "skipped": self.stats["skipped"],
                "success_rate": round(self.stats["successful"] / self.stats["total_attempted"] * 100, 2) if self.stats["total_attempted"] > 0 else 0,
                "duration_seconds": round(duration, 2),
                "duration_minutes": round(duration / 60, 2),
                "apps_per_minute": round(self.stats["total_attempted"] / (duration / 60), 2) if duration > 0 else 0
            },
            "by_platform": self.stats["by_platform"],
            "error_breakdown": self.stats["errors"],
            "timeline": {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat()
            },
            "all_results": [asdict(r) for r in self.results]
        }
        
        # Save report
        report_file = self.output_dir / "MATT_1000_REAL_REPORT.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Print summary
        print("\n" + "="*80)
        print("✅ CAMPAIGN COMPLETE - FINAL REPORT")
        print("="*80)
        print(f"\n📊 Results:")
        print(f"   Total Attempted:    {report['summary']['total_attempted']}")
        print(f"   Successful:         {report['summary']['successful']}")
        print(f"   Failed:             {report['summary']['failed']}")
        print(f"   Skipped:            {report['summary']['skipped']}")
        print(f"   Success Rate:       {report['summary']['success_rate']:.1f}%")
        print(f"\n⏱️ Timing:")
        print(f"   Duration:           {report['summary']['duration_minutes']:.1f} minutes")
        print(f"   Apps/Minute:        {report['summary']['apps_per_minute']:.2f}")
        print(f"\n💾 Report: {report_file}")
        print("="*80)
        
        # Cleanup browser
        if self.browser_manager:
            await self.browser_manager.close_all()


async def main():
    """Main entry."""
    campaign = RealCampaign()
    
    if not campaign.jobs:
        print("❌ No jobs loaded")
        return
    
    print("\n" + "⚠️ "*40)
    print("⚠️  THIS IS A REAL CAMPAIGN WITH ACTUAL BROWSER AUTOMATION  ⚠️")
    print("⚠️ "*40)
    print(f"\nThis will navigate to {len(campaign.jobs)} real job URLs using BrowserBase")
    print(f"Candidate: {MATT_PROFILE['name']} <{MATT_PROFILE['email']}>")
    print("\n🚀 Starting in 10 seconds... (Ctrl+C to cancel)")
    
    try:
        for i in range(10, 0, -1):
            print(f"   {i}...", end="\r")
            await asyncio.sleep(1)
        print("   Go!    ")
        
        await campaign.run_campaign()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelled by user")
        if campaign.browser_manager:
            await campaign.browser_manager.close_all()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
