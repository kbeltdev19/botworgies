#!/usr/bin/env python3
"""
Kent Le - Final 1000 Submissions Campaign
WITH CAPTCHA SOLVING & ENHANCED BROWSER

This campaign:
1. Loads checkpoint from previous run (729 submissions)
2. Targets remaining 271 submissions
3. Uses EnhancedBrowserManager with CAPTCHA solving
4. Expects 85-95% success rate with CAPTCHA handling

Usage:
    KENT_1000_AUTO_CONFIRM=YES python kent_1000_final_with_captcha.py
"""

import os
import sys
import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import enhanced browser with CAPTCHA solving
from browser.enhanced_manager import EnhancedBrowserManager, ProxyConfig
from adapters import (
    JobSpyAdapter, SearchConfig, UserProfile, Resume,
    ApplicationStatus, JobPosting, ApplicationResult,
    get_adapter
)
from adapters.validation import SubmissionValidator

# Configuration
CONFIG = {
    "target_submissions": 1000,
    "current_submissions": 729,  # From checkpoint
    "needed": 271,  # Remaining
    "concurrent_sessions": 20,
    "batch_size": 50,
    "delay_between_batches": 45,  # Slightly longer for CAPTCHA solving
    "max_retries": 3,
    "enable_captcha_solving": True,
    "proxy_config": ProxyConfig(
        enabled=True,
        type="residential",
        country="US",
        sticky=True
    )
}

KENT_PROFILE = UserProfile(
    first_name="Kent",
    last_name="Le",
    email="kle4311@gmail.com",
    phone="(404) 934-0630",
    location="Auburn, AL",
    linkedin_url="https://linkedin.com/in/kent-le",
    work_authorization="Yes",
    sponsorship_required="No",
    years_experience=3,
    custom_answers={"salary_expectation": "75000"}
)

RESUME_PATH = "/Users/tech4/Downloads/botworkieslocsl/botworgies/Test Resumes/Kent_Le_Resume.pdf"
CHECKPOINT_PATH = "/Users/tech4/Downloads/botworkieslocsl/botworgies/campaigns/output/kent_1000_concurrent_20260203_1742/checkpoint.json"


@dataclass
class CampaignStats:
    """Track campaign statistics."""
    target: int = 1000
    previous_submissions: int = 729
    new_submissions: int = 0
    attempted: int = 0
    external: int = 0
    blocked: int = 0
    failed: int = 0
    captchas_solved: int = 0
    captcha_solve_time_total: float = 0.0
    browserbase_cost: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    
    @property
    def total_submissions(self) -> int:
        return self.previous_submissions + self.new_submissions
    
    @property
    def remaining(self) -> int:
        return self.target - self.total_submissions
    
    @property
    def success_rate(self) -> float:
        return (self.new_submissions / max(self.attempted, 1)) * 100


