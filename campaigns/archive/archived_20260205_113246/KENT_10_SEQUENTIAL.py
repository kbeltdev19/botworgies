#!/usr/bin/env python3
"""
KENT LE - 10 REAL APPLICATIONS (SEQUENTIAL WITH TIMEOUTS)
"""

import sys
import os
import asyncio
import json
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

# Cleanup
os.system("pkill -9 -f 'playwright' 2>/dev/null")

print("="*70)
print("🚀 KENT LE - 10 REAL JOB APPLICATIONS")
print("="*70)
print("⚠️  THIS WILL SUBMIT ACTUAL JOB APPLICATIONS!")
print("="*70)

# Load jobs
jobs_file = Path(__file__).parent / "kent_test_10_jobs.json"
with open(jobs_file) as f:
    data = json.load(f)
    test_jobs = data.get('jobs', [])[:10]

print(f"\n📋 Jobs: {len(test_jobs)}")
print(f"👤 Kent Le (kle4311@gmail.com)")
print()

# 5 second warning
print("Starting in 5 seconds... (Ctrl+C to cancel)")
import time
try:
    time.sleep(5)
except KeyboardInterrupt:
    print("\n❌ Cancelled")
    sys.exit(0)

async def apply_with_timeout(router, job, timeout=90):
    """Apply with timeout protection"""
    try:
        result = await asyncio.wait_for(
            router.apply(job['url']),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        from ats_automation.models import ApplicationResult, ATSPlatform
        return ApplicationResult(
            success=False,
            platform=ATSPlatform.UNKNOWN,
            job_id=job['url'],
            job_url=job['url'],
            status='timeout',
            error_message='Application timed out after 90 seconds'
        )

async def main():
    from ats_automation import ATSRouter
    from ats_automation.models import UserProfile
    
    profile = UserProfile(
        first_name="Kent",
        last_name="Le",
        email="kle4311@gmail.com",
        phone="404-934-0630",
        resume_path="Test Resumes/Kent_Le_Resume.pdf"
    )
    
    print("\nInitializing...")
    router = ATSRouter(profile)
    print("✅ Ready\n")
    
    results = []
    start_time = datetime.now()
    
    for i, job in enumerate(test_jobs, 1):
        print(f"[{i:2d}/10] {job['company'][:18]:18} | {job['title'][:32]:32}")
        print(f"       {job['url'][:65]}...")
        
        try:
            result = await apply_with_timeout(router, job, timeout=90)
            
            if result.success:
                print(f"       ✅ SUCCESS - {result.status}")
                results.append({'job': job, 'status': 'success', 'error': None})
            else:
                print(f"       ❌ {result.status}")
                if result.error_message:
                    print(f"          {result.error_message[:50]}")
                results.append({'job': job, 'status': result.status, 'error': result.error_message})
                
        except Exception as e:
            print(f"       💥 EXCEPTION: {str(e)[:50]}")
            results.append({'job': job, 'status': 'exception', 'error': str(e)})
        
        # Rate limiting
        if i < len(test_jobs):
            await asyncio.sleep(3)
        print()
    
    await router.cleanup()
    
    # Summary
    duration = (datetime.now() - start_time).total_seconds() / 60
    success = sum(1 for r in results if r['status'] == 'success')
    
    print("="*70)
    print("📊 RESULTS")
    print("="*70)
    print(f"Total: {len(results)}")
    print(f"✅ Success: {success}")
    print(f"❌ Failed: {len(results) - success}")
    print(f"⏱️  Duration: {duration:.1f} min")
    
    if success > 0:
        print(f"\n📧 Check kle4311@gmail.com for {success} confirmation email(s)!")
    
    print("\n✅ TEST COMPLETE")

asyncio.run(main())
