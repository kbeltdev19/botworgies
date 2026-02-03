#!/usr/bin/env python3
"""
KENT LE - REAL 1000 JOB APPLICATIONS (FIXED VERSION)
Uses correct ATSRouter API (no auto_submit parameter)
"""

import sys
import os
import signal
import asyncio
import json
from pathlib import Path
from datetime import datetime
import time

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

# Kill zombies before starting
print("🧹 Cleaning up zombie processes...")
os.system("pkill -9 -f 'python.*campaign\|playwright' 2>/dev/null")
print("✅ Cleaned up")

print("\n" + "="*70)
print("🚀 KENT LE - REAL 1000 JOB APPLICATIONS (FIXED)")
print("="*70)
print("⚠️  THIS WILL ACTUALLY SUBMIT JOB APPLICATIONS!")
print("="*70)
print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Load jobs
jobs_file = Path(__file__).parent / "kent_le_real_jobs_1000.json"
with open(jobs_file) as f:
    data = json.load(f)
    all_jobs = data.get('jobs', [])

print(f"📋 Loaded {len(all_jobs)} jobs")
print(f"🎯 Will submit: 1000 REAL applications")
print()

# WARNING
print("⚠️  ⚠️  ⚠️  WARNING  ⚠️  ⚠️  ⚠️")
print("This will submit ACTUAL job applications.")
print("You WILL receive confirmation emails.")
print("Press Ctrl+C within 10 seconds to cancel...")
print("⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️\n")

try:
    for i in range(10, 0, -1):
        print(f"Starting in {i}...", end='\r')
        time.sleep(1)
    print("\n🚀 Starting REAL submissions!          ")
except KeyboardInterrupt:
    print("\n\n❌ Cancelled")
    sys.exit(0)

# Now run using the correct API
print("\n" + "="*70)
print("📧 Submitting REAL applications...")
print("="*70 + "\n")

async def run_real_campaign():
    from ats_automation import ATSRouter
    from campaigns.duplicate_checker import DuplicateChecker
    
    # Load profile
    profile = {
        "first_name": "Kent",
        "last_name": "Le",
        "email": "kle4311@gmail.com",
        "phone": "404-934-0630",
        "resume_path": "Test Resumes/Kent_Le_Resume.pdf",
        "location": "Auburn, AL"
    }
    
    router = ATSRouter(profile)
    checker = DuplicateChecker()
    
    jobs = all_jobs[:1000]
    total = len(jobs)
    submitted = 0
    failed = 0
    skipped = 0
    
    start_time = datetime.now()
    
    for i, job in enumerate(jobs, 1):
        # Check for duplicates
        if checker.is_already_applied("kle4311@gmail.com", job['url']):
            skipped += 1
            print(f"[{i:4d}/{total}] ⏭️  SKIPPED (duplicate): {job['title'][:30]} at {job['company'][:20]}")
            continue
        
        print(f"[{i:4d}/{total}] Submitting: {job['title'][:30]} at {job['company'][:20]}...")
        
        try:
            # ⚠️ THIS ACTUALLY SUBMITS THE APPLICATION
            # No auto_submit parameter - controlled by handler internally
            result = await router.apply(job['url'])
            
            if result.success:
                submitted += 1
                checker.record_application("kle4311@gmail.com", job['url'], "kent_real_1000")
                print(f"   ✅ SUBMITTED")
                
                # Rate limiting - be nice to job sites
                await asyncio.sleep(3)
            else:
                failed += 1
                print(f"   ❌ FAILED: {result.error_message[:40] if result.error_message else 'Unknown'}")
                
        except Exception as e:
            failed += 1
            print(f"   ❌ ERROR: {str(e)[:50]}")
        
        # Progress every 50
        if i % 50 == 0:
            elapsed = (datetime.now() - start_time).total_seconds() / 60
            rate = i / elapsed if elapsed > 0 else 0
            print(f"\n📊 Progress: {i}/{total} | Submitted: {submitted} | Rate: {rate:.1f}/min\n")
        
        # Kill zombies periodically
        if i % 100 == 0:
            os.system("pkill -9 -f 'python.*zombie\|playwright.*zombie' 2>/dev/null")
    
    # Cleanup
    await router.cleanup()
    
    # Report
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60
    
    print("\n" + "="*70)
    print("✅ CAMPAIGN COMPLETE")
    print("="*70)
    print(f"Total: {total}")
    print(f"✅ Submitted: {submitted}")
    print(f"❌ Failed: {failed}")
    print(f"⏭️  Duplicates: {skipped}")
    print(f"📈 Success Rate: {(submitted/total*100):.1f}%")
    print(f"⏱️  Duration: {duration:.1f} minutes")
    print("="*70)
    print("\n📧 You should receive confirmation emails!")
    print("   Check kle4311@gmail.com (and spam folder)")

# Run
asyncio.run(run_real_campaign())
