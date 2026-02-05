#!/usr/bin/env python3
"""
KENT LE - FAST CAMPAIGN (10+ jobs/min)
Optimized for speed with 35 concurrent sessions
"""

import sys
import os
from pathlib import Path

# Load environment
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
from datetime import datetime
from typing import List, Dict

from ats_automation import ATSRouter, UserProfile, ApplicationResult
from ats_automation.browserbase_manager import BrowserBaseManager
from campaigns.duplicate_checker import DuplicateChecker, CampaignTracker

# Kent's Profile
KENT_PROFILE = UserProfile(
    first_name="Kent",
    last_name="Le",
    email="kle4311@gmail.com",
    phone="404-934-0630",
    resume_path="Test Resumes/Kent_Le_Resume.pdf",
    resume_text="""KENT LE
Auburn, Alabama | 404-934-0630 | kle4311@gmail.com

PROFESSIONAL SUMMARY
Results-driven Customer Success professional with 5+ years of experience building client relationships, driving product adoption, and reducing churn. Proven track record of increasing customer satisfaction scores by 25% and growing account revenue by 30% year-over-year.

WORK EXPERIENCE
Senior Customer Success Manager | TechCorp Inc. | 2021-Present
• Manage portfolio of 50+ enterprise accounts worth $5M+ in ARR
• Achieved 95% customer retention rate through proactive engagement
• Increased average contract value by 35% through strategic upselling

Account Manager | CloudSolutions LLC | 2019-2021
• Supported 75+ mid-market accounts in SaaS technology sector
• Exceeded quarterly revenue targets by 120% on average

EDUCATION
Bachelor of Business Administration | Auburn University | 2018
""",
    linkedin_url="https://linkedin.com/in/kentle",
    salary_expectation="$75,000 - $95,000",
    years_experience=5,
    skills=["Customer Success", "Account Management", "Salesforce", "HubSpot", "CRM", "Retention"],
    custom_answers={
        "salary_expectations": "$75,000 - $95,000",
        "willing_to_relocate": "No - prefer remote or Auburn, AL area",
        "authorized_to_work": "Yes - US Citizen"
    }
)


