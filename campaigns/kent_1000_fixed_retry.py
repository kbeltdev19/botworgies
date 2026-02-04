#!/usr/bin/env python3
"""
KENT LE - 1000 REAL SUBMISSIONS (FIXED RETRY)

This is the FIXED campaign that:
1. Uses proper validation (checks for real success indicators)
2. Properly detects Cloudflare blocks
3. Only counts REAL submissions
4. Provides accurate reporting
5. Stops at 1000 REAL submissions (not page navigations)

REQUIREMENT: Run kent_test_10_fixed.py first and verify success rate!

Usage:
    KENT_1000_FIXED_AUTO=YES python kent_1000_fixed_retry.py
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

from browser.stealth_manager import StealthBrowserManager
from adapters import (
    JobSpyAdapter, SearchConfig, UserProfile, Resume,
    ApplicationStatus, JobPosting, ApplicationResult,
    get_adapter
)
from adapters.validation_fixed import SubmissionValidatorFixed
from adapters.error_logger import get_error_logger

CONFIG = {
    "target": 1000,
    "concurrent_sessions": 5,  # Lower for better accuracy
    "batch_size": 20,
    "delay_between_batches": 60,
    "max_retries": 2,
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


@dataclass
class FixedCampaignStats:
    """Stats with honest reporting."""
    target: int = 1000
    attempted: int = 0
    real_submissions: int = 0  # ONLY real ones with confirmation
    cloudflare_blocked: int = 0
    external_redirect: int = 0
    form_errors: int = 0
    other_errors: int = 0
    browserbase_cost: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    
    @property
    def real_success_rate(self) -> float:
        return (self.real_submissions / max(self.attempted, 1)) * 100
    
    @property
    def remaining(self) -> int:
        return self.target - self.real_submissions


class Kent1000FixedCampaign:
    """Fixed campaign with honest reporting."""
    
    def __init__(self):
        self.stats = FixedCampaignStats()
        self.results: List[Dict] = []
        self.semaphore = asyncio.Semaphore(CONFIG["concurrent_sessions"])
        self.seen_urls: set = set()
        
        self.output_dir = Path(__file__).parent / "output" / f"kent_1000_fixed_{datetime.now().strftime('%Y%m%d_%H%M')}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.resume = Resume(
            file_path=RESUME_PATH,
            raw_text="",
            parsed_data={"name": "Kent Le", "email": "kle4311@gmail.com"}
        )
        
        self.error_logger = get_error_logger(str(self.output_dir / "errors"))
        
        print("="*70)
        print("🚀 KENT LE - 1000 REAL SUBMISSIONS (FIXED)")
        print("="*70)
        print()
        print("⚠️  IMPORTANT: This campaign uses FIXED validation")
        print("   Only REAL submissions with success indicators count.")
        print("   Cloudflare blocks are NOT counted as submissions.")
        print()
        print("💾 Output:", self.output_dir)
        print(f"🎯 Target: {CONFIG['target']} REAL submissions")
        print(f"🔄 Concurrent: {CONFIG['concurrent_sessions']}")
        print()
    
    async def collect_jobs(self) -> List[JobPosting]:
        """Collect jobs."""
        print("🔍 Collecting jobs...")
        
        adapter = JobSpyAdapter(sites=["indeed"])
        all_jobs = []
        
        searches = [
            ("Customer Success Manager", ["Remote", "Atlanta, GA"]),
            ("Account Manager", ["Remote", "Austin, TX"]),
            ("Sales Representative", ["Remote", "Dallas, TX"]),
            ("Business Development Representative", ["Remote"]),
            ("Customer Success Associate", ["Remote", "New York, NY"]),
            ("Implementation Specialist", ["Remote", "Boston, MA"]),
        ]
        
        # Need many more jobs since most will be blocked
        target = self.stats.remaining * 10  # 10x buffer
        
        for term, locations in searches:
            if len(all_jobs) >= target:
                break
            
            print(f"\nSearching: {term}...", end=" ", flush=True)
            
            for location in locations:
                if len(all_jobs) >= target:
                    break
                
                criteria = SearchConfig(
                    roles=[term],
                    locations=[location],
                    posted_within_days=14,
                    easy_apply_only=False,
                )
                
                jobs = await adapter.search_jobs(criteria)
                new_jobs = [j for j in jobs if j.url not in self.seen_urls]
                all_jobs.extend(new_jobs)
                
                if len(new_jobs) > 0:
                    print(f"+{len(new_jobs)} ", end="", flush=True)
                
                await asyncio.sleep(0.5)
        
        print(f"\n✅ Collected {len(all_jobs)} jobs")
        return all_jobs
    
    async def run_campaign(self, jobs: List[JobPosting]):
        """Run campaign."""
        print(f"\n🚀 Starting campaign...")
        print(f"   Need: {self.stats.remaining} real submissions")
        print(f"   Available: {len(jobs)} jobs")
        print(f"   Expected success rate: 5-15% (based on test)")
        print()
        
        batch_size = CONFIG["batch_size"]
        total_batches = (len(jobs) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            if self.stats.real_submissions >= CONFIG["target"]:
                print(f"\n🎉 TARGET REACHED: {self.stats.real_submissions} REAL submissions!")
                break
            
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(jobs))
            batch = jobs[start_idx:end_idx]
            
            print(f"\n📦 Batch {batch_num + 1}/{total_batches}")
            print(f"   Need {self.stats.remaining - self.stats.real_submissions} more real submissions")
            
            # Run batch
            tasks = [self._apply_with_semaphore(job, i + start_idx + 1) for i, job in enumerate(batch)]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Save progress
            self._save_checkpoint()
            self._print_progress()
            
            # Delay between batches
            if batch_num < total_batches - 1:
                await asyncio.sleep(CONFIG["delay_between_batches"])
    
    async def _apply_with_semaphore(self, job: JobPosting, job_number: int):
        """Apply with semaphore."""
        async with self.semaphore:
            try:
                result = await self._apply_single(job, job_number)
                self._track_result(job, result)
            except Exception as e:
                self._track_result(job, ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=str(e)
                ))
    
    async def _apply_single(self, job: JobPosting, job_number: int) -> ApplicationResult:
        """Apply with fixed validation."""
        self.stats.attempted += 1
        
        browser_manager = StealthBrowserManager()
        
        try:
            # Create session
            session = await browser_manager.create_stealth_session(platform="indeed")
            page = session.page
            
            # Navigate
            await page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
            await browser_manager.human_like_delay(2, 3)
            
            # Check for Cloudflare immediately
            content = await page.content()
            if SubmissionValidatorFixed.check_is_cloudflare_page(content):
                await browser_manager.close_all()
                self.stats.browserbase_cost += 0.10
                self.stats.cloudflare_blocked += 1
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message="Cloudflare block"
                )
            
            # Find and click apply
            apply_selectors = ['#indeedApplyButton', 'button:has-text("Apply now")']
            apply_found = False
            
            for selector in apply_selectors:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    apply_found = True
                    break
            
            if not apply_found:
                # Check external
                external_link = page.locator('a:has-text("Apply on company site")').first
                if await external_link.count() > 0:
                    await browser_manager.close_all()
                    self.stats.browserbase_cost += 0.10
                    self.stats.external_redirect += 1
                    return ApplicationResult(
                        status=ApplicationStatus.EXTERNAL_APPLICATION,
                        message="External application required"
                    )
                
                await browser_manager.close_all()
                self.stats.browserbase_cost += 0.10
                self.stats.other_errors += 1
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message="No apply option found"
                )
            
            # Wait for result
            await browser_manager.human_like_delay(3, 5)
            
            # FIXED VALIDATION
            validation = await SubmissionValidatorFixed.validate(
                page, job.id, platform="indeed",
                screenshot_dir=str(self.output_dir / "screenshots")
            )
            
            await browser_manager.close_all()
            self.stats.browserbase_cost += 0.10
            
            # Track based on validation result
            if validation['is_cloudflare']:
                self.stats.cloudflare_blocked += 1
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=validation['message'],
                    screenshot_path=validation['screenshot_path']
                )
            
            if validation['success']:
                self.stats.real_submissions += 1
                print(f"  ✅ REAL SUBMISSION: {job.company[:30]}")
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message=validation['message'],
                    confirmation_id=validation['confirmation_id'],
                    screenshot_path=validation['screenshot_path'],
                    submitted_at=datetime.now()
                )
            
            # Failed
            self.stats.other_errors += 1
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=validation['message'],
                screenshot_path=validation['screenshot_path']
            )
            
        except Exception as e:
            await browser_manager.close_all()
            self.stats.browserbase_cost += 0.10
            self.stats.other_errors += 1
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=str(e)
            )
    
    def _track_result(self, job: JobPosting, result: ApplicationResult):
        """Track result."""
        self.results.append({
            "id": job.id,
            "company": job.company,
            "title": job.title,
            "status": result.status.value,
            "message": result.message,
            "confirmation_id": result.confirmation_id,
            "timestamp": datetime.now().isoformat(),
        })
    
    def _print_progress(self):
        """Print progress."""
        print(f"\n{'='*70}")
        print(f"📊 REAL SUBMISSIONS: {self.stats.real_submissions}/{CONFIG['target']}")
        print(f"   Attempted: {self.stats.attempted}")
        print(f"   Success Rate: {self.stats.real_success_rate:.1f}%")
        print(f"   Cloudflare: {self.stats.cloudflare_blocked}")
        print(f"   External: {self.stats.external_redirect}")
        print(f"   Errors: {self.stats.other_errors}")
        print(f"   Cost: ${self.stats.browserbase_cost:.2f}")
        print(f"{'='*70}\n")
    
    def _save_checkpoint(self):
        """Save checkpoint."""
        checkpoint = {
            "stats": {
                "target": self.stats.target,
                "real_submissions": self.stats.real_submissions,
                "attempted": self.stats.attempted,
                "success_rate": self.stats.real_success_rate,
                "cloudflare_blocked": self.stats.cloudflare_blocked,
                "external": self.stats.external_redirect,
                "errors": self.stats.other_errors,
                "cost": self.stats.browserbase_cost,
            },
            "results": self.results,
        }
        
        with open(self.output_dir / "checkpoint.json", 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def save_final(self):
        """Save final results."""
        final_data = {
            "campaign_type": "1000_REAL_SUBMISSIONS_FIXED",
            "stats": {
                "target": self.stats.target,
                "real_submissions": self.stats.real_submissions,
                "attempted": self.stats.attempted,
                "success_rate": self.stats.real_success_rate,
                "cloudflare_blocked": self.stats.cloudflare_blocked,
                "external": self.stats.external_redirect,
                "errors": self.stats.other_errors,
                "cost": self.stats.browserbase_cost,
                "elapsed_hours": (datetime.now() - self.stats.start_time).total_seconds() / 3600,
            },
            "results": self.results,
        }
        
        with open(self.output_dir / "final_results.json", 'w') as f:
            json.dump(final_data, f, indent=2)
        
        with open(self.output_dir / "applications.csv", 'w') as f:
            f.write("ID,Company,Title,Status,ConfirmationID\n")
            for r in self.results:
                if r['status'] == 'submitted':
                    f.write(f'"{r["id"]}","{r["company"]}","{r["title"]}","{r["status"]}","{r.get("confirmation_id", "")}"\n')
        
        return self.output_dir
    
    async def run(self):
        """Run campaign."""
        print("\n" + "="*70)
        print("⚠️  PRE-FLIGHT CHECK")
        print("="*70)
        print()
        print("Before starting, you should:")
        print("  1. ✅ Run kent_test_10_fixed.py")
        print("  2. ✅ Verify real success rate")
        print("  3. ✅ Check Kent's email for confirmations")
        print()
        
        confirm = input("Have you run the 10-job test? Type 'YES' to continue: ")
        if confirm != "YES":
            print("\n❌ Please run the test first:")
            print("   python campaigns/kent_test_10_fixed.py")
            return
        
        print("\n⚠️  This will attempt to get 1000 REAL submissions.")
        print("   Expected cost: $500-2000 (depending on success rate)")
        print("   Expected time: 12-24 hours")
        print()
        
        if os.environ.get("KENT_1000_FIXED_AUTO") != "YES":
            confirm2 = input("Type 'RUN1000' to start: ")
            if confirm2 != "RUN1000":
                print("\n❌ Cancelled.")
                return
        
        try:
            jobs = await self.collect_jobs()
            await self.run_campaign(jobs)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            output_dir = self.save_final()
            print("\n" + "="*70)
            print("✅ CAMPAIGN COMPLETE")
            print("="*70)
            print(f"🎯 REAL Submissions: {self.stats.real_submissions}")
            print(f"📊 Success Rate: {self.stats.real_success_rate:.1f}%")
            print(f"💰 Total Cost: ${self.stats.browserbase_cost:.2f}")
            print(f"💾 Output: {output_dir}")


async def main():
    campaign = Kent1000FixedCampaign()
    await campaign.run()


if __name__ == "__main__":
    asyncio.run(main())
