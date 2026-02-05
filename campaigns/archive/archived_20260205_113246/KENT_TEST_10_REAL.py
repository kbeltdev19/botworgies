#!/usr/bin/env python3
"""
KENT LE - TEST 10 REAL JOB APPLICATIONS
Production test with verified job URLs
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
print("🧹 Cleaning up zombie processes...")
os.system("pkill -9 -f 'python.*campaign\|playwright' 2>/dev/null")

print("\n" + "="*70)
print("🧪 KENT LE - TEST 10 REAL JOB APPLICATIONS")
print("="*70)
print("⚠️  THIS WILL SUBMIT 10 ACTUAL JOB APPLICATIONS!")
print("="*70)
print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Load test jobs
jobs_file = Path(__file__).parent / "kent_test_10_jobs.json"
with open(jobs_file) as f:
    data = json.load(f)
    test_jobs = data.get('jobs', [])[:10]

print(f"📋 Loaded {len(test_jobs)} test jobs")
print(f"👤 Candidate: Kent Le (kle4311@gmail.com)")
print(f"📄 Resume: Test Resumes/Kent_Le_Resume.pdf")
print()

# Show jobs
print("Jobs to apply to:")
for i, job in enumerate(test_jobs, 1):
    icon = "💼" if job['platform'] == 'workday' else "🌱" if job['platform'] == 'greenhouse' else "🔗"
    print(f"  {i}. {icon} {job['company'][:15]:15} | {job['title'][:35]}")

print()
print("⚠️  WARNING: This will submit ACTUAL applications!")
print("⚠️  Confirmation emails will be sent to kle4311@gmail.com")
print()
print("Press Ctrl+C in 10 seconds to cancel...")

import time
try:
    for i in range(10, 0, -1):
        print(f"  Starting in {i}...", end='\r')
        time.sleep(1)
    print("\n🚀 Starting test applications!          ")
except KeyboardInterrupt:
    print("\n❌ Cancelled by user")
    sys.exit(0)

# Results tracking
results = []

def log_result(job, success, error=None):
    """Log result to database"""
    db_path = Path(__file__).parent.parent / 'data' / 'job_applier.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO applications 
        (id, user_id, job_url, job_title, company, platform, status, error, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        f"kent_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(results)}",
        "kent-le-user",
        job['url'],
        job['title'],
        job['company'],
        job.get('platform', 'unknown'),
        'submitted' if success else 'failed',
        error
    ))
    conn.commit()
    conn.close()

async def run_test():
    from ats_automation import ATSRouter
    from ats_automation.models import UserProfile
    from campaigns.duplicate_checker import DuplicateChecker
    
    # Create profile
    profile = UserProfile(
        first_name="Kent",
        last_name="Le",
        email="kle4311@gmail.com",
        phone="404-934-0630",
        resume_path="Test Resumes/Kent_Le_Resume.pdf"
    )
    
    print(f"\n🔄 Initializing ATSRouter...")
    router = ATSRouter(profile)
    checker = DuplicateChecker()
    print("✅ Router ready\n")
    
    print("="*70)
    print("📝 PROCESSING APPLICATIONS")
    print("="*70)
    
    for i, job in enumerate(test_jobs, 1):
        print(f"\n[{i}/10] {job['company'][:20]:20} | {job['title'][:35]}")
        print(f"      Platform: {job.get('platform', 'unknown')}")
        print(f"      URL: {job['url'][:60]}...")
        
        # Check duplicate
        if checker.is_already_applied("kle4311@gmail.com", job['url']):
            print(f"      ⏭️  SKIPPED (already applied)")
            results.append({'job': job, 'status': 'skipped', 'error': None})
            continue
        
        try:
            # Submit application
            result = await router.apply(job['url'])
            
            if result.success:
                print(f"      ✅ SUCCESS - {result.status}")
                if result.confirmation_number:
                    print(f"      🎫 Confirmation: {result.confirmation_number}")
                results.append({'job': job, 'status': 'success', 'error': None})
                checker.record_application("kle4311@gmail.com", job['url'], "kent_test")
                log_result(job, True)
            else:
                print(f"      ❌ FAILED - {result.status}")
                if result.error_message:
                    print(f"      📝 Error: {result.error_message[:60]}")
                results.append({'job': job, 'status': 'failed', 'error': result.error_message})
                log_result(job, False, result.error_message)
            
        except Exception as e:
            print(f"      ❌ EXCEPTION: {str(e)[:60]}")
            results.append({'job': job, 'status': 'exception', 'error': str(e)})
            log_result(job, False, str(e))
        
        # Rate limiting between applications
        if i < len(test_jobs):
            print(f"      ⏱️  Waiting 5 seconds...")
            await asyncio.sleep(5)
    
    # Cleanup
    await router.cleanup()
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST RESULTS SUMMARY")
    print("="*70)
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = sum(1 for r in results if r['status'] == 'failed')
    exception_count = sum(1 for r in results if r['status'] == 'exception')
    skipped_count = sum(1 for r in results if r['status'] == 'skipped')
    
    print(f"Total: {len(results)}")
    print(f"  ✅ Success:     {success_count}")
    print(f"  ❌ Failed:      {failed_count}")
    print(f"  💥 Exceptions:  {exception_count}")
    print(f"  ⏭️  Skipped:    {skipped_count}")
    
    if success_count > 0:
        print(f"\n📧 Kent should receive {success_count} confirmation email(s)!")
        print("   Check kle4311@gmail.com (including spam folder)")
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETE")
    print("="*70)

# Run
asyncio.run(run_test())