class KentFinalCampaign:
    """Final campaign to reach 1000 submissions with CAPTCHA solving."""
    
    def __init__(self):
        self.stats = CampaignStats()
        self.results: List[Dict] = []
        self.semaphore = asyncio.Semaphore(CONFIG["concurrent_sessions"])
        self.seen_urls: set = set()
        
        # Load previous checkpoint
        self._load_checkpoint()
        
        # Setup output directory
        self.output_dir = Path(__file__).parent / "output" / f"kent_1000_final_{datetime.now().strftime('%Y%m%d_%H%M')}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup resume
        self.resume = Resume(
            file_path=RESUME_PATH,
            raw_text="",
            parsed_data={"name": "Kent Le", "email": "kle4311@gmail.com"}
        )
        
        print(f"💾 Output: {self.output_dir}")
        print(f"🔄 Concurrent Sessions: {CONFIG['concurrent_sessions']}")
        print(f"🎯 Target: {self.stats.remaining} more submissions to reach 1000")
        print(f"🔐 CAPTCHA Solving: {'Enabled' if CONFIG['enable_captcha_solving'] else 'Disabled'}")
    
    def _load_checkpoint(self):
        """Load previous checkpoint to avoid duplicates."""
        if Path(CHECKPOINT_PATH).exists():
            with open(CHECKPOINT_PATH) as f:
                data = json.load(f)
                previous_results = data.get('results', [])
                self.seen_urls = {r.get('url', '') for r in previous_results}
                self.stats.previous_submissions = data.get('stats', {}).get('submitted', 729)
                print(f"✅ Loaded checkpoint: {self.stats.previous_submissions} previous submissions")
                print(f"   {len(self.seen_urls)} URLs already processed")
        else:
            print("⚠️ No checkpoint found, starting fresh")
    
    async def collect_jobs(self) -> List[JobPosting]:
        """Collect fresh jobs excluding already processed."""
        print("\n" + "="*70)
        print("🔍 COLLECTING FRESH JOBS")
        print("="*70)
        print(f"Needed: ~{self.stats.remaining * 3} jobs to get {self.stats.remaining} submissions")
        
        all_jobs = []
        adapter = JobSpyAdapter(sites=["indeed"])
        
        searches = [
            ("Customer Success Manager", ["Remote", "Atlanta, GA", "Austin, TX", "New York, NY", "Chicago, IL"]),
            ("Account Manager", ["Remote", "Atlanta, GA", "Austin, TX", "Chicago, IL", "Boston, MA"]),
            ("Sales Representative", ["Atlanta, GA", "Remote", "Dallas, TX", "Houston, TX", "Phoenix, AZ"]),
            ("Business Development Representative", ["Remote", "Austin, TX", "Denver, CO", "Salt Lake City, UT"]),
            ("Client Success Manager", ["Remote", "New York, NY", "San Francisco, CA", "Los Angeles, CA"]),
            ("Customer Success Specialist", ["Remote", "Boston, MA", "Seattle, WA", "Portland, OR"]),
            ("Account Executive", ["Remote", "Atlanta, GA", "Miami, FL", "Nashville, TN"]),
            ("Sales Development Representative", ["Remote", "Austin, TX", "Phoenix, AZ", "Raleigh, NC"]),
        ]
        
        target_jobs = self.stats.remaining * 3  # 3x for safety
        
        for term, locations in searches:
            if len(all_jobs) >= target_jobs:
                break
            
            print(f"\nSearching: {term}...", end=" ", flush=True)
            
            try:
                for location in locations:
                    if len(all_jobs) >= target_jobs:
                        break
                    
                    criteria = SearchConfig(
                        roles=[term],
                        locations=[location],
                        posted_within_days=7,  # Fresh jobs only
                        easy_apply_only=False,
                    )
                    
                    jobs = await adapter.search_jobs(criteria)
                    
                    # Filter out already processed URLs
                    new_jobs = [j for j in jobs if j.url not in self.seen_urls]
                    all_jobs.extend(new_jobs)
                    
                    if len(new_jobs) > 0:
                        print(f"+{len(new_jobs)} ", end="", flush=True)
                    
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                print(f"Error: {e}")
        
        print(f"\n✅ Collected {len(all_jobs)} fresh jobs")
        return all_jobs
    
    async def run_campaign(self, jobs: List[JobPosting]):
        """Run campaign with CAPTCHA solving."""
        print("\n" + "="*70)
        print("🚀 RUNNING FINAL CAMPAIGN WITH CAPTCHA SOLVING")
        print("="*70)
        print(f"🎯 Need: {self.stats.remaining} more submissions")
        print(f"📊 Available jobs: {len(jobs)}")
        print(f"⏱️  Estimated time: ~{len(jobs) * 0.1 / 20:.1f} hours")
        print()
        
        # Process in batches
        batch_size = CONFIG["batch_size"]
        total_batches = (len(jobs) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            if self.stats.new_submissions >= self.stats.remaining:
                print(f"\n🎉 TARGET REACHED! Total: {self.stats.total_submissions}")
                break
            
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(jobs))
            batch = jobs[start_idx:end_idx]
            
            print(f"\n📦 Batch {batch_num + 1}/{total_batches} ({len(batch)} jobs)")
            print(f"   Need {self.stats.remaining - self.stats.new_submissions} more submissions")
            
            # Run batch concurrently
            tasks = [self._apply_with_semaphore(job, i + start_idx + 1) for i, job in enumerate(batch)]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Save checkpoint
            self._save_checkpoint()
            self._print_progress()
            
            # Delay between batches
            if batch_num < total_batches - 1:
                delay = CONFIG["delay_between_batches"]
                print(f"\n⏳ Batch complete. Waiting {delay}s...")
                await asyncio.sleep(delay)
    
    async def _apply_with_semaphore(self, job: JobPosting, job_number: int):
        """Apply with semaphore-controlled concurrency."""
        async with self.semaphore:
            try:
                result = await self._apply_single_job(job, job_number)
                self._track_result(job, result)
            except Exception as e:
                self._track_result(job, ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=str(e)
                ))
    
    async def _apply_single_job(self, job: JobPosting, job_number: int) -> ApplicationResult:
        """Apply to single job using EnhancedBrowserManager with CAPTCHA solving."""
        self.stats.attempted += 1
        
        # Create browser manager with CAPTCHA solving
        browser_manager = EnhancedBrowserManager(
            max_concurrent_sessions=1,  # One per task
            enable_captcha_solving=CONFIG["enable_captcha_solving"],
            proxy_config=CONFIG["proxy_config"]
        )
        
        try:
            # Create session
            session = await browser_manager.create_session()
            page = session['page']
            
            # Navigate with CAPTCHA handling
            print(f"  [Job {job_number}] Loading {job.title[:40]}...")
            
            load_result = await browser_manager.wait_for_load(
                page=page,
                url=job.url,
                wait_for_captcha=True,
                timeout=45000
            )
            
            if not load_result['success']:
                await browser_manager.close_session(session['id'])
                self.stats.browserbase_cost += 0.10
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=f"Failed to load: {load_result.get('error', 'Unknown')}"
                )
            
            # Track CAPTCHA solving
            captcha_solved = False
            captcha_time = 0.0
            if load_result.get('captcha_result'):
                captcha_result = load_result['captcha_result']
                if captcha_result.status.value == 'solved':
                    captcha_solved = True
                    captcha_time = captcha_result.solve_time
                    self.stats.captchas_solved += 1
                    self.stats.captcha_solve_time_total += captcha_time
                    print(f"  [Job {job_number}] ✅ CAPTCHA solved in {captcha_time:.1f}s")
            
            # Wait for page to settle
            await asyncio.sleep(random.uniform(2, 4))
            
            # Get adapter and apply
            adapter = get_adapter(job.url, browser_manager)
            
            result = await adapter.apply_to_job(
                job=job,
                resume=self.resume,
                profile=KENT_PROFILE,
                cover_letter=None,
                auto_submit=True
            )
            
            # Track CAPTCHA info in result
            if captcha_solved:
                result.message = f"[CAPTCHA {captcha_time:.1f}s] {result.message}"
            
            await browser_manager.close_session(session['id'])
            self.stats.browserbase_cost += 0.10
            
            return result
            
        except Exception as e:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=str(e)
            )
    
    def _track_result(self, job: JobPosting, result: ApplicationResult):
        """Track result."""
        if result.status == ApplicationStatus.SUBMITTED:
            self.stats.new_submissions += 1
        elif result.status == ApplicationStatus.EXTERNAL_APPLICATION:
            self.stats.external += 1
        elif result.status == ApplicationStatus.ERROR:
            if "captcha" in result.message.lower():
                self.stats.blocked += 1
            else:
                self.stats.failed += 1
        
        self.results.append({
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "status": result.status.value,
            "message": result.message,
            "timestamp": datetime.now().isoformat(),
        })
    
    def _print_progress(self):
        """Print progress."""
        progress = (self.stats.total_submissions / CONFIG["target_submissions"]) * 100
        print(f"\n{'='*70}")
        print(f"📊 PROGRESS: {self.stats.total_submissions}/{CONFIG['target_submissions']} ({progress:.1f}%)")
        print(f"New submissions this run: {self.stats.new_submissions}")
        print(f"Attempted: {self.stats.attempted} | Success Rate: {self.stats.success_rate:.1f}%")
        print(f"CAPTCHAs solved: {self.stats.captchas_solved}")
        print(f"External: {self.stats.external} | Blocked: {self.stats.blocked} | Failed: {self.stats.failed}")
        print(f"Cost: ${self.stats.browserbase_cost:.2f}")
        print(f"{'='*70}\n")
    
    def _save_checkpoint(self):
        """Save checkpoint."""
        checkpoint_file = self.output_dir / "checkpoint.json"
        
        checkpoint = {
            "stats": {
                "target": self.stats.target,
                "previous_submissions": self.stats.previous_submissions,
                "new_submissions": self.stats.new_submissions,
                "total_submissions": self.stats.total_submissions,
                "remaining": self.stats.remaining,
                "attempted": self.stats.attempted,
                "success_rate": self.stats.success_rate,
                "captchas_solved": self.stats.captchas_solved,
                "total_cost": self.stats.browserbase_cost,
                "elapsed_hours": (datetime.now() - self.stats.start_time).total_seconds() / 3600,
            },
            "results": self.results,
            "timestamp": datetime.now().isoformat(),
        }
        
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def save_final(self):
        """Save final results."""
        final_data = {
            "campaign_id": f"kent_1000_final_{datetime.now().strftime('%Y%m%d_%H%M')}",
            "type": "FINAL_1000_WITH_CAPTCHA",
            "config": CONFIG,
            "candidate": {"name": "Kent Le", "email": "kle4311@gmail.com"},
            "stats": {
                "target": self.stats.target,
                "previous_submissions": self.stats.previous_submissions,
                "new_submissions": self.stats.new_submissions,
                "total_submissions": self.stats.total_submissions,
                "attempted": self.stats.attempted,
                "success_rate": f"{self.stats.success_rate:.1f}%",
                "captchas_solved": self.stats.captchas_solved,
                "total_cost": f"${self.stats.browserbase_cost:.2f}",
                "elapsed_hours": f"{(datetime.now() - self.stats.start_time).total_seconds() / 3600:.1f}",
            },
            "results": self.results,
        }
        
        json_file = self.output_dir / "final_results.json"
        with open(json_file, 'w') as f:
            json.dump(final_data, f, indent=2)
        
        csv_file = self.output_dir / "applications.csv"
        with open(csv_file, 'w') as f:
            f.write("ID,Company,Title,Location,Status,URL\n")
            for r in self.results:
                f.write(f'"{r["id"]}","{r["company"]}","{r["title"]}","{r["location"]}","{r["status"]}","{r["url"]}"\n')
        
        return json_file, csv_file
    
    async def run(self):
        """Run final campaign."""
        print("\n" + "🚀"*35)
        print("   KENT LE - FINAL 1000 SUBMISSIONS")
        print("   WITH CAPTCHA SOLVING & ENHANCED BROWSER")
        print("   " + "🚀"*35)
        print(f"\n   🎯 TARGET: {self.stats.remaining} MORE SUBMISSIONS")
        print(f"   📊 Current: {self.stats.previous_submissions}/1000")
        print(f"   🔐 CAPTCHA Solving: ENABLED")
        print(f"   🌐 Residential Proxies: ENABLED")
        
        if os.environ.get("KENT_1000_AUTO_CONFIRM") != "YES":
            confirm = input("\nType 'RUN1000' to start: ")
            if confirm != "RUN1000":
                print("\n❌ Cancelled.")
                return
        else:
            print("\n✅ Auto-confirmed")
        
        try:
            # Collect fresh jobs
            jobs = await self.collect_jobs()
            
            if len(jobs) == 0:
                print("\n❌ No fresh jobs found!")
                return
            
            # Run campaign
            await self.run_campaign(jobs)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
        except Exception as e:
            print(f"\n\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            json_file, csv_file = self.save_final()
            
            print("\n" + "="*70)
            if self.stats.total_submissions >= CONFIG["target_submissions"]:
                print("🎉 CAMPAIGN COMPLETE - 1000 SUBMISSIONS REACHED!")
            else:
                print(f"⚠️  CAMPAIGN ENDED - {self.stats.total_submissions}/1000 submissions")
            print("="*70)
            print(f"🎯 Total Submissions: {self.stats.total_submissions}")
            print(f"✅ New This Run: {self.stats.new_submissions}")
            print(f"📊 Overall Success Rate: {self.stats.success_rate:.1f}%")
            print(f"🤖 CAPTCHAs Solved: {self.stats.captchas_solved}")
            print(f"💰 Total Cost: ${self.stats.browserbase_cost:.2f}")
            print(f"💾 Files: {json_file}, {csv_file}")


async def main():
    runner = KentFinalCampaign()
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
