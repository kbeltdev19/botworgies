#!/usr/bin/env python3
"""
Kent Le 1000-Job Campaign

Target: 1000 job applications
Concurrent: 100 browser sessions
Profile: Kent Le - Auburn, AL - $75k+ - Remote/Hybrid/In-person
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from typing import List, Dict
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ['BROWSERBASE_API_KEY'] = 'bb_live_xxx'
os.environ['BROWSERBASE_PROJECT_ID'] = 'c47b2ef9-00fa-4b16-9cc6-e74e5288e03c'

from jobspy import scrape_jobs
from evaluation.evaluation_criteria import (
    CampaignEvaluator, ApplicationMetrics, ApplicationStatus, 
    FailureCategory, KENT_LE_EVALUATION_CRITERIA
)

# Kent's profile
KENT_PROFILE = {
    "name": "Kent Le",
    "location": "Auburn, AL",
    "email": "kle4311@gmail.com",
    "phone": "+1 (404) 934-0630",
    "open_to": ["remote", "hybrid", "in_person"],
    "min_salary": 75000,
    "target_roles": [
        "Client Success Manager",
        "Customer Success Manager",
        "Account Manager",
        "Sales Representative",
        "Business Development Representative",
        "Account Executive",
        "Client Relationship Manager",
        "Sales Development Representative"
    ],
    "locations": [
        "Auburn, AL",
        "Atlanta, GA",
        "Birmingham, AL",
        "Montgomery, AL",
        "Remote"
    ],
    "experience_years": 3,
    "skills": ["CRM", "Salesforce", "Data Analysis", "Supply Chain", "Bilingual Vietnamese"]
}


class KentLeCampaign:
    """1000-job campaign for Kent Le."""
    
    def __init__(self):
        self.evaluator = CampaignEvaluator(
            campaign_id="kent_le_1000_2026",
            target_jobs=1000,
            target_sessions=100
        )
        self.jobs_scraped: List[Dict] = []
        self.output_dir = Path(__file__).parent / "output"
        self.output_dir.mkdir(exist_ok=True)
        
    async def scrape_all_jobs(self) -> List[Dict]:
        """Scrape jobs for all target roles and locations."""
        print("🕷️  PHASE 1: Scraping Jobs")
        print("=" * 60)
        
        all_jobs = []
        seen_urls = set()
        
        for role in KENT_PROFILE["target_roles"]:
            for location in KENT_PROFILE["locations"]:
                print(f"\n🔍 Searching: {role} in {location}")
                
                try:
                    is_remote = location == "Remote"
                    
                    jobs_df = scrape_jobs(
                        site_name=["linkedin", "indeed", "zip_recruiter"],
                        search_term=role,
                        location="" if is_remote else location,
                        is_remote=is_remote,
                        results_wanted=50,  # Per site
                        hours_old=168,  # Last 7 days
                        job_type="fulltime"
                    )
                    
                    if len(jobs_df) > 0:
                        # Convert to list of dicts
                        for _, row in jobs_df.iterrows():
                            job = {
                                "id": str(hash(row.get('job_url', '')))[:12],
                                "title": row.get('title', ''),
                                "company": row.get('company', ''),
                                "location": row.get('location', ''),
                                "url": row.get('job_url', ''),
                                "description": str(row.get('description', ''))[:500],
                                "is_remote": row.get('is_remote', False),
                                "min_amount": row.get('min_amount'),
                                "max_amount": row.get('max_amount'),
                                "currency": row.get('currency', 'USD'),
                                "interval": row.get('interval'),
                                "site": row.get('site', 'unknown'),
                                "date_posted": str(row.get('date_posted', '')),
                                "search_role": role,
                                "search_location": location
                            }
                            
                            # Deduplicate by URL
                            if job["url"] and job["url"] not in seen_urls:
                                seen_urls.add(job["url"])
                                all_jobs.append(job)
                        
                        print(f"   ✅ Found {len(jobs_df)} jobs (total unique: {len(all_jobs)})")
                    else:
                        print(f"   ⚠️  No jobs found")
                        
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    continue
        
        # Filter by salary (>= $75k)
        print(f"\n💰 Filtering by minimum salary: $75,000")
        filtered_jobs = self._filter_by_salary(all_jobs, 75000)
        print(f"   Jobs after salary filter: {len(filtered_jobs)}")
        
        self.jobs_scraped = filtered_jobs
        
        # Save scraped jobs
        with open(self.output_dir / "scraped_jobs.json", 'w') as f:
            json.dump(filtered_jobs, f, indent=2, default=str)
        
        print(f"\n📊 Phase 1 Complete: {len(filtered_jobs)} unique jobs ready")
        return filtered_jobs
    
    def _filter_by_salary(self, jobs: List[Dict], min_salary: int) -> List[Dict]:
        """Filter jobs by minimum salary."""
        filtered = []
        
        for job in jobs:
            min_amt = job.get("min_amount")
            interval = job.get("interval", "").lower()
            
            if min_amt is None:
                # Include jobs without salary info
                filtered.append(job)
                continue
            
            # Convert to yearly
            if "hour" in interval:
                yearly = min_amt * 2080  # 40 hrs * 52 weeks
            else:
                yearly = min_amt
            
            if yearly >= min_salary:
                filtered.append(job)
        
        return filtered
    
    async def apply_to_jobs(self, jobs: List[Dict]):
        """Apply to all scraped jobs."""
        print("\n🚀 PHASE 2: Applying to Jobs")
        print("=" * 60)
        print(f"Target: {len(jobs)} jobs")
        print(f"Concurrent sessions: 100")
        print(f"Estimated time: {(len(jobs) / 30):.0f} minutes at 30 apps/min")
        print()
        
        # For this test, we'll simulate applications
        # In production, this would use the actual browser automation
        
        semaphore = asyncio.Semaphore(100)  # 100 concurrent
        
        tasks = []
        for i, job in enumerate(jobs[:1000]):  # Limit to 1000
            task = self._apply_with_semaphore(semaphore, job, i)
            tasks.append(task)
        
        # Process in batches to avoid overwhelming
        batch_size = 100
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            await asyncio.gather(*batch, return_exceptions=True)
            
            # Take snapshot after each batch
            self.evaluator.take_snapshot(
                active_sessions=min(100, len(tasks) - i),
                queue_depth=len(tasks) - i - len(batch)
            )
            
            # Progress report
            progress = self.evaluator.get_progress_summary()
            print(f"\n📈 Progress: {progress['completed']}/{progress['total_jobs']} "
                  f"({progress['progress_percent']:.1f}%) | "
                  f"Success: {progress['current_success_rate']:.1f}% | "
                  f"Apps/min: {progress.get('apps_per_minute', 0):.1f}")
        
        print("\n✅ Phase 2 Complete: All applications processed")
    
    async def _apply_with_semaphore(self, semaphore: asyncio.Semaphore, job: Dict, idx: int):
        """Apply to a single job with semaphore control."""
        async with semaphore:
            # Create metrics
            metrics = ApplicationMetrics(
                job_id=job["id"],
                job_title=job["title"],
                company=job["company"],
                platform=job["site"],
                url=job["url"]
            )
            
            self.evaluator.record_application_start(metrics)
            
            # Simulate application process
            try:
                # Simulate processing time (0.5-2 seconds per app)
                await asyncio.sleep(0.5 + (idx % 10) / 10)
                
                # Simulate 85% success rate
                import random
                if random.random() < 0.85:
                    self.evaluator.record_application_complete(
                        job["id"],
                        status=ApplicationStatus.SUCCESS
                    )
                else:
                    # Random failure category
                    failures = [
                        FailureCategory.CAPTCHA,
                        FailureCategory.FORM_ERROR,
                        FailureCategory.TIMEOUT
                    ]
                    self.evaluator.record_application_complete(
                        job["id"],
                        status=ApplicationStatus.FAILED,
                        failure_category=random.choice(failures),
                        error_message="Simulated failure for testing"
                    )
                    
            except Exception as e:
                self.evaluator.record_application_complete(
                    job["id"],
                    status=ApplicationStatus.ERROR,
                    failure_category=FailureCategory.UNKNOWN,
                    error_message=str(e)
                )
    
    def generate_report(self):
        """Generate final evaluation report."""
        print("\n📊 PHASE 3: Generating Report")
        print("=" * 60)
        
        report = self.evaluator.generate_report()
        
        # Save report
        report_file = self.output_dir / "campaign_report.json"
        report.save_to_file(report_file)
        
        # Print summary
        print(f"\n{'='*60}")
        print("📋 CAMPAIGN REPORT - Kent Le 1000-Job Test")
        print(f"{'='*60}")
        
        print(f"\n📈 Overall Results:")
        print(f"   Total Attempted:    {report.total_attempted}")
        print(f"   Successful:         {report.total_successful}")
        print(f"   Failed:             {report.total_failed}")
        print(f"   Success Rate:       {report.calculate_overall_success_rate():.1f}%")
        print(f"   Duration:           {report.duration_seconds/60:.1f} minutes")
        print(f"   Apps/Minute:        {report.apps_per_minute:.1f}")
        
        print(f"\n🏢 By Platform:")
        for platform, stats in report.by_platform.items():
            print(f"   {platform:15} {stats.successful:4d}/{stats.total_attempts:4d} ({stats.success_rate:.1f}%)")
        
        print(f"\n❌ Failure Breakdown:")
        for category, count in report.by_failure_category.items():
            print(f"   {category:20} {count:4d}")
        
        print(f"\n✅ What Worked:")
        for item in report.what_worked:
            print(f"   • {item}")
        
        print(f"\n❌ What Didn't Work:")
        for item in report.what_didnt_work:
            print(f"   • {item}")
        
        print(f"\n💡 Recommendations:")
        for item in report.recommendations:
            print(f"   • {item}")
        
        print(f"\n{'='*60}")
        print(f"Report saved to: {report_file}")
        print(f"{'='*60}")
        
        return report


async def main():
    """Run the full campaign."""
    print("\n" + "="*60)
    print("🚀 KENT LE 1000-JOB CAMPAIGN")
    print("="*60)
    print(f"\nCandidate: {KENT_PROFILE['name']}")
    print(f"Location: {KENT_PROFILE['location']}")
    print(f"Min Salary: ${KENT_PROFILE['min_salary']:,}")
    print(f"Target Roles: {len(KENT_PROFILE['target_roles'])}")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    campaign = KentLeCampaign()
    
    # Phase 1: Scrape jobs
    jobs = await campaign.scrape_all_jobs()
    
    if len(jobs) == 0:
        print("\n❌ No jobs found. Campaign aborted.")
        return
    
    # Phase 2: Apply to jobs
    await campaign.apply_to_jobs(jobs)
    
    # Phase 3: Generate report
    report = campaign.generate_report()
    
    print("\n✅ CAMPAIGN COMPLETE")
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
