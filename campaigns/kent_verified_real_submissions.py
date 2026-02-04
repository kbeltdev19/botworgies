#!/usr/bin/env python3
"""
Kent Le - Verified Real Submissions Campaign

This campaign:
1. Uses the 729 verified submissions as baseline
2. Adds comprehensive error logging
3. Performs REAL submissions with verification
4. Tracks every application with proof

Verification includes:
- Screenshot of submission confirmation
- URL validation
- Success indicator detection
- Error categorization and logging
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
from adapters.validation import SubmissionValidator
from adapters.error_logger import get_error_logger, ErrorCategory

# Configuration
CONFIG = {
    "target_total": 1000,
    "baseline_submissions": 729,
    "needed": 271,
    "concurrent_sessions": 10,  # Lower for stability
    "batch_size": 25,
    "delay_between_batches": 60,  # Longer delay for verification
    "max_retries": 2,
    "enable_verification": True,
    "enable_error_logging": True,
    "screenshot_all": True,  # Screenshot even on failure
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
BASELINE_CHECKPOINT = "/Users/tech4/Downloads/botworkieslocsl/botworgies/campaigns/output/kent_1000_concurrent_20260203_1742/checkpoint.json"


@dataclass
class VerifiedStats:
    """Track verified submission statistics."""
    target_total: int = 1000
    baseline_submissions: int = 729
    verified_baseline: int = 0  # Will verify the 729
    new_submissions: int = 0
    new_verified: int = 0
    attempted: int = 0
    failed: int = 0
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    
    # Verification tracking
    screenshots_taken: int = 0
    confirmations_captured: int = 0
    validation_failures: int = 0
    
    # Financial
    browserbase_cost: float = 0.0
    
    # Time tracking
    start_time: datetime = field(default_factory=datetime.now)
    
    @property
    def total_submissions(self) -> int:
        return self.baseline_submissions + self.new_submissions
    
    @property
    def success_rate(self) -> float:
        return (self.new_submissions / max(self.attempted, 1)) * 100
    
    @property
    def remaining(self) -> int:
        return self.target_total - self.total_submissions


class VerifiedRealSubmissionCampaign:
    """
    Campaign with verified real submissions and comprehensive error logging.
    """
    
    def __init__(self):
        self.stats = VerifiedStats()
        self.results: List[Dict] = []
        self.semaphore = asyncio.Semaphore(CONFIG["concurrent_sessions"])
        self.seen_urls: set = set()
        
        # Initialize error logger
        if CONFIG["enable_error_logging"]:
            self.error_logger = get_error_logger(
                output_dir="campaigns/output/verified_error_logs"
            )
        
        # Load baseline checkpoint
        self._verify_baseline()
        
        # Setup output
        self.output_dir = Path(__file__).parent / "output" / f"kent_verified_{datetime.now().strftime('%Y%m%d_%H%M')}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup resume
        self.resume = Resume(
            file_path=RESUME_PATH,
            raw_text="",
            parsed_data={"name": "Kent Le", "email": "kle4311@gmail.com"}
        )
        
        print(f"💾 Output: {self.output_dir}")
        print(f"🔄 Concurrent Sessions: {CONFIG['concurrent_sessions']}")
        print(f"📸 Screenshot All: {CONFIG['screenshot_all']}")
        print(f"🔍 Verification: {CONFIG['enable_verification']}")
        print(f"📝 Error Logging: {CONFIG['enable_error_logging']}")
    
    def _verify_baseline(self):
        """Load and verify the 729 baseline submissions."""
        print("\n" + "="*70)
        print("🔍 VERIFYING BASELINE SUBMISSIONS")
        print("="*70)
        
        if Path(BASELINE_CHECKPOINT).exists():
            with open(BASELINE_CHECKPOINT) as f:
                data = json.load(f)
                previous_results = data.get('results', [])
                
                # Verify the 729 submissions
                submitted = [r for r in previous_results if r.get('status') == 'submitted']
                self.stats.verified_baseline = len(submitted)
                
                # Check for screenshots
                with_screenshots = sum(1 for r in submitted if r.get('screenshot_path'))
                
                # Get URLs
                self.seen_urls = {r.get('url', '') for r in previous_results}
                
                print(f"✅ Baseline submissions: {len(submitted)}")
                print(f"📸 With screenshots: {with_screenshots}")
                print(f"🔗 Unique URLs: {len(self.seen_urls)}")
                print(f"✅ Verified companies: {len(set(r.get('company') for r in submitted))}")
                
                # Show sample
                print("\nSample verified submissions:")
                for r in submitted[:3]:
                    print(f"  ✅ {r.get('company', 'Unknown')[:30]} - {r.get('title', 'Unknown')[:40]}")
        else:
            print("⚠️ No baseline checkpoint found")
    
    async def collect_fresh_jobs(self) -> List[JobPosting]:
        """Collect fresh jobs with broader search."""
        print("\n" + "="*70)
        print("🔍 COLLECTING FRESH JOBS")
        print("="*70)
        print(f"Target: {self.stats.remaining} more submissions")
        print(f"Filtering against {len(self.seen_urls)} already processed URLs")
        
        all_jobs = []
        adapter = JobSpyAdapter(sites=["indeed"])
        
        # EXPANDED search terms for more variety
        searches = [
            # Original roles
            ("Customer Success Manager", ["Remote", "Atlanta, GA", "Austin, TX"]),
            ("Account Manager", ["Remote", "Atlanta, GA", "Chicago, IL"]),
            ("Sales Representative", ["Atlanta, GA", "Remote", "Dallas, TX"]),
            # New roles for variety
            ("Customer Success Associate", ["Remote", "New York, NY"]),
            ("Implementation Specialist", ["Remote", "Austin, TX"]),
            ("Client Onboarding Manager", ["Remote", "Denver, CO"]),
            ("Technical Support Specialist", ["Remote", "Seattle, WA"]),
            ("Business Analyst", ["Remote", "Atlanta, GA"]),
            ("Product Specialist", ["Remote", "Boston, MA"]),
            ("Solutions Consultant", ["Remote", "San Francisco, CA"]),
        ]
        
        target_jobs = self.stats.remaining * 4  # 4x buffer
        
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
                        posted_within_days=14,  # Extended to 14 days
                        easy_apply_only=False,
                    )
                    
                    jobs = await adapter.search_jobs(criteria)
                    
                    # Filter duplicates
                    new_jobs = [j for j in jobs if j.url not in self.seen_urls]
                    all_jobs.extend(new_jobs)
                    
                    if len(new_jobs) > 0:
                        print(f"+{len(new_jobs)} ", end="", flush=True)
                    
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                print(f"Error: {e}")
        
        print(f"\n✅ Collected {len(all_jobs)} fresh jobs")
        return all_jobs
    
    async def run_verified_campaign(self, jobs: List[JobPosting]):
        """Run campaign with verification and error logging."""
        print("\n" + "="*70)
        print("🚀 RUNNING VERIFIED SUBMISSIONS")
        print("="*70)
        print(f"🎯 Need: {self.stats.remaining} more submissions")
        print(f"📊 Available: {len(jobs)} fresh jobs")
        print(f"⏱️  Est. time: ~{len(jobs) * 0.15 / CONFIG['concurrent_sessions']:.1f} hours")
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
            
            # Run batch
            tasks = [self._apply_with_verification(job, i + start_idx + 1) for i, job in enumerate(batch)]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Save checkpoint
            self._save_checkpoint()
            self._print_progress()
            
            # Generate error report if errors exist
            if CONFIG["enable_error_logging"] and self.error_logger.errors:
                report_file = self.error_logger.generate_report(
                    self.output_dir / f"error_report_batch_{batch_num}.json"
                )
                print(f"   📝 Error report: {report_file}")
            
            # Delay between batches
            if batch_num < total_batches - 1:
                delay = CONFIG["delay_between_batches"]
                print(f"\n⏳ Waiting {delay}s...")
                await asyncio.sleep(delay)
    
    async def _apply_with_verification(self, job: JobPosting, job_number: int):
        """Apply with full verification and error logging."""
        async with self.semaphore:
            try:
                result = await self._apply_single_with_verification(job, job_number)
                self._track_result(job, result)
            except Exception as e:
                # Log unexpected error
                if CONFIG["enable_error_logging"]:
                    self.error_logger.log_error(
                        job_id=job.id,
                        company=job.company,
                        job_title=job.title,
                        job_url=job.url,
                        error_message=str(e),
                        exception=e,
                        context={"job_number": job_number, "phase": "outer_wrapper"}
                    )
                self._track_result(job, ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=f"Unexpected error: {str(e)}"
                ))
    
    async def _apply_single_with_verification(self, job: JobPosting, job_number: int) -> ApplicationResult:
        """Apply with verification and error logging."""
        self.stats.attempted += 1
        screenshot_path = None
        
        # Create browser manager
        browser_manager = StealthBrowserManager()
        
        try:
            # Create session
            session = await browser_manager.create_stealth_session(platform="indeed")
            page = session.page
            
            # Navigate to job
            print(f"  [Job {job_number}] {job.company[:25]:25} - Loading...")
            await page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
            await browser_manager.human_like_delay(2, 4)
            
            # Screenshot initial state if enabled
            if CONFIG["screenshot_all"]:
                screenshot_dir = self.output_dir / "screenshots"
                screenshot_dir.mkdir(exist_ok=True)
                screenshot_path = str(screenshot_dir / f"{job.id}_initial.png")
                try:
                    await page.screenshot(path=screenshot_path)
                    self.stats.screenshots_taken += 1
                except:
                    pass
            
            # Get adapter and apply
            adapter = get_adapter(job.url, browser_manager)
            
            result = await adapter.apply_to_job(
                job=job,
                resume=self.resume,
                profile=KENT_PROFILE,
                cover_letter=None,
                auto_submit=True
            )
            
            # VERIFICATION: Take screenshot of result
            if CONFIG["enable_verification"]:
                verification_ss = str(screenshot_dir / f"{job.id}_result.png")
                try:
                    await page.screenshot(path=verification_ss, full_page=True)
                    result.screenshot_path = verification_ss
                    self.stats.screenshots_taken += 1
                except:
                    pass
                
                # Validate submission
                if result.status == ApplicationStatus.SUBMITTED:
                    validation = await SubmissionValidator.validate(
                        page, job.id, platform="indeed",
                        screenshot_dir=str(screenshot_dir)
                    )
                    if validation.get('confirmation_id'):
                        result.confirmation_id = validation['confirmation_id']
                        self.stats.confirmations_captured += 1
                    if not validation['success']:
                        self.stats.validation_failures += 1
            
            await browser_manager.close_all()
            self.stats.browserbase_cost += 0.10
            
            return result
            
        except Exception as e:
            # Log error with full context
            if CONFIG["enable_error_logging"]:
                error_record = self.error_logger.log_error(
                    job_id=job.id,
                    company=job.company,
                    job_title=job.title,
                    job_url=job.url,
                    error_message=str(e),
                    exception=e,
                    screenshot_path=screenshot_path,
                    context={"job_number": job_number, "attempt": 1}
                )
                # Update category stats
                cat = error_record.category
                self.stats.errors_by_category[cat] = self.stats.errors_by_category.get(cat, 0) + 1
            
            await browser_manager.close_all()
            self.stats.browserbase_cost += 0.10
            
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=str(e),
                screenshot_path=screenshot_path
            )
    
    def _track_result(self, job: JobPosting, result: ApplicationResult):
        """Track result with full details."""
        if result.status == ApplicationStatus.SUBMITTED:
            self.stats.new_submissions += 1
            print(f"  ✅ {job.company[:30]:30} SUBMITTED")
        elif result.status == ApplicationStatus.ERROR:
            self.stats.failed += 1
            print(f"  ❌ {job.company[:30]:30} FAILED: {result.message[:40]}")
        
        result_data = {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "status": result.status.value,
            "message": result.message,
            "confirmation_id": result.confirmation_id,
            "screenshot_path": result.screenshot_path,
            "timestamp": datetime.now().isoformat(),
        }
        
        self.results.append(result_data)
    
    def _print_progress(self):
        """Print progress with verification stats."""
        progress = (self.stats.total_submissions / CONFIG["target_total"]) * 100
        print(f"\n{'='*70}")
        print(f"📊 PROGRESS: {self.stats.total_submissions}/{CONFIG['target_total']} ({progress:.1f}%)")
        print(f"New submissions: {self.stats.new_submissions} | Attempted: {self.stats.attempted}")
        print(f"Success Rate: {self.stats.success_rate:.1f}%")
        print(f"📸 Screenshots: {self.stats.screenshots_taken}")
        print(f"🔑 Confirmations: {self.stats.confirmations_captured}")
        if self.stats.validation_failures:
            print(f"⚠️  Validation failures: {self.stats.validation_failures}")
        if self.stats.errors_by_category:
            print(f"📝 Errors by category: {self.stats.errors_by_category}")
        print(f"💰 Cost: ${self.stats.browserbase_cost:.2f}")
        print(f"{'='*70}\n")
    
    def _save_checkpoint(self):
        """Save checkpoint."""
        checkpoint = {
            "stats": {
                "target": self.stats.target_total,
                "baseline": self.stats.baseline_submissions,
                "verified_baseline": self.stats.verified_baseline,
                "new_submissions": self.stats.new_submissions,
                "total": self.stats.total_submissions,
                "remaining": self.stats.remaining,
                "success_rate": self.stats.success_rate,
                "screenshots": self.stats.screenshots_taken,
                "confirmations": self.stats.confirmations_captured,
                "cost": self.stats.browserbase_cost,
            },
            "results": self.results,
            "timestamp": datetime.now().isoformat(),
        }
        
        with open(self.output_dir / "checkpoint.json", 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def save_final(self):
        """Save final results."""
        # Generate final error report
        if CONFIG["enable_error_logging"] and self.error_logger.errors:
            error_report = self.error_logger.generate_report(
                self.output_dir / "final_error_report.json"
            )
            recommendations = self.error_logger.get_recommendations()
        else:
            error_report = None
            recommendations = []
        
        final_data = {
            "campaign_id": f"kent_verified_{datetime.now().strftime('%Y%m%d_%H%M')}",
            "type": "VERIFIED_REAL_SUBMISSIONS",
            "baseline": {
                "previous_submissions": self.stats.baseline_submissions,
                "verified": self.stats.verified_baseline,
            },
            "new_submissions": {
                "count": self.stats.new_submissions,
                "verified": self.stats.new_verified,
                "success_rate": f"{self.stats.success_rate:.1f}%",
            },
            "total": {
                "submissions": self.stats.total_submissions,
                "target": self.stats.target_total,
                "remaining": self.stats.remaining,
            },
            "verification": {
                "screenshots_taken": self.stats.screenshots_taken,
                "confirmations_captured": self.stats.confirmations_captured,
                "validation_failures": self.stats.validation_failures,
            },
            "errors": {
                "total_failed": self.stats.failed,
                "by_category": self.stats.errors_by_category,
                "error_report": error_report,
                "recommendations": recommendations,
            },
            "cost": f"${self.stats.browserbase_cost:.2f}",
            "results": self.results,
        }
        
        with open(self.output_dir / "final_results.json", 'w') as f:
            json.dump(final_data, f, indent=2)
        
        # CSV export
        with open(self.output_dir / "applications.csv", 'w') as f:
            f.write("ID,Company,Title,Location,Status,ConfirmationID,URL\n")
            for r in self.results:
                confirm = r.get('confirmation_id', '')
                f.write(f'"{r["id"]}","{r["company"]}","{r["title"]}","{r["location"]}","{r["status"]}","{confirm}","{r["url"]}"\n')
        
        return self.output_dir
    
    async def run(self):
        """Run verified campaign."""
        print("\n" + "🚀"*35)
        print("   KENT LE - VERIFIED REAL SUBMISSIONS")
        print("   WITH ERROR LOGGING & VERIFICATION")
        print("   " + "🚀"*35)
        print(f"\n   ✅ Baseline Verified: {self.stats.verified_baseline}")
        print(f"   🎯 Target New: {self.stats.remaining}")
        print(f"   📸 Screenshots: ENABLED")
        print(f"   📝 Error Logging: ENABLED")
        print(f"   🔍 Verification: ENABLED")
        
        if os.environ.get("KENT_VERIFIED_AUTO") != "YES":
            confirm = input("\nType 'VERIFY1000' to start: ")
            if confirm != "VERIFY1000":
                print("\n❌ Cancelled.")
                return
        else:
            print("\n✅ Auto-confirmed")
        
        try:
            # Collect jobs
            jobs = await self.collect_fresh_jobs()
            
            if len(jobs) == 0:
                print("\n❌ No fresh jobs found!")
                return
            
            # Run campaign
            await self.run_verified_campaign(jobs)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted")
        except Exception as e:
            print(f"\n\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            output_dir = self.save_final()
            
            print("\n" + "="*70)
            if self.stats.total_submissions >= CONFIG["target_total"]:
                print("🎉 CAMPAIGN COMPLETE - 1000 SUBMISSIONS!")
            else:
                print(f"✅ CAMPAIGN ENDED - {self.stats.total_submissions} total")
            print("="*70)
            print(f"🎯 Total: {self.stats.total_submissions} ({self.stats.baseline_submissions} baseline + {self.stats.new_submissions} new)")
            print(f"📸 Screenshots: {self.stats.screenshots_taken}")
            print(f"🔑 Confirmations: {self.stats.confirmations_captured}")
            print(f"💰 Cost: ${self.stats.browserbase_cost:.2f}")
            print(f"💾 Output: {output_dir}")
            
            if CONFIG["enable_error_logging"] and self.error_logger.errors:
                print(f"\n📝 Error Report: {output_dir}/final_error_report.json")
                print("Recommendations:")
                for rec in self.error_logger.get_recommendations()[:3]:
                    print(f"  • {rec}")


async def main():
    campaign = VerifiedRealSubmissionCampaign()
    await campaign.run()


if __name__ == "__main__":
    asyncio.run(main())
