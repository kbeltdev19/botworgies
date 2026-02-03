#!/usr/bin/env python3
"""
KENT LE - 10 REAL APPLICATIONS (OPTIMIZED TEST)
Test run with zombie handling and concurrency
"""

import sys
import os
import asyncio
import json
import sqlite3
import psutil
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

# Config optimized for 10 jobs/minute
CONCURRENT = 5
JOB_TIMEOUT = 45
DELAY_BETWEEN = 6  # seconds = 10 jobs/minute

# =============================================================================
# ZOMBIE KILLER
# =============================================================================
def kill_zombies():
    """Kill stuck Python and browser processes"""
    killed = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name'].lower() if proc.info['name'] else ''
            cmdline = ' '.join(proc.info['cmdline'] or []).lower()
            
            should_kill = False
            if 'python' in name and ('campaign' in cmdline or 'kent' in cmdline):
                should_kill = True
            if 'playwright' in cmdline or 'browserbase' in cmdline:
                should_kill = True
            if name == 'node' and 'cli.js' in cmdline:
                should_kill = True
                
            if should_kill:
                try:
                    proc.kill()
                    killed.append(proc.info['pid'])
                except:
                    pass
        except:
            pass
    return killed

def force_cleanup():
    """Force kill browser processes"""
    os.system("pkill -9 -f 'playwright\|chrome\|chromium' 2>/dev/null")

# =============================================================================
# MAIN
# =============================================================================
print("="*70)
print("🚀 KENT LE - 10 OPTIMIZED REAL APPLICATIONS")
print("="*70)
print(f"⚡ Target: 10 jobs/minute | Concurrent: {CONCURRENT}")
print("="*70)

# Initial cleanup
print("\n🧹 Cleaning up zombies...")
killed = kill_zombies()
if killed:
    print(f"   Killed {len(killed)} processes")
force_cleanup()

# Load jobs
jobs_file = Path(__file__).parent / "kent_test_10_jobs.json"
with open(jobs_file) as f:
    jobs = json.load(f)['jobs'][:10]

print(f"\n📋 {len(jobs)} jobs loaded")
for i, job in enumerate(jobs, 1):
    print(f"   {i}. {job['company'][:15]:15} | {job['title'][:35]}")

print(f"\n⚠️  WARNING: Will submit {len(jobs)} REAL applications!")
print("   Press Ctrl+C in 5 seconds to cancel...")

import time
try:
    time.sleep(5)
except KeyboardInterrupt:
    print("\n❌ Cancelled")
    sys.exit(0)

async def run():
    from ats_automation import ATSRouter
    from ats_automation.models import UserProfile
    from campaigns.duplicate_checker import DuplicateChecker
    
    # Setup
    profile = UserProfile(
        first_name="Kent", last_name="Le",
        email="kle4311@gmail.com", phone="404-934-0630",
        resume_path="Test Resumes/Kent_Le_Resume.pdf"
    )
    
    router = ATSRouter(profile)
    checker = DuplicateChecker()
    
    db_path = Path(__file__).parent.parent / 'data' / 'job_applier.db'
    stats = {'submitted': 0, 'failed': 0, 'skipped': 0}
    
    # Concurrency semaphore
    semaphore = asyncio.Semaphore(CONCURRENT)
    start = datetime.now()
    
    async def process_one(job, idx):
        async with semaphore:
            # Duplicate check
            if checker.is_already_applied("kle4311@gmail.com", job['url']):
                stats['skipped'] += 1
                print(f"[{idx:2d}/10] ⏭️  SKIPPED (duplicate)")
                return
            
            # Apply with timeout
            try:
                result = await asyncio.wait_for(
                    router.apply(job['url']),
                    timeout=JOB_TIMEOUT
                )
                
                # Record to DB
                try:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO applications (id, user_id, job_url, job_title, company, platform, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (
                        f"kent_opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}",
                        "kent-le-user", job['url'], job['title'], job['company'],
                        job.get('platform', 'unknown'),
                        'submitted' if result.success else 'failed'
                    ))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    pass
                
                # Update stats
                if result.success:
                    stats['submitted'] += 1
                    checker.record_application("kle4311@gmail.com", job['url'], "kent_opt")
                    icon = "✅"
                else:
                    stats['failed'] += 1
                    icon = "❌"
                
                print(f"[{idx:2d}/10] {icon} {job['company'][:15]:15} | {result.status}")
                
            except asyncio.TimeoutError:
                stats['failed'] += 1
                print(f"[{idx:2d}/10] ⏱️  TIMEOUT | {job['company'][:15]:15}")
            except Exception as e:
                stats['failed'] += 1
                print(f"[{idx:2d}/10] 💥 ERROR | {job['company'][:15]:15} | {str(e)[:30]}")
            
            # Rate limiting
            await asyncio.sleep(DELAY_BETWEEN)
    
    # Process all
    print("\n" + "="*70)
    print("📝 PROCESSING")
    print("="*70 + "\n")
    
    tasks = [process_one(job, i+1) for i, job in enumerate(jobs)]
    await asyncio.gather(*tasks)
    
    # Cleanup
    await router.cleanup()
    force_cleanup()
    
    # Stats
    duration = (datetime.now() - start).total_seconds() / 60
    rate = stats['submitted'] / duration if duration > 0 else 0
    
    print("\n" + "="*70)
    print("📊 RESULTS")
    print("="*70)
    print(f"✅ Submitted: {stats['submitted']}")
    print(f"❌ Failed: {stats['failed']}")
    print(f"⏭️  Skipped: {stats['skipped']}")
    print(f"⏱️  Duration: {duration:.1f} minutes")
    print(f"⚡ Rate: {rate:.1f} jobs/minute")
    print(f"📈 Success: {(stats['submitted']/len(jobs)*100):.1f}%")
    print("="*70)
    
    if stats['submitted'] > 0:
        print(f"\n📧 Check kle4311@gmail.com for confirmations!")

asyncio.run(run())
