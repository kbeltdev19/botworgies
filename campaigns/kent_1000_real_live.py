#!/usr/bin/env python3
"""
Kent Le - 1000 REAL Applications - PRODUCTION RUN
Live browser automation with CAPTCHA solving and proxy rotation

⚠️  THIS IS REAL - WILL SUBMIT ACTUAL APPLICATIONS
Estimated Cost: $200-350 | Time: 3-5 days
"""

import os
import sys
import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from browser.stealth_manager import StealthBrowserManager
from adapters import (
    JobSpyAdapter, SearchConfig, UserProfile, Resume,
    ApplicationStatus, JobPosting, ApplicationResult,
    get_adapter
)

# Production Configuration
CONFIG = {
    "target": 1000,
    "batch_size": 50,  # Save progress every 50
    "delay_between": (45, 90),  # 45-90 seconds between apps
    "max_retries": 3,
    "captcha_api_key": os.environ.get("CAPTCHA_API_KEY", ""),  # 2captcha
    "use_proxies": True,
    "screenshot_on_success": True,
    "screenshot_on_failure": True,
    "auto_submit": False,  # Safety: stop at review step
}

# Kent's Profile
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
    custom_answers={
        "salary_expectation": "75000",
        "relocation": "Open to remote and hybrid positions nationwide",
        "start_date": "2 weeks notice",
        "languages": "English, Vietnamese (fluent)",
    }
)

RESUME_PATH = "/Users/tech4/Downloads/botworkieslocsl/botworgies/Test Resumes/Kent_Le_Resume.pdf"


@dataclass
class RealStats:
    """Track real application statistics."""
    target: int = 1000
    attempted: int = 0
    submitted: int = 0  # Actually submitted
    external: int = 0   # Redirected to external
    blocked: int = 0    # CAPTCHA/rate limit
    failed: int = 0     # Other errors
    skipped: int = 0    # Skipped due to issues
    
    # Financial tracking
    browserbase_cost: float = 0.0
    captcha_cost: float = 0.0
    proxy_cost: float = 0.0
    
    # Time tracking
    start_time: datetime = None
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now()
    
    @property
    def success_rate(self) -> float:
        return (self.submitted / max(self.attempted, 1)) * 100
    
    @property
    def total_cost(self) -> float:
        return self.browserbase_cost + self.captcha_cost + self.proxy_cost
    
    @property
    def elapsed_hours(self) -> float:
        return (datetime.now() - self.start_time).total_seconds() / 3600
    
    @property
    def apps_per_hour(self) -> float:
        return self.attempted / max(self.elapsed_hours, 0.01)


