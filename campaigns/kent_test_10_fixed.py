#!/usr/bin/env python3
"""
KENT LE - TEST 10 JOBS WITH FIXED VALIDATION

This is a TEST campaign to verify the fixed validation works:
1. Apply to only 10 jobs
2. Use fixed validation (checks for real success indicators)
3. Detect Cloudflare blocks properly
4. Log everything in detail
5. Report actual success rate
6. STOP and report results

Usage:
    python kent_test_10_fixed.py
"""

import os
import sys
import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict
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
class TestStats:
    """Track test statistics."""
    attempted: int = 0
    real_submissions: int = 0  # ONLY counts with success indicator
    cloudflare_blocked: int = 0
    form_errors: int = 0
    external_redirect: int = 0
    other_errors: int = 0
    browserbase_cost: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    
    @property
    def real_success_rate(self) -> float:
        return (self.real_submissions / max(self.attempted, 1)) * 100


class KentTest10Campaign:
    """Test campaign with fixed validation - 10 jobs only."""
    
    def __init__(self):
        self.stats = TestStats()
        self.results: List[Dict] = []
        self.output_dir = Path(__file__).parent / "output" / f"kent_test10_fixed_{datetime.now().strftime('%Y%m%d_%H%M')}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.resume = Resume(
            file_path=RESUME_PATH,
            raw_text="",
            parsed_data={"name": "Kent Le", "email": "kle4311@gmail.com"}
        )
        
        self.error_logger = get_error_logger(str(self.output_dir / "errors"))
        
        print("="*70)
        print("🧪 KENT LE - TEST 10 JOBS (FIXED VALIDATION)")
        print("="*70)
        print()
        print("This test will:")
        print("  1. Apply to exactly 10 jobs")
        print("  2. Use FIXED validation logic")
        print("  3. Count ONLY real submissions (with success indicators)")
        print("  4. Properly detect Cloudflare blocks")
        print("  5. Report ACTUAL success rate")
        print()
        print("💾 Output:", self.output_dir)
        print()
    
    async def get_10_jobs(self) -> List[JobPosting]:
        """Get exactly 10 fresh jobs."""
        print("🔍 Collecting 10 test jobs...")
        
        adapter = JobSpyAdapter(sites=["indeed"])
        all_jobs = []
        
        searches = [
            ("Customer Success Manager", ["Remote"]),
            ("Account Manager", ["Remote"]),
        ]
        
        for term, locations in searches:
            if len(all_jobs) >= 10:
                break
            
            for location in locations:
                if len(all_jobs) >= 10:
                    break
                
                criteria = SearchConfig(
                    roles=[term],
                    locations=[location],
                    posted_within_days=7,
                    easy_apply_only=False,
                )
                
                jobs = await adapter.search_jobs(criteria)
                all_jobs.extend(jobs[:10])
                
                await asyncio.sleep(0.5)
        
        return all_jobs[:10]
    
    async def run_test(self, jobs: List[JobPosting]):
        """Run test on 10 jobs sequentially (for detailed logging)."""
        print(f"\n🚀 TESTING {len(jobs)} JOBS WITH FIXED VALIDATION\n")
        print("="*70)
        
        for i, job in enumerate(jobs, 1):
            print(f"\n📋 Job {i}/10: {job.company[:35]} - {job.title[:40]}")
            print("-"*70)
            
            result = await self._apply_single(job, i)
            self._track_result(job, result)
            
            # Pause between jobs for clarity
            if i < len(jobs):
                print("\n⏳ Waiting 5s before next job...")
                await asyncio.sleep(5)
        
        print("\n" + "="*70)
        print("🧪 TEST COMPLETE")
        print("="*70)
    
    async def _apply_single(self, job: JobPosting, job_number: int) -> ApplicationResult:
        """Apply to single job with fixed validation."""
        self.stats.attempted += 1
        
        browser_manager = StealthBrowserManager()
        
        try:
            # Step 1: Navigate
            print("  [1/4] Navigating to job page...")
            session = await browser_manager.create_stealth_session(platform="indeed")
            page = session.page
            
            await page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
            await browser_manager.human_like_delay(2, 3)
            
            # Step 2: Check for Cloudflare immediately
            content = await page.content()
            if SubmissionValidatorFixed.check_is_cloudflare_page(content):
                print("  ❌ BLOCKED: Cloudflare verification detected immediately")
                self.stats.cloudflare_blocked += 1
                await browser_manager.close_all()
                self.stats.browserbase_cost += 0.10
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message="Cloudflare block on initial load"
                )
            
            # Step 3: Find and click Apply
            print("  [2/4] Looking for Apply button...")
            apply_selectors = [
                '#indeedApplyButton',
                'button:has-text("Apply now")',
                '.ia-ApplyButton',
            ]
            
            apply_found = False
            for selector in apply_selectors:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    print(f"  ✅ Found apply button: {selector}")
                    await btn.click()
                    apply_found = True
                    break
            
            if not apply_found:
                print("  ⚠️  No Apply button found - checking for external redirect...")
                # Check if external apply link
                external_link = page.locator('a:has-text("Apply on company site")').first
                if await external_link.count() > 0:
                    print("  🔗 EXTERNAL: Company site application required")
                    self.stats.external_redirect += 1
                    await browser_manager.close_all()
                    self.stats.browserbase_cost += 0.10
                    return ApplicationResult(
                        status=ApplicationStatus.EXTERNAL_APPLICATION,
                        message="External application required"
                    )
                
                print("  ❌ ERROR: No apply option found")
                self.stats.other_errors += 1
                await browser_manager.close_all()
                self.stats.browserbase_cost += 0.10
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message="No apply button or external link found"
                )
            
            # Step 4: Wait for form/result
            print("  [3/4] Waiting for application form/result...")
            await browser_manager.human_like_delay(3, 5)
            
            # Step 5: FIXED VALIDATION
            print("  [4/4] Validating result with FIXED validator...")
            validation = await SubmissionValidatorFixed.validate(
                page, job.id, platform="indeed",
                screenshot_dir=str(self.output_dir / "screenshots")
            )
            
            await browser_manager.close_all()
            self.stats.browserbase_cost += 0.10
            
            # Log result
            if validation['is_cloudflare']:
                print(f"  ❌ RESULT: Cloudflare blocked")
                print(f"  📝 Message: {validation['message']}")
                self.stats.cloudflare_blocked += 1
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=validation['message'],
                    screenshot_path=validation['screenshot_path']
                )
            
            if validation['success']:
                print(f"  ✅ RESULT: REAL SUBMISSION CONFIRMED!")
                print(f"  📝 Message: {validation['message']}")
                if validation['confirmation_id']:
                    print(f"  🔑 Confirmation ID: {validation['confirmation_id']}")
                self.stats.real_submissions += 1
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message=validation['message'],
                    confirmation_id=validation['confirmation_id'],
                    screenshot_path=validation['screenshot_path'],
                    submitted_at=datetime.now()
                )
            
            # Not success, not cloudflare - some other error
            print(f"  ❌ RESULT: Failed - {validation['message']}")
            self.stats.other_errors += 1
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=validation['message'],
                screenshot_path=validation['screenshot_path']
            )
            
        except Exception as e:
            print(f"  ❌ EXCEPTION: {str(e)[:80]}")
            await browser_manager.close_all()
            self.stats.browserbase_cost += 0.10
            self.stats.other_errors += 1
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Exception: {str(e)}"
            )
    
    def _track_result(self, job: JobPosting, result: ApplicationResult):
        """Track result."""
        self.results.append({
            "job_number": len(self.results) + 1,
            "company": job.company,
            "title": job.title,
            "url": job.url,
            "status": result.status.value,
            "message": result.message,
            "confirmation_id": result.confirmation_id,
            "screenshot": result.screenshot_path,
        })
    
    def print_final_report(self):
        """Print final test report."""
        print("\n" + "="*70)
        print("📊 FINAL TEST REPORT")
        print("="*70)
        print()
        print(f"Jobs Tested: {self.stats.attempted}")
        print()
        print("Results:")
        print(f"  ✅ REAL Submissions:     {self.stats.real_submissions}")
        print(f"  🚫 Cloudflare Blocked:   {self.stats.cloudflare_blocked}")
        print(f"  🔗 External Redirect:    {self.stats.external_redirect}")
        print(f"  📝 Form Errors:          {self.stats.form_errors}")
        print(f"  ❌ Other Errors:         {self.stats.other_errors}")
        print()
        print(f"ACTUAL Success Rate: {self.stats.real_success_rate:.1f}%")
        print(f"Cost: ${self.stats.browserbase_cost:.2f}")
        print()
        
        if self.stats.real_submissions > 0:
            print("🎉 GOOD NEWS: Found real submissions!")
            print("   The fixed validation is working correctly.")
            print()
            print("Next steps:")
            print("  1. Check Kent's email for confirmations")
            print("  2. If emails arrive, scale up to 100 jobs")
            print("  3. Then full campaign")
        else:
            print("⚠️  ISSUE: No real submissions")
            print("   Possible causes:")
            print("   - All 10 jobs blocked by Cloudflare")
            print("   - Indeed detecting automation")
            print("   - Need CAPTCHA solving")
            print()
            print("Recommendations:")
            print("  1. Try with CAPTCHA solving service")
            print("  2. Use residential proxies")
            print("  3. Slow down (longer delays)")
        
        print()
        print(f"💾 Full results: {self.output_dir}/test_results.json")
        print("="*70)
    
    def save_results(self):
        """Save test results."""
        results = {
            "test_type": "10_JOBS_FIXED_VALIDATION",
            "timestamp": datetime.now().isoformat(),
            "stats": {
                "attempted": self.stats.attempted,
                "real_submissions": self.stats.real_submissions,
                "cloudflare_blocked": self.stats.cloudflare_blocked,
                "external_redirect": self.stats.external_redirect,
                "form_errors": self.stats.form_errors,
                "other_errors": self.stats.other_errors,
                "success_rate": self.stats.real_success_rate,
                "cost": self.stats.browserbase_cost,
            },
            "results": self.results,
        }
        
        with open(self.output_dir / "test_results.json", 'w') as f:
            json.dump(results, f, indent=2)
    
    async def run(self):
        """Run test campaign."""
        print("\n⚠️  CONFIRMATION REQUIRED")
        print("-"*70)
        print("This will test 10 jobs and cost approximately $1.00")
        print("The goal is to verify the FIXED validation works correctly.")
        print()
        confirm = input("Type 'TEST10' to start: ")
        
        if confirm != "TEST10":
            print("\n❌ Cancelled.")
            return
        
        try:
            # Get jobs
            jobs = await self.get_10_jobs()
            
            if len(jobs) < 10:
                print(f"\n⚠️  Only found {len(jobs)} jobs, proceeding...")
            
            # Run test
            await self.run_test(jobs)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.print_final_report()
            self.save_results()


async def main():
    campaign = KentTest10Campaign()
    await campaign.run()


if __name__ == "__main__":
    asyncio.run(main())
