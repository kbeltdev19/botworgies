#!/usr/bin/env python3
"""
Kent Le - 1000 REAL Applications - CONCURRENT VERSION
Multiple parallel browser sessions for faster processing

Concurrent Sessions: 20 (default)
Estimated Time: 5-10 hours (vs 50-100 sequential)
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

# Concurrent Configuration
CONFIG = {
    "target_submissions": 1000,  # Target: 1000 SUBMISSIONS (not attempts)
    "target_jobs_multiplier": 6,  # Collect 6x jobs to get enough submissions
    "concurrent_sessions": 20,  # Number of parallel browser sessions
    "batch_size": 50,
    "delay_between_batches": 30,  # Seconds between batches
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
class ConcurrentStats:
    """Track concurrent application statistics."""
    target_submissions: int = 1000
    target_attempts: int = 6000  # ~6k attempts needed for 1k submissions at 20% rate
    attempted: int = 0
    submitted: int = 0
    external: int = 0
    blocked: int = 0
    failed: int = 0
    
    # Financial
    browserbase_cost: float = 0.0
    
    # Time tracking
    start_time: datetime = field(default_factory=datetime.now)
    
    # Concurrency
    active_sessions: int = 0
    max_concurrent: int = CONFIG["concurrent_sessions"]
    
    @property
    def success_rate(self) -> float:
        return (self.submitted / max(self.attempted, 1)) * 100
    
    @property
    def submissions_remaining(self) -> int:
        return max(0, self.target_submissions - self.submitted)
    
    @property
    def elapsed_hours(self) -> float:
        return (datetime.now() - self.start_time).total_seconds() / 3600


class ConcurrentApplicationRunner:
    """Run applications with concurrent browser sessions."""
    
    def __init__(self):
        self.stats = ConcurrentStats()
        self.results: List[Dict] = []
        self.semaphore = asyncio.Semaphore(CONFIG["concurrent_sessions"])
        
        self.output_dir = Path(__file__).parent / "output" / f"kent_1000_concurrent_{datetime.now().strftime('%Y%m%d_%H%M')}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.resume = Resume(
            file_path=RESUME_PATH,
            raw_text="",
            parsed_data={"name": "Kent Le", "email": "kle4311@gmail.com"}
        )
        
        print(f"💾 Output: {self.output_dir}")
        print(f"🔄 Concurrent Sessions: {CONFIG['concurrent_sessions']}")
    
    async def _search_single(self, adapter, term: str, location: str, seen_urls: set) -> List[JobPosting]:
        """Run a single search query."""
        try:
            criteria = SearchConfig(
                roles=[term],
                locations=[location],
                posted_within_days=14,
                easy_apply_only=False,
            )
            
            jobs = await adapter.search_jobs(criteria)
            
            # Filter out duplicates
            new_jobs = [j for j in jobs if j.url not in seen_urls]
            return new_jobs
            
        except Exception as e:
            return []
    
    async def collect_jobs(self, min_jobs: int = None) -> List[JobPosting]:
        """Collect jobs in parallel from multiple sources."""
        print("\n" + "="*70)
        print("🔍 COLLECTING JOBS (PARALLEL MODE)")
        print("="*70)
        print(f"Target: {CONFIG['target_submissions']} submissions")
        print(f"Estimated jobs needed: ~{CONFIG['target_submissions'] * CONFIG['target_jobs_multiplier']}")
        
        all_jobs = []
        seen_urls = set()
        
        # Multi-platform adapters for broader coverage
        # Note: LinkedIn disabled due to aggressive rate limiting
        adapters_config = [
            ("indeed", ["indeed"]),
            # ("linkedin", ["linkedin"]),  # Disabled - 429 rate limit errors
            # ("ziprecruiter", ["ziprecruiter"]),  # Can enable if needed
        ]
        
        # Expanded search queries with more variations
        search_terms = [
            ("Customer Success Manager", ["Remote", "Atlanta, GA", "Austin, TX", "New York, NY", "Chicago, IL", "Denver, CO"]),
            ("Account Manager", ["Remote", "Atlanta, GA", "Austin, TX", "Chicago, IL", "Boston, MA", "Seattle, WA"]),
            ("Sales Representative", ["Atlanta, GA", "Remote", "Dallas, TX", "Houston, TX", "Phoenix, AZ", "Miami, FL"]),
            ("Business Development Representative", ["Remote", "Austin, TX", "Denver, CO", "Salt Lake City, UT"]),
            ("Client Success Manager", ["Remote", "New York, NY", "San Francisco, CA", "Los Angeles, CA"]),
            ("Customer Success Specialist", ["Remote", "Boston, MA", "Seattle, WA", "Portland, OR"]),
            ("Account Executive", ["Remote", "Atlanta, GA", "Miami, FL", "Nashville, TN"]),
            ("Sales Development Representative", ["Remote", "Austin, TX", "Phoenix, AZ", "Raleigh, NC"]),
            ("Customer Success Associate", ["Remote", "New York, NY", "San Francisco, CA"]),
            ("Implementation Manager", ["Remote", "Austin, TX", "Boston, MA"]),
            ("Onboarding Specialist", ["Remote", "Denver, CO", "Atlanta, GA"]),
            ("Technical Account Manager", ["Remote", "Seattle, WA", "San Francisco, CA"]),
        ]
        
        target_jobs = min_jobs or (CONFIG['target_submissions'] * CONFIG['target_jobs_multiplier'])
        
        # Create all search tasks for parallel execution
        search_tasks = []
        adapters = {}
        
        for platform_name, sites in adapters_config:
            try:
                adapter = JobSpyAdapter(sites=sites)
                adapters[platform_name] = adapter
            except Exception as e:
                print(f"  ⚠️  Could not initialize {platform_name}: {e}")
                continue
        
        # If no adapters available, fallback to indeed only
        if not adapters:
            adapters["indeed"] = JobSpyAdapter(sites=["indeed"])
        
        print(f"\n🌐 Active sources: {', '.join(adapters.keys())}")
        print(f"📋 Search queries: {len(search_terms)} terms × multiple locations")
        print("\nStarting parallel job collection...\n")
        
        # Process searches in parallel batches
        batch_size = 20  # 20 concurrent searches at a time
        
        for i in range(0, len(search_terms), batch_size):
            if len(all_jobs) >= target_jobs:
                break
            
            batch_terms = search_terms[i:i+batch_size]
            tasks = []
            task_info = []
            
            for term, locations in batch_terms:
                for location in locations:
                    # Rotate through adapters
                    for platform_name, adapter in adapters.items():
                        task = self._search_single(adapter, term, location, seen_urls)
                        tasks.append(task)
                        task_info.append((term, location, platform_name))
            
            # Run batch concurrently
            print(f"  Batch {i//batch_size + 1}: {len(tasks)} parallel searches...", end=" ", flush=True)
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            batch_new = 0
            for jobs, info in zip(batch_results, task_info):
                if isinstance(jobs, Exception):
                    continue
                for job in jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        all_jobs.append(job)
                        batch_new += 1
            
            if batch_new > 0:
                print(f"+{batch_new} jobs (total: {len(all_jobs)})")
            else:
                print("no new jobs")
            
            # Small delay between batches to be polite
            await asyncio.sleep(1)
        
        print(f"\n✅ Total collected: {len(all_jobs)} unique jobs")
        return all_jobs
    
    async def run_concurrent_applications(self, jobs: List[JobPosting]):
        """Run applications with concurrency until target submissions reached."""
        print("\n" + "="*70)
        print("🚀 RUNNING CONCURRENT APPLICATIONS")
        print("="*70)
        print(f"🎯 TARGET: {CONFIG['target_submissions']} SUBMISSIONS")
        print(f"Concurrent Sessions: {CONFIG['concurrent_sessions']}")
        print(f"Initial Jobs: {len(jobs)}")
        print(f"Estimated Time: 10-15 hours")
        print()
        
        # Sort jobs
        jobs = self._prioritize_jobs(jobs)
        job_queue = list(jobs)  # Copy for processing
        
        batch_num = 0
        
        # Keep processing until we hit target submissions
        while self.stats.submitted < CONFIG['target_submissions'] and job_queue:
            batch_num += 1
            
            # Calculate batch size
            batch_size = min(CONFIG["concurrent_sessions"] * 2, len(job_queue))
            batch = job_queue[:batch_size]
            job_queue = job_queue[batch_size:]  # Remove processed jobs
            
            remaining = CONFIG['target_submissions'] - self.stats.submitted
            print(f"\n📦 Batch {batch_num} | Jobs: {len(batch)} | Submissions needed: {remaining}")
            
            # Run batch concurrently
            tasks = [self._apply_with_semaphore(job, batch_num * batch_size + i + 1) for i, job in enumerate(batch)]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Save checkpoint
            self._save_checkpoint()
            self._print_progress()
            
            # Check if we need more jobs
            if len(job_queue) < 100 and self.stats.submitted < CONFIG['target_submissions']:
                print(f"\n🔍 Running low on jobs ({len(job_queue)} remaining). Collecting more...")
                new_jobs = await self.collect_jobs(min_jobs=500)
                # Filter out already processed URLs
                seen_urls = {r['url'] for r in self.results}
                new_jobs = [j for j in new_jobs if j.url not in seen_urls]
                job_queue.extend(self._prioritize_jobs(new_jobs))
                print(f"✅ Added {len(new_jobs)} new jobs to queue")
            
            # Check if target reached
            if self.stats.submitted >= CONFIG['target_submissions']:
                print(f"\n🎉 TARGET REACHED: {self.stats.submitted} submissions!")
                break
            
            # Delay between batches
            print(f"\n⏳ Batch complete. Waiting {CONFIG['delay_between_batches']}s...")
            await asyncio.sleep(CONFIG['delay_between_batches'])
        
        if self.stats.submitted < CONFIG['target_submissions']:
            print(f"\n⚠️  Ran out of jobs. Submitted: {self.stats.submitted} / Target: {CONFIG['target_submissions']}")
    
    async def _apply_with_semaphore(self, job: JobPosting, job_number: int):
        """Apply with semaphore-controlled concurrency."""
        async with self.semaphore:
            self.stats.active_sessions += 1
            
            try:
                result = await self._apply_single_job(job, job_number)
                self._track_result(job, result)
            except Exception as e:
                self._track_result(job, ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=str(e)
                ))
            finally:
                self.stats.active_sessions -= 1
    
    async def _apply_single_job(self, job: JobPosting, job_number: int) -> ApplicationResult:
        """Apply to single job."""
        self.stats.attempted += 1
        
        try:
            # Create fresh browser manager for each concurrent task
            browser_manager = StealthBrowserManager()
            
            adapter = get_adapter(job.url, browser_manager)
            
            result = await adapter.apply_to_job(
                job=job,
                resume=self.resume,
                profile=KENT_PROFILE,
                cover_letter=None,
                auto_submit=True
            )
            
            await browser_manager.close_all()
            
            self.stats.browserbase_cost += 0.10
            
            return result
            
        except Exception as e:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=str(e)
            )
    
    def _prioritize_jobs(self, jobs: List[JobPosting]) -> List[JobPosting]:
        """Prioritize jobs."""
        scored = []
        
        for job in jobs:
            score = 0
            if job.easy_apply:
                score += 50
            if job.remote or "remote" in job.location.lower():
                score += 40
            if job.salary_range and any(x in job.salary_range for x in ['80000', '90000']):
                score += 30
            
            title = job.title.lower()
            if "customer success" in title:
                score += 25
            elif "account manager" in title:
                score += 20
            
            scored.append((job, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [j for j, _ in scored]
    
    def _track_result(self, job: JobPosting, result: ApplicationResult):
        """Track result with validation details."""
        if result.status == ApplicationStatus.SUBMITTED:
            self.stats.submitted += 1
        elif result.status == ApplicationStatus.EXTERNAL_APPLICATION:
            self.stats.external += 1
        elif result.status == ApplicationStatus.ERROR:
            if "captcha" in result.message.lower():
                self.stats.blocked += 1
            else:
                self.stats.failed += 1
        
        result_data = {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "status": result.status.value,
            "message": result.message,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Add validation info if available
        if result.confirmation_id:
            result_data["confirmation_id"] = result.confirmation_id
        if result.screenshot_path:
            result_data["screenshot_path"] = result.screenshot_path
            
        self.results.append(result_data)
    
    def _print_progress(self):
        """Print progress with validation stats."""
        progress_pct = (self.stats.submitted / CONFIG['target_submissions']) * 100
        
        # Count validated submissions
        validated = sum(1 for r in self.results if r.get('confirmation_id'))
        with_screenshots = sum(1 for r in self.results if r.get('screenshot_path'))
        
        print(f"\n{'='*70}")
        print(f"📊 PROGRESS: {self.stats.submitted}/{CONFIG['target_submissions']} submissions ({progress_pct:.1f}%)")
        print(f"Attempted: {self.stats.attempted} | Success Rate: {self.stats.success_rate:.1f}%")
        print(f"External: {self.stats.external} | Blocked: {self.stats.blocked} | Failed: {self.stats.failed}")
        print(f"Active Sessions: {self.stats.active_sessions}/{CONFIG['concurrent_sessions']}")
        print(f"Cost: ${self.stats.browserbase_cost:.2f} | Time: {self.stats.elapsed_hours:.1f}h")
        if validated > 0 or with_screenshots > 0:
            print(f"✅ Validated: {validated} | 📸 Screenshots: {with_screenshots}")
        print(f"{'='*70}\n")
    
    def _save_checkpoint(self):
        """Save checkpoint."""
        checkpoint_file = self.output_dir / "checkpoint.json"
        
        checkpoint = {
            "stats": {
                "target_submissions": CONFIG['target_submissions'],
                "submissions_remaining": self.stats.submissions_remaining,
                "attempted": self.stats.attempted,
                "submitted": self.stats.submitted,
                "external": self.stats.external,
                "blocked": self.stats.blocked,
                "failed": self.stats.failed,
                "success_rate": self.stats.success_rate,
                "total_cost": self.stats.browserbase_cost,
                "elapsed_hours": self.stats.elapsed_hours,
                "active_sessions": self.stats.active_sessions,
            },
            "results": self.results,
            "timestamp": datetime.now().isoformat(),
        }
        
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def save_final(self):
        """Save final results."""
        final_data = {
            "campaign_id": f"kent_1000_concurrent_{datetime.now().strftime('%Y%m%d_%H%M')}",
            "type": "REAL_APPLICATIONS_1000_SUBMISSIONS",
            "config": CONFIG,
            "candidate": {"name": "Kent Le", "email": "kle4311@gmail.com"},
            "stats": {
                "target_submissions": CONFIG['target_submissions'],
                "submissions_achieved": self.stats.submitted,
                "target_met": self.stats.submitted >= CONFIG['target_submissions'],
                "attempted": self.stats.attempted,
                "submitted": self.stats.submitted,
                "external": self.stats.external,
                "blocked": self.stats.blocked,
                "failed": self.stats.failed,
                "success_rate": f"{self.stats.success_rate:.1f}%",
                "total_cost": f"${self.stats.browserbase_cost:.2f}",
                "elapsed_hours": f"{self.stats.elapsed_hours:.1f}",
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
        """Run campaign until 1000 submissions reached."""
        print("\n" + "🚀"*35)
        print("   KENT LE - 1000 REAL SUBMISSIONS TARGET")
        print("   CONCURRENT MODE - 20 Parallel Sessions")
        print("   " + "🚀"*35)
        print(f"\n   🎯 TARGET: {CONFIG['target_submissions']} SUBMISSIONS")
        print(f"   📊 Est. attempts needed: ~{CONFIG['target_submissions'] * 5}")
        print(f"   💰 Est. cost: ~${CONFIG['target_submissions'] * 5 * 0.10:.0f}")
        print(f"   ⏱️  Est. time: ~12-15 hours")
        
        if os.environ.get("KENT_1000_AUTO_CONFIRM") != "YES":
            confirm = input("\nType 'RUN1000' to start: ")
            if confirm != "RUN1000":
                print("\n❌ Cancelled.")
                return
        else:
            print("\n✅ Auto-confirmed")
        
        try:
            # Collect initial batch of jobs
            jobs = await self.collect_jobs()
            
            if len(jobs) == 0:
                print("\n❌ No jobs found!")
                return
            
            # Run until target submissions reached
            await self.run_concurrent_applications(jobs)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
        except Exception as e:
            print(f"\n\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            json_file, csv_file = self.save_final()
            
            print("\n" + "="*70)
            if self.stats.submitted >= CONFIG['target_submissions']:
                print("🎉 CAMPAIGN COMPLETE - TARGET REACHED!")
            else:
                print("⚠️  CAMPAIGN ENDED - Target not fully reached")
            print("="*70)
            print(f"🎯 Target Submissions: {CONFIG['target_submissions']}")
            print(f"✅ Submissions Made: {self.stats.submitted}")
            print(f"📊 Success Rate: {self.stats.success_rate:.1f}%")
            print(f"💰 Total Cost: ${self.stats.browserbase_cost:.2f}")
            print(f"⏱️  Total Time: {self.stats.elapsed_hours:.1f} hours")
            print(f"💾 Files: {json_file}, {csv_file}")


async def main():
    runner = ConcurrentApplicationRunner()
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
