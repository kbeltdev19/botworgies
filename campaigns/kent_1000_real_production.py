#!/usr/bin/env python3
"""
Kent Le - 1000 REAL Applications Production Run
Actual browser automation with Playwright + BrowserBase

⚠️  WARNING: This will take 50-100+ hours and cost real money for BrowserBase sessions
"""

import os
import sys
import asyncio
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from browser.stealth_manager import StealthBrowserManager
from adapters import (
    JobSpyAdapter, SearchConfig, UserProfile, Resume,
    ApplicationStatus, JobPosting, ApplicationResult,
    get_adapter
)

# Configuration
BATCH_SIZE = 10  # Process in small batches to avoid overwhelming
DELAY_BETWEEN_APPS = (30, 60)  # 30-60 seconds between applications
BROWSERBASE_COST_PER_SESSION = 0.10  # Approximate cost per session
MAX_RETRIES = 3

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
        "start_date": "2 weeks notice",
    }
)

RESUME_PATH = "/Users/tech4/Downloads/botworkieslocsl/botworgies/Test Resumes/Kent_Le_Resume.pdf"


class RealApplicationRunner:
    """Run REAL applications with actual browser automation."""
    
    def __init__(self, target: int = 1000):
        self.target = target
        self.browser_manager = StealthBrowserManager()
        
        self.output_dir = Path(__file__).parent / "output" / f"kent_1000_real_{datetime.now().strftime('%Y%m%d_%H%M')}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats = {
            "target": target,
            "attempted": 0,
            "successful": 0,
            "failed": 0,
            "external": 0,  # Redirected to external site
            "blocked": 0,   # CAPTCHA/rate limit
            "error": 0,
            "by_platform": {},
            "start_time": datetime.now().isoformat(),
            "estimated_cost": 0.0,
        }
        
        self.results = []
        
    async def discover_real_jobs(self) -> List[JobPosting]:
        """Discover real jobs using JobSpy."""
        print("\n" + "="*80)
        print("🔍 DISCOVERING REAL JOBS")
        print("="*80)
        print(f"\nTarget: Collect {self.target * 2} jobs to ensure we can apply to {self.target}")
        print("Sources: Indeed, LinkedIn, ZipRecruiter")
        print("\nThis uses real APIs and returns actual job listings.\n")
        
        all_jobs = []
        seen_urls = set()
        
        adapter = JobSpyAdapter(sites=["indeed"])  # Start with Indeed
        
        search_terms = [
            ("Customer Success Manager", "Remote"),
            ("Account Manager", "Remote"),
            ("Sales Representative", "Atlanta, GA"),
            ("Business Development Representative", "Remote"),
            ("Client Success Manager", "Remote"),
        ]
        
        for term, location in search_terms:
            if len(all_jobs) >= self.target * 2:
                break
                
            print(f"Searching: {term} in {location}...", end=" ", flush=True)
            
            try:
                criteria = SearchConfig(
                    roles=[term],
                    locations=[location],
                    posted_within_days=7,
                    easy_apply_only=False,
                )
                
                jobs = await adapter.search_jobs(criteria)
                
                # Add unique jobs
                new_count = 0
                for job in jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        all_jobs.append(job)
                        new_count += 1
                
                print(f"Found {new_count} new (total: {len(all_jobs)})")
                
                await asyncio.sleep(2)  # Rate limiting
                
            except Exception as e:
                print(f"Error: {e}")
                continue
        
        print(f"\n✅ Discovered {len(all_jobs)} real jobs")
        return all_jobs[:self.target]
    
    async def run_real_applications(self, jobs: List[JobPosting]):
        """Run REAL applications with browser automation."""
        print("\n" + "="*80)
        print("🚀 RUNNING REAL APPLICATIONS")
        print("="*80)
        print(f"\n⚠️  WARNING: This is REAL browser automation")
        print("   • Actual browsers will open")
        print("   • Real forms will be filled")
        print("   • Real applications will be submitted")
        print("   • This will take many hours")
        print(f"   • Estimated cost: ${len(jobs) * BROWSERBASE_COST_PER_SESSION:.2f} in BrowserBase sessions")
        print()
        
        # Load resume
        resume = Resume(
            file_path=RESUME_PATH,
            raw_text="",
            parsed_data={
                "name": "Kent Le",
                "email": "kle4311@gmail.com",
                "phone": "(404) 934-0630",
            }
        )
        
        for i, job in enumerate(jobs, 1):
            if self.stats["successful"] >= self.target:
                print(f"\n🎉 TARGET REACHED: {self.target} successful applications!")
                break
            
            print(f"\n{'='*80}")
            print(f"📨 Application {i}/{len(jobs)}: {job.title} @ {job.company}")
            print(f"{'='*80}")
            print(f"Location: {job.location}")
            print(f"URL: {job.url}")
            print(f"Easy Apply: {job.easy_apply}")
            
            result = await self._apply_with_retry(job, resume, KENT_PROFILE)
            
            # Record result
            self._record_result(job, result)
            
            # Update stats
            self.stats["attempted"] += 1
            self.stats["estimated_cost"] += BROWSERBASE_COST_PER_SESSION
            
            if result.status == ApplicationStatus.SUBMITTED:
                self.stats["successful"] += 1
                print(f"✅ SUCCESS: {result.message}")
                if result.confirmation_id:
                    print(f"   Confirmation: {result.confirmation_id}")
            elif result.status == ApplicationStatus.EXTERNAL_APPLICATION:
                self.stats["external"] += 1
                print(f"🔗 EXTERNAL: {result.message}")
            elif result.status == ApplicationStatus.ERROR:
                if "captcha" in result.message.lower() or "blocked" in result.message.lower():
                    self.stats["blocked"] += 1
                    print(f"🚫 BLOCKED: {result.message}")
                else:
                    self.stats["error"] += 1
                    print(f"❌ ERROR: {result.message}")
            
            # Progress update
            if i % 5 == 0:
                self._print_progress()
                self._save_checkpoint()
            
            # Delay between applications
            if i < len(jobs):
                delay = random.uniform(*DELAY_BETWEEN_APPS)
                print(f"\n⏳ Waiting {delay:.0f}s before next application...")
                await asyncio.sleep(delay)
        
        await self.browser_manager.close_all()
    
    async def _apply_with_retry(self, job: JobPosting, resume: Resume, profile: UserProfile) -> ApplicationResult:
        """Apply with retry logic."""
        for attempt in range(MAX_RETRIES):
            try:
                return await self._apply_single_job(job, resume, profile)
            except Exception as e:
                error_msg = str(e).lower()
                if "captcha" in error_msg or "blocked" in error_msg:
                    return ApplicationResult(
                        status=ApplicationStatus.ERROR,
                        message=f"Blocked by CAPTCHA or rate limit: {e}"
                    )
                
                if attempt < MAX_RETRIES - 1:
                    print(f"  ⚠️  Attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(10)
                else:
                    return ApplicationResult(
                        status=ApplicationStatus.ERROR,
                        message=str(e)
                    )
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Max retries exceeded"
        )
    
    async def _apply_single_job(self, job: JobPosting, resume: Resume, profile: UserProfile) -> ApplicationResult:
        """Apply to a single job with REAL browser automation."""
        try:
            # Get appropriate adapter
            adapter = get_adapter(job.url, self.browser_manager)
            platform = adapter.platform.value
            
            # Update platform stats
            if platform not in self.stats["by_platform"]:
                self.stats["by_platform"][platform] = {"attempted": 0, "successful": 0}
            self.stats["by_platform"][platform]["attempted"] += 1
            
            print(f"\n  🌐 Platform: {platform}")
            print(f"  ⏳ Opening browser session...")
            
            # Apply using real browser automation
            result = await adapter.apply_to_job(
                job=job,
                resume=resume,
                profile=profile,
                cover_letter=None,
                auto_submit=False  # Manual review for safety
            )
            
            # Update platform success
            if result.status == ApplicationStatus.SUBMITTED:
                self.stats["by_platform"][platform]["successful"] += 1
            
            return result
            
        except Exception as e:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=str(e)
            )
    
    def _record_result(self, job: JobPosting, result: ApplicationResult):
        """Record application result."""
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
            "submitted_at": result.submitted_at.isoformat() if result.submitted_at else None,
            "timestamp": datetime.now().isoformat(),
        })
    
    def _print_progress(self):
        """Print progress update."""
        elapsed = (datetime.now() - datetime.fromisoformat(self.stats["start_time"])).total_seconds() / 60
        success_rate = (self.stats["successful"] / max(self.stats["attempted"], 1)) * 100
        
        print(f"\n{'='*80}")
        print(f"📊 PROGRESS UPDATE")
        print(f"{'='*80}")
        print(f"Attempted: {self.stats['attempted']} | Successful: {self.stats['successful']} | Rate: {success_rate:.1f}%")
        print(f"External: {self.stats['external']} | Blocked: {self.stats['blocked']} | Errors: {self.stats['error']}")
        print(f"Elapsed: {elapsed:.1f} min | Cost: ${self.stats['estimated_cost']:.2f}")
        print(f"ETA: {(self.target - self.stats['successful']) * 5:.0f} minutes remaining")
        print(f"{'='*80}\n")
    
    def _save_checkpoint(self):
        """Save progress checkpoint."""
        checkpoint_file = self.output_dir / "checkpoint.json"
        
        data = {
            "stats": self.stats,
            "results": self.results,
            "timestamp": datetime.now().isoformat(),
        }
        
        with open(checkpoint_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def save_final_results(self):
        """Save final campaign results."""
        self.stats["end_time"] = datetime.now().isoformat()
        
        # Calculate duration
        start = datetime.fromisoformat(self.stats["start_time"])
        end = datetime.fromisoformat(self.stats["end_time"])
        duration_hours = (end - start).total_seconds() / 3600
        
        final_data = {
            "campaign_id": f"kent_1000_real_{datetime.now().strftime('%Y%m%d_%H%M')}",
            "type": "REAL_APPLICATIONS",
            "candidate": {
                "name": "Kent Le",
                "email": "kle4311@gmail.com",
                "phone": "(404) 934-0630",
                "location": "Auburn, AL",
                "target_salary": "$75,000+",
            },
            "stats": {
                **self.stats,
                "duration_hours": duration_hours,
                "final_success_rate": f"{(self.stats['successful'] / max(self.stats['attempted'], 1) * 100):.1f}%",
            },
            "results": self.results,
        }
        
        results_file = self.output_dir / "real_application_results.json"
        with open(results_file, 'w') as f:
            json.dump(final_data, f, indent=2)
        
        # CSV export
        csv_file = self.output_dir / "applications.csv"
        with open(csv_file, 'w') as f:
            f.write("ID,Company,Title,Location,Status,ConfirmationID,URL\n")
            for r in self.results:
                f.write(f'"{r[\"id\"]}\",\"{r[\"company\"]}\",\"{r[\"title\"]}\",\"{r[\"location\"]}\",\"{r[\"status\"]}\",\"{r[\"confirmation_id\"] or \"\"}\",\"{r[\"url\"]}\"\n')
        
        return results_file, csv_file
    
    def print_final_report(self, results_file, csv_file):
        """Print final report."""
        print("\n" + "="*80)
        print("📊 FINAL REPORT - REAL APPLICATIONS")
        print("="*80)
        print(f"\n🎯 TARGET: {self.target} applications")
        print(f"✅ ATTEMPTED: {self.stats['attempted']}")
        print(f"🎉 SUCCESSFUL: {self.stats['successful']}")
        print(f"🔗 EXTERNAL: {self.stats['external']}")
        print(f"🚫 BLOCKED: {self.stats['blocked']}")
        print(f"❌ ERRORS: {self.stats['error']}")
        
        if self.stats["attempted"] > 0:
            rate = (self.stats["successful"] / self.stats["attempted"]) * 100
            print(f"\n📈 SUCCESS RATE: {rate:.1f}%")
        
        print(f"\n💰 ESTIMATED COST: ${self.stats['estimated_cost']:.2f}")
        
        print(f"\n📁 OUTPUT FILES:")
        print(f"   JSON: {results_file}")
        print(f"   CSV: {csv_file}")
        print(f"   Dir: {self.output_dir}")
        
        print("\n🏢 BY PLATFORM:")
        for platform, stats in self.stats["by_platform"].items():
            success_rate = (stats.get("successful", 0) / max(stats["attempted"], 1)) * 100
            print(f"   {platform}: {stats['successful']}/{stats['attempted']} ({success_rate:.0f}%)")
        
        print("="*80)
    
    async def run(self):
        """Run the complete campaign."""
        print("\n" + "🚀"*40)
        print("   KENT LE - 1000 REAL APPLICATIONS")
        print("   Actual Browser Automation")
        print("   " + "🚀"*40)
        
        print("\n⚠️  IMPORTANT NOTICES:")
        print("   • This will open REAL browser windows")
        print("   • This will submit REAL applications")
        print("   • This costs REAL money (BrowserBase sessions)")
        print("   • This will take MANY HOURS")
        print("   • Sites may block/rate-limit you")
        print()
        
        confirm = input("Type 'YES' to proceed with REAL applications: ")
        if confirm != "YES":
            print("\n❌ Cancelled. No applications were submitted.")
            return
        
        try:
            # Discover jobs
            jobs = await self.discover_real_jobs()
            
            if len(jobs) < self.target:
                print(f"\n⚠️  Only found {len(jobs)} jobs, adjusting target")
                self.target = len(jobs)
            
            # Run applications
            await self.run_real_applications(jobs[:self.target])
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
        except Exception as e:
            print(f"\n\n❌ Campaign error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup
            await self.browser_manager.close_all()
            
            # Save results
            results_file, csv_file = self.save_final_results()
            self.print_final_report(results_file, csv_file)


async def main():
    """Main entry."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Kent Le - 1000 REAL Applications')
    parser.add_argument('--target', type=int, default=1000, help='Number of applications')
    parser.add_argument('--test', action='store_true', help='Test mode (5 applications)')
    args = parser.parse_args()
    
    target = 5 if args.test else args.target
    
    runner = RealApplicationRunner(target=target)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
