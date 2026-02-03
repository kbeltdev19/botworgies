"""
Test improvements with 100-job batch

Compare performance:
- Before: 95.5% success, 57 min for 1000 jobs
- Target: 98%+ success, <25 min for 1000 jobs
"""

import sys
import os
from pathlib import Path
from datetime import datetime

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

from ats_automation import ATSRouter, UserProfile, ApplicationResult
from ats_automation.browserbase_manager import BrowserBaseManager
import asyncio
from typing import List, Dict
import json


# Kent Le's Profile (simplified for test)
KENT_LE_PROFILE = UserProfile(
    first_name="Kent",
    last_name="Le",
    email="kle4311@gmail.com",
    phone="404-934-0630",
    resume_path="Test Resumes/Kent_Le_Resume.pdf",
    resume_text="Kent Le - Customer Success Professional with 5+ years experience.",
    salary_expectation="$75,000 - $95,000",
    years_experience=5,
)


async def test_100_jobs():
    """Test improvements with 100 jobs"""
    
    # Load 100 job URLs
    with open("ats_automation/testing/job_urls_1000.txt") as f:
        job_urls = [line.strip() for line in f if line.strip()][:100]
    
    print("\n" + "="*80)
    print("🧪 TESTING IMPROVEMENTS - 100 JOB BATCH")
    print("="*80)
    print(f"Jobs: 100")
    print(f"Target Success Rate: 98%+")
    print(f"Target Time: <3 minutes")
    print("="*80 + "\n")
    
    start_time = datetime.now()
    results = []
    
    # Process with improved handlers
    semaphore = asyncio.Semaphore(20)  # 20 concurrent
    
    async def process_job(url: str, index: int):
        async with semaphore:
            try:
                print(f"[{index+1}/100] {url[:50]}...", end=" ")
                router = ATSRouter(KENT_LE_PROFILE)
                result = await router.apply(url)
                await router.cleanup()
                
                status_emoji = "✅" if result.status in ['redirect', 'external_redirect'] else "⚠️" if result.status == 'manual_required' else "❌"
                print(f"{status_emoji} {result.platform.value if result.platform else 'unknown'} - {result.status}")
                
                return result
            except Exception as e:
                print(f"❌ Error: {e}")
                return ApplicationResult(
                    success=False,
                    platform=None,
                    job_id=url,
                    job_url=url,
                    status="exception",
                    error_message=str(e)
                )
    
    # Run all tasks
    tasks = [process_job(url, i) for i, url in enumerate(job_urls)]
    results = await asyncio.gather(*tasks)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Analyze results
    successful = sum(1 for r in results if r.success)
    redirects = sum(1 for r in results if r.status in ['redirect', 'external_redirect'])
    manual = sum(1 for r in results if r.status == 'manual_required')
    failed = 100 - successful - redirects - manual
    
    # Platform breakdown
    platforms = {}
    for r in results:
        p = r.platform.value if r.platform else 'unknown'
        if p not in platforms:
            platforms[p] = {'total': 0, 'success': 0}
        platforms[p]['total'] += 1
        if r.status in ['redirect', 'external_redirect']:
            platforms[p]['success'] += 1
    
    # Status breakdown
    statuses = {}
    for r in results:
        s = r.status
        statuses[s] = statuses.get(s, 0) + 1
    
    # Print report
    print("\n" + "="*80)
    print("📊 TEST RESULTS")
    print("="*80)
    print(f"Total Jobs: 100")
    print(f"Successful: {successful}")
    print(f"External Redirects: {redirects}")
    print(f"Manual Required: {manual}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {((successful + redirects) / 100) * 100:.1f}%")
    print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"Avg Time/Job: {duration/100:.1f} seconds")
    
    print(f"\n📈 Platform Breakdown:")
    for platform, stats in platforms.items():
        rate = (stats['success'] / stats['total']) * 100 if stats['total'] else 0
        print(f"  {platform}: {stats['success']}/{stats['total']} ({rate:.1f}%)")
    
    print(f"\n📋 Status Breakdown:")
    for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")
    
    print("\n" + "="*80)
    
    # Compare with baseline
    print("\n📊 COMPARISON WITH BASELINE:")
    print(f"  Success Rate: {((successful + redirects) / 100) * 100:.1f}% (baseline: 95.5%)")
    print(f"  Duration: {duration/60:.1f} min for 100 jobs (baseline: 5.7 min for 100 jobs)")
    print(f"  Avg Time/Job: {duration/100:.1f}s (baseline: 3.4s)")
    
    if ((successful + redirects) / 100) >= 0.98:
        print("\n✅ SUCCESS RATE TARGET MET!")
    else:
        print("\n⚠️ Success rate below 98% target")
    
    if duration <= 180:  # 3 minutes
        print("✅ TIME TARGET MET!")
    else:
        print("⚠️ Time over 3 minute target")
    
    print("="*80)
    
    # Save results
    report = {
        "test_id": f"improvements_test_100_{datetime.now().strftime('%Y%m%d_%H%M')}",
        "total_jobs": 100,
        "successful": successful,
        "redirects": redirects,
        "manual_required": manual,
        "failed": failed,
        "success_rate": ((successful + redirects) / 100) * 100,
        "duration_seconds": duration,
        "avg_time_per_job": duration / 100,
        "platforms": platforms,
        "statuses": statuses
    }
    
    with open("ats_automation/testing/test_results/improvements_test_100_report.json", 'w') as f:
        json.dump(report, f, indent=2)
    
    return report


if __name__ == "__main__":
    asyncio.run(test_100_jobs())
