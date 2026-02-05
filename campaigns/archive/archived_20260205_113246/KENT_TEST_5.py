#!/usr/bin/env python3
"""
KENT LE - TEST 5 REAL APPLICATIONS
Test run before full 1000
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

print("🧹 Cleaning up...")
os.system("pkill -9 -f 'python.*campaign\|playwright' 2>/dev/null")

print("\n" + "="*70)
print("🧪 KENT LE - TEST 5 REAL APPLICATIONS")
print("="*70)
print("⚠️  THIS WILL SUBMIT 5 ACTUAL JOB APPLICATIONS!")
print("="*70)

# Load jobs
jobs_file = Path(__file__).parent / "kent_le_real_jobs_1000.json"
with open(jobs_file) as f:
    data = json.load(f)
    all_jobs = data.get('jobs', [])

print(f"📋 Loaded {len(all_jobs)} total jobs")
print(f"🎯 Will test with: 5 jobs")
print("\n⚠️  Press Ctrl+C in 5 seconds to cancel...")

import time
try:
    for i in range(5, 0, -1):
        print(f"  {i}...", end='\r')
        time.sleep(1)
    print("\n🚀 Starting test!          ")
except KeyboardInterrupt:
    print("\n❌ Cancelled")
    sys.exit(0)

async def test_apply():
    from ats_automation import ATSRouter
    from ats_automation.models import UserProfile
    
    db_path = Path(__file__).parent.parent / 'data' / 'job_applier.db'
    
    profile = UserProfile(
        first_name="Kent",
        last_name="Le",
        email="kle4311@gmail.com",
        phone="404-934-0630",
        resume_path="Test Resumes/Kent_Le_Resume.pdf"
    )
    
    print(f"\n👤 Profile: {profile.first_name} {profile.last_name}")
    print(f"📧 Email: {profile.email}")
    
    print("\nInitializing ATSRouter...")
    router = ATSRouter(profile)
    print("✅ Router ready")
    
    # Test with first 5 jobs
    test_jobs = all_jobs[:5]
    
    print(f"\n📝 Testing {len(test_jobs)} applications:\n")
    
    for i, job in enumerate(test_jobs, 1):
        print(f"[{i}/5] {job['company'][:20]:20} | {job['title'][:35]}")
        print(f"      URL: {job['url'][:60]}...")
        
        try:
            result = await router.apply(job['url'])
            print(f"      Result: {'✅ SUCCESS' if result.success else '❌ FAILED'} - {result.status}")
            if result.error_message:
                print(f"      Error: {result.error_message[:60]}")
            print()
            
            # Rate limiting
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"      ❌ EXCEPTION: {str(e)[:60]}")
            print()
    
    await router.cleanup()
    print("✅ Test complete!")

asyncio.run(test_apply())