class FastCampaignRunner:
    """Optimized for 10+ jobs/min with 35 concurrent sessions"""
    
    def __init__(self, profile: UserProfile):
        self.profile = profile
        self.results: List[ApplicationResult] = []
        self.start_time: datetime = None
        self.checker = DuplicateChecker()
        
    async def run_fast_campaign(
        self,
        job_urls: List[str],
        concurrent: int = 35,
        target_rate: float = 10.0  # jobs per minute
    ) -> Dict:
        """Run optimized fast campaign"""
        
        self.start_time = datetime.now()
        total_jobs = len(job_urls)
        
        print("\n" + "="*70)
        print("🚀 KENT LE - FAST CAMPAIGN (Optimized for 10+ jobs/min)")
        print("="*70)
        print(f"Total Jobs: {total_jobs}")
        print(f"Concurrent Sessions: {concurrent}")
        print(f"Target Rate: {target_rate} jobs/min")
        print(f"Est. Duration: {total_jobs/target_rate:.0f} minutes")
        print(f"Started: {self.start_time.strftime('%H:%M:%S')}")
        print("="*70 + "\n")
        
        # Process with semaphore for concurrency
        semaphore = asyncio.Semaphore(concurrent)
        completed = 0
        last_progress_time = self.start_time
        
        async def process_job(url: str, index: int):
            nonlocal completed, last_progress_time
            
            async with semaphore:
                start = datetime.now()
                
                try:
                    # Quick duplicate check
                    if self.checker.is_already_applied("kle4311@gmail.com", url):
                        return {"status": "skipped", "reason": "already_applied"}
                    
                    # Fast timeout - skip slow jobs
                    router = ATSRouter(self.profile)
                    
                    try:
                        result = await asyncio.wait_for(
                            router.apply(url),
                            timeout=30.0  # 30 second max per job
                        )
                    except asyncio.TimeoutError:
                        result = ApplicationResult(
                            success=False,
                            platform=None,
                            job_id=url,
                            job_url=url,
                            status="timeout",
                            error_message="Processing timeout (30s)"
                        )
                    
                    self.results.append(result)
                    
                    if result.success:
                        self.checker.record_application(
                            "kle4311@gmail.com", url, "kent_fast_campaign"
                        )
                    
                    completed += 1
                    
                    # Progress every 35 jobs (1 batch)
                    if completed % 35 == 0:
                        elapsed = (datetime.now() - self.start_time).total_seconds() / 60
                        current_rate = completed / elapsed if elapsed > 0 else 0
                        eta_mins = (total_jobs - completed) / current_rate if current_rate > 0 else 0
                        
                        print(f"📊 [{completed:4d}/{total_jobs}] Rate: {current_rate:5.1f}/min | "
                              f"ETA: {eta_mins:4.0f}min | {datetime.now().strftime('%H:%M:%S')}")
                    
                    return result
                    
                except Exception as e:
                    error_result = ApplicationResult(
                        success=False,
                        platform=None,
                        job_id=url,
                        job_url=url,
                        status="error",
                        error_message=str(e)[:50]
                    )
                    self.results.append(error_result)
                    completed += 1
                    return error_result
                finally:
                    if 'router' in locals():
                        await router.cleanup()
        
        # Create and run tasks in batches for better control
        batch_size = 35
        for batch_start in range(0, total_jobs, batch_size):
            batch_end = min(batch_start + batch_size, total_jobs)
            batch = job_urls[batch_start:batch_end]
            
            tasks = [process_job(url, i) for i, url in enumerate(batch, batch_start)]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Brief pause between batches to prevent overload
            await asyncio.sleep(0.5)
        
        end_time = datetime.now()
        duration_mins = (end_time - self.start_time).total_seconds() / 60
        actual_rate = total_jobs / duration_mins if duration_mins > 0 else 0
        
        # Generate report
        successful = sum(1 for r in self.results if r.success)
        failed = total_jobs - successful
        
        report = {
            "campaign_id": f"kent_fast_{self.start_time.strftime('%Y%m%d_%H%M')}",
            "total_jobs": total_jobs,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total_jobs * 100) if total_jobs > 0 else 0,
            "duration_minutes": duration_mins,
            "actual_rate_jobs_per_min": actual_rate,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        # Save report
        report_path = f"ats_automation/testing/test_results/{report['campaign_id']}_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print("\n" + "="*70)
        print("✅ CAMPAIGN COMPLETE")
        print("="*70)
        print(f"Total: {total_jobs}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {report['success_rate']:.1f}%")
        print(f"Duration: {duration_mins:.1f} minutes")
        print(f"Actual Rate: {actual_rate:.1f} jobs/min")
        print(f"Target Rate: {target_rate:.1f} jobs/min")
        print(f"Status: {'✅ HIT TARGET' if actual_rate >= target_rate else '⚠️ BELOW TARGET'}")
        print(f"Report: {report_path}")
        print("="*70)
        
        return report


async def main():
    """Run fast campaign"""
    # Load remaining jobs (skip first 122 already processed)
    job_file = Path("ats_automation/testing/job_urls_1000.txt")
    with open(job_file) as f:
        all_urls = [line.strip() for line in f if line.strip()]
    
    # Skip first 122 already processed
    remaining_urls = all_urls[122:1000]
    
    print(f"📋 Loading {len(remaining_urls)} remaining jobs (skipped 122 already processed)")
    
    # Run fast campaign
    runner = FastCampaignRunner(KENT_PROFILE)
    report = await runner.run_fast_campaign(
        job_urls=remaining_urls,
        concurrent=35,  # 35 concurrent for optimal speed/stability
        target_rate=10.0
    )
    
    return report


if __name__ == "__main__":
    asyncio.run(main())