class Kent1000RealProduction:
    """Production runner for 1000 real applications."""
    
    def __init__(self):
        self.stats = RealStats(target=CONFIG["target"])
        self.browser_manager = StealthBrowserManager()
        self.results: List[Dict] = []
        
        # Output directory
        self.output_dir = Path(__file__).parent / "output" / f"kent_1000_real_live_{datetime.now().strftime('%Y%m%d_%H%M')}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Resume
        self.resume = self._load_resume()
        
        print(f"\n💾 Output directory: {self.output_dir}")
        print(f"📄 Resume: {self.resume.file_path}")
    
    def _load_resume(self) -> Resume:
        """Load Kent's resume."""
        return Resume(
            file_path=RESUME_PATH,
            raw_text="",
            parsed_data={
                "name": "Kent Le",
                "email": "kle4311@gmail.com",
                "phone": "(404) 934-0630",
            }
        )
    
    async def collect_jobs(self) -> List[JobPosting]:
        """Collect real jobs from multiple sources."""
        print("\n" + "="*80)
        print("🔍 PHASE 1: COLLECTING REAL JOBS")
        print("="*80)
        print(f"Target: {self.stats.target * 2} jobs to ensure we can apply to {self.stats.target}")
        
        all_jobs = []
        seen_urls = set()
        
        # Search strategies
        strategies = [
            # Strategy 1: Indeed (high volume, mostly external)
            {
                "adapter": JobSpyAdapter(sites=["indeed"]),
                "searches": [
                    ("Customer Success Manager", ["Remote", "Atlanta, GA"]),
                    ("Account Manager", ["Remote", "Austin, TX"]),
                    ("Sales Representative", ["Atlanta, GA", "Remote"]),
                    ("Business Development Representative", ["Remote"]),
                ]
            },
            # Strategy 2: LinkedIn (quality, rate limited)
            {
                "adapter": JobSpyAdapter(sites=["linkedin"]),
                "searches": [
                    ("Customer Success Manager", ["Remote"]),
                    ("Account Executive", ["Remote", "Atlanta, GA"]),
                ]
            },
            # Strategy 3: ZipRecruiter (volume)
            {
                "adapter": JobSpyAdapter(sites=["zip_recruiter"]),
                "searches": [
                    ("Client Success Manager", ["Remote"]),
                    ("Account Manager", ["Remote"]),
                ]
            },
        ]
        
        for strategy in strategies:
            adapter = strategy["adapter"]
            
            for term, locations in strategy["searches"]:
                if len(all_jobs) >= self.stats.target * 2:
                    break
                
                print(f"\nSearching: {term}...", end=" ", flush=True)
                
                try:
                    for location in locations:
                        criteria = SearchConfig(
                            roles=[term],
                            locations=[location],
                            posted_within_days=7,
                            easy_apply_only=False,
                        )
                        
                        jobs = await adapter.search_jobs(criteria)
                        
                        # Add unique
                        new = 0
                        for job in jobs:
                            if job.url not in seen_urls:
                                seen_urls.add(job.url)
                                all_jobs.append(job)
                                new += 1
                        
                        if new > 0:
                            print(f"+{new} ", end="", flush=True)
                        
                        await asyncio.sleep(2)
                        
                except Exception as e:
                    print(f"Error: {e}")
                    continue
            
            print(f"(total: {len(all_jobs)})")
        
        print(f"\n✅ Collected {len(all_jobs)} unique jobs")
        return all_jobs
    
    async def run_applications(self, jobs: List[JobPosting]):
        """Run real applications."""
        print("\n" + "="*80)
        print("🚀 PHASE 2: RUNNING REAL APPLICATIONS")
        print("="*80)
        print("⚠️  THIS IS REAL - ACTUAL BROWSERS WILL OPEN")
        print("⚠️  ACTUAL FORMS WILL BE FILLED AND SUBMITTED")
        print()
        print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Estimated duration: 50-100 hours")
        print(f"Estimated cost: $200-350")
        print()
        
        # Sort by priority
        jobs = self._prioritize_jobs(jobs)
        
        for i, job in enumerate(jobs[:self.stats.target], 1):
            if self.stats.submitted >= self.stats.target:
                print(f"\n🎉 TARGET REACHED: {self.stats.target} applications submitted!")
                break
            
            print(f"\n{'='*80}")
            print(f"📨 {i}/{min(len(jobs), self.stats.target)}: {job.title}")
            print(f"   Company: {job.company}")
            print(f"   Location: {job.location}")
            print(f"   URL: {job.url}")
            print(f"{'='*80}")
            
            result = await self._apply_single_job(job)
            
            # Track result
            self._track_result(job, result)
            
            # Save checkpoint every batch
            if i % CONFIG["batch_size"] == 0:
                self._save_checkpoint()
                self._print_progress()
            
            # Delay between applications
            if i < len(jobs):
                delay = random.uniform(*CONFIG["delay_between"])
                print(f"\n⏳ Waiting {delay:.0f}s...")
                await asyncio.sleep(delay)
        
        # Final cleanup
        await self.browser_manager.close_all()
    
    def _prioritize_jobs(self, jobs: List[JobPosting]) -> List[JobPosting]:
        """Prioritize jobs for application."""
        scored = []
        
        for job in jobs:
            score = 0
            
            # Easy Apply preferred
            if job.easy_apply:
                score += 50
            
            # Remote preferred
            if job.remote or "remote" in job.location.lower():
                score += 40
            
            # Good salary
            if job.salary_range and any(x in job.salary_range for x in ['80000', '90000', '100000']):
                score += 30
            
            # Title relevance
            title = job.title.lower()
            if "customer success" in title:
                score += 25
            elif "account manager" in title:
                score += 20
            elif "sales" in title:
                score += 15
            
            scored.append((job, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [j for j, _ in scored]
    
    async def _apply_single_job(self, job: JobPosting) -> ApplicationResult:
        """Apply to a single job with real browser automation."""
        self.stats.attempted += 1
        
        try:
            # Get adapter
            adapter = get_adapter(job.url, self.browser_manager)
            
            print(f"   🌐 Platform: {adapter.platform.value}")
            print(f"   ⏳ Opening browser...")
            
            # Track costs
            self.stats.browserbase_cost += 0.10  # Per session
            
            # Apply
            result = await adapter.apply_to_job(
                job=job,
                resume=self.resume,
                profile=KENT_PROFILE,
                cover_letter=None,
                auto_submit=CONFIG["auto_submit"]
            )
            
            # Screenshot if needed
            if (result.status == ApplicationStatus.SUBMITTED and CONFIG["screenshot_on_success"]) or \
               (result.status != ApplicationStatus.SUBMITTED and CONFIG["screenshot_on_failure"]):
                # Would capture screenshot here
                pass
            
            return result
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if "captcha" in error_msg:
                self.stats.captcha_cost += 0.50
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=f"CAPTCHA blocked: {e}"
                )
            elif "rate" in error_msg or "block" in error_msg:
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=f"Rate limited: {e}"
                )
            else:
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=str(e)
                )
    
    def _track_result(self, job: JobPosting, result: ApplicationResult):
        """Track application result."""
        # Update stats
        if result.status == ApplicationStatus.SUBMITTED:
            self.stats.submitted += 1
            print(f"   ✅ SUBMITTED: {result.message}")
        elif result.status == ApplicationStatus.EXTERNAL_APPLICATION:
            self.stats.external += 1
            print(f"   🔗 EXTERNAL: {result.message}")
        elif result.status == ApplicationStatus.ERROR:
            if "captcha" in result.message.lower():
                self.stats.blocked += 1
                print(f"   🚫 CAPTCHA: {result.message}")
            else:
                self.stats.failed += 1
                print(f"   ❌ FAILED: {result.message}")
        
        # Record
        self.results.append({
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "platform": job.platform.value,
            "status": result.status.value,
            "message": result.message,
            "confirmation_id": result.confirmation_id,
            "timestamp": datetime.now().isoformat(),
        })
    
    def _print_progress(self):
        """Print progress."""
        print(f"\n{'='*80}")
        print(f"📊 PROGRESS")
        print(f"{'='*80}")
        print(f"Attempted: {self.stats.attempted} | Submitted: {self.stats.submitted} | Rate: {self.stats.success_rate:.1f}%")
        print(f"External: {self.stats.external} | Blocked: {self.stats.blocked} | Failed: {self.stats.failed}")
        print(f"Cost: ${self.stats.total_cost:.2f} | Time: {self.stats.elapsed_hours:.1f}h | Speed: {self.stats.apps_per_hour:.1f}/hr")
        print(f"ETA: {(self.stats.target - self.stats.submitted) / max(self.stats.apps_per_hour, 1):.1f} hours remaining")
        print(f"{'='*80}\n")
    
    def _save_checkpoint(self):
        """Save checkpoint."""
        checkpoint = {
            "stats": {
                "target": self.stats.target,
                "attempted": self.stats.attempted,
                "submitted": self.stats.submitted,
                "external": self.stats.external,
                "blocked": self.stats.blocked,
                "failed": self.stats.failed,
                "success_rate": self.stats.success_rate,
                "total_cost": self.stats.total_cost,
                "elapsed_hours": self.stats.elapsed_hours,
            },
            "results": self.results,
            "timestamp": datetime.now().isoformat(),
        }
        
        checkpoint_file = self.output_dir / "checkpoint.json"
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def save_final(self):
        """Save final results."""
        final_data = {
            "campaign_id": f"kent_1000_real_{datetime.now().strftime('%Y%m%d_%H%M')}",
            "type": "REAL_APPLICATIONS_PRODUCTION",
            "candidate": {
                "name": "Kent Le",
                "email": "kle4311@gmail.com",
                "phone": "(404) 934-0630",
            },
            "stats": {
                "target": self.stats.target,
                "attempted": self.stats.attempted,
                "submitted": self.stats.submitted,
                "external": self.stats.external,
                "blocked": self.stats.blocked,
                "failed": self.stats.failed,
                "success_rate": f"{self.stats.success_rate:.1f}%",
                "total_cost": f"${self.stats.total_cost:.2f}",
                "elapsed_hours": f"{self.stats.elapsed_hours:.1f}",
            },
            "results": self.results,
            "completed_at": datetime.now().isoformat(),
        }
        
        # JSON
        json_file = self.output_dir / "final_results.json"
        with open(json_file, 'w') as f:
            json.dump(final_data, f, indent=2)
        
        # CSV
        csv_file = self.output_dir / "applications.csv"
        with open(csv_file, 'w') as f:
            f.write("ID,Company,Title,Location,Status,ConfirmationID,URL\n")
            for r in self.results:
                conf_id = r.get("confirmation_id", "")
                line = f'"{r["id"]}","{r["company"]}","{r["title"]}","{r["location"]}","{r["status"]}","{conf_id}","{r["url"]}"\n'
                f.write(line)
        
        return json_file, csv_file
    
    def print_final(self, json_file, csv_file):
        """Print final report."""
        print("\n" + "="*80)
        print("✅ CAMPAIGN COMPLETE - REAL APPLICATIONS")
        print("="*80)
        print(f"\n📊 FINAL STATISTICS")
        print(f"   Target: {self.stats.target}")
        print(f"   Attempted: {self.stats.attempted}")
        print(f"   ✅ Submitted: {self.stats.submitted}")
        print(f"   🔗 External: {self.stats.external}")
        print(f"   🚫 Blocked: {self.stats.blocked}")
        print(f"   ❌ Failed: {self.stats.failed}")
        print(f"\n📈 Success Rate: {self.stats.success_rate:.1f}%")
        print(f"💰 Total Cost: ${self.stats.total_cost:.2f}")
        print(f"⏱️  Total Time: {self.stats.elapsed_hours:.1f} hours")
        print(f"\n📁 Files:")
        print(f"   JSON: {json_file}")
        print(f"   CSV: {csv_file}")
        print("="*80)
    
    async def run(self):
        """Run complete campaign."""
        print("\n" + "🚀"*40)
        print("   KENT LE - 1000 REAL APPLICATIONS")
        print("   PRODUCTION RUN")
        print("   " + "🚀"*40)
        
        print("\n⚠️  FINAL CONFIRMATION:")
        print("   This will submit REAL job applications using:")
        print("   • BrowserBase cloud browsers ($0.10/session)")
        print("   • Your resume and profile")
        print("   • Real form filling on company websites")
        print(f"   • Estimated cost: $200-350")
        print(f"   • Estimated time: 3-5 days")
        
        # Check for auto-confirm flag
        if os.environ.get("KENT_1000_AUTO_CONFIRM") == "YES":
            print("\n✅ Auto-confirmed via environment variable")
            confirm = "RUN1000"
        else:
            confirm = input("\nType 'RUN1000' to start: ")
        
        if confirm != "RUN1000":
            print("\n❌ Cancelled.")
            return
        
        try:
            # Collect jobs
            jobs = await self.collect_jobs()
            
            if len(jobs) < self.stats.target:
                print(f"\n⚠️  Only found {len(jobs)} jobs")
                proceed = input("Proceed with available jobs? (yes/no): ")
                if proceed != "yes":
                    return
                self.stats.target = len(jobs)
            
            # Run applications
            await self.run_applications(jobs)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
        except Exception as e:
            print(f"\n\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Save final
            json_file, csv_file = self.save_final()
            self.print_final(json_file, csv_file)


async def main():
    runner = Kent1000RealProduction()
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
