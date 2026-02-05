#!/usr/bin/env python3
"""
KENT LE - PRODUCTION REAL APPLICATIONS
Uses Dice.com Easy Apply for genuine job applications
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
print("🚀 KENT LE - REAL JOB APPLICATIONS (PRODUCTION)")
print("="*70)
print("⚠️  THIS WILL ACTUALLY SUBMIT JOB APPLICATIONS!")
print("="*70)
print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Configuration
MAX_APPLICATIONS = 100
CONCURRENT_LIMIT = 3  # Conservative for BrowserBase
RATE_LIMIT_DELAY = 5  # Seconds between applications

print(f"🎯 Target: {MAX_APPLICATIONS} REAL applications")
print(f"🔧 Concurrent: {CONCURRENT_LIMIT}")
print(f"⏱️  Rate limit: {RATE_LIMIT_DELAY}s between apps")
print()

# WARNING
print("⚠️  ⚠️  ⚠️  WARNING  ⚠️  ⚠️  ⚠️")
print("This will submit ACTUAL job applications to Dice.com")
print("You WILL receive confirmation emails at kle4311@gmail.com")
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

async def run_production():
    from ats_automation import ATSRouter
    from ats_automation.models import UserProfile
    from campaigns.duplicate_checker import DuplicateChecker
    
    # Create proper UserProfile
    profile = UserProfile(
        first_name="Kent",
        last_name="Le",
        email="kle4311@gmail.com",
        phone="404-934-0630",
        resume_path="Test Resumes/Kent_Le_Resume.pdf",
        resume_text=""  # Will be extracted by handlers
    )
    
    print(f"\n👤 Profile: {profile.first_name} {profile.last_name}")
    print(f"📧 Email: {profile.email}")
    print(f"📄 Resume: {profile.resume_path}")
    print()
    
    router = ATSRouter(profile)
    checker = DuplicateChecker()
    
    # Search terms for Dice
    search_queries = [
        ("Customer Success Manager", "Remote"),
        ("Account Manager", "Remote"),
        ("Sales Representative", "Remote"),
        ("Client Success Manager", "United States"),
        ("Business Development Representative", "Remote"),
        ("Account Executive", "Remote"),
        ("Sales Development Representative", "United States"),
    ]
    
    start_time = datetime.now()
    total_submitted = 0
    total_failed = 0
    total_skipped = 0
    
    for query, location in search_queries:
        if total_submitted >= MAX_APPLICATIONS:
            break
        
        remaining = MAX_APPLICATIONS - total_submitted
        to_search = min(20, remaining * 2)  # Get more since not all are Easy Apply
        
        print(f"\n🔍 Searching: '{query}' in {location}")
        print(f"   Looking for {to_search} jobs...")
        
        try:
            # Search and apply using Dice Easy Apply
            results = await router.search_and_apply_dice(
                query=query,
                location=location,
                remote=True,
                max_jobs=min(remaining, 15)  # Cap per search
            )
            
            for result in results:
                if isinstance(result, Exception):
                    total_failed += 1
                    print(f"   ❌ ERROR: {str(result)[:50]}")
                    continue
                
                if result.success:
                    total_submitted += 1
                    print(f"   ✅ SUBMITTED: {result.job_id[:40]}...")
                    
                    # Record in duplicate checker
                    checker.record_application(
                        "kle4311@gmail.com", 
                        result.job_url, 
                        "kent_dice_production"
                    )
                    
                    # Rate limiting
                    await asyncio.sleep(RATE_LIMIT_DELAY)
                else:
                    total_failed += 1
                    print(f"   ❌ FAILED: {result.status}")
                
                if total_submitted >= MAX_APPLICATIONS:
                    break
                    
        except Exception as e:
            print(f"   ❌ Search error: {e}")
            continue
        
        # Progress report
        elapsed = (datetime.now() - start_time).total_seconds() / 60
        print(f"\n📊 Progress: {total_submitted}/{MAX_APPLICATIONS} submitted")
        print(f"   Elapsed: {elapsed:.1f} min | Failed: {total_failed}")
    
    # Cleanup
    await router.cleanup()
    
    # Final report
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60
    
    print("\n" + "="*70)
    print("✅ CAMPAIGN COMPLETE")
    print("="*70)
    print(f"✅ Submitted: {total_submitted}")
    print(f"❌ Failed: {total_failed}")
    print(f"⏱️  Duration: {duration:.1f} minutes")
    print(f"📈 Rate: {total_submitted/duration:.1f} apps/min" if duration > 0 else "")
    print("="*70)
    print("\n📧 Check kle4311@gmail.com for confirmation emails!")
    print("   (including spam folder)")

# Run
asyncio.run(run_production())
