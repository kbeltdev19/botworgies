#!/usr/bin/env python3
"""
KENT LE - 1000 REAL JOB APPLICATIONS (PRODUCTION)
Complete production script with proper error handling and monitoring
"""

import sys
import os
import asyncio
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict

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

# Ensure Kent exists in database
def ensure_kent_user():
    """Create Kent as a user if not exists"""
    db_path = Path(__file__).parent.parent / 'data' / 'job_applier.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check if Kent exists
    cursor.execute("SELECT id FROM users WHERE email = ?", ("kle4311@gmail.com",))
    user = cursor.fetchone()
    
    if user:
        user_id = user[0]
        print(f"✅ Kent user exists: {user_id}")
    else:
        # Create Kent user
        user_id = "kent-le-production"
        cursor.execute("""
            INSERT INTO users (id, email, hashed_password, is_active)
            VALUES (?, ?, ?, 1)
        """, (user_id, "kle4311@gmail.com", " Kent_password_hash_123"))
        
        # Create profile
        cursor.execute("""
            INSERT INTO profiles (user_id, first_name, last_name, email, phone, work_authorization, sponsorship_required)
            VALUES (?, ?, ?, ?, ?, 'Yes', 'No')
        """, (user_id, "Kent", "Le", "kle4311@gmail.com", "404-934-0630"))
        
        conn.commit()
        print(f"✅ Created Kent user: {user_id}")
    
    conn.close()
    return user_id

# Setup logging
log_file = Path("/tmp/kent_1000_production.log")
def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {msg}"
    print(log_line)
    with open(log_file, 'a') as f:
        f.write(log_line + '\n')

# Kill zombies
os.system("pkill -9 -f 'python.*campaign\|playwright' 2>/dev/null")

print("="*70)
print("🚀 KENT LE - 1000 REAL JOB APPLICATIONS (PRODUCTION)")
print("="*70)
print("⚠️  THIS WILL SUBMIT ACTUAL JOB APPLICATIONS!")
print("="*70)
log("Campaign starting...")

# Ensure user exists
user_id = ensure_kent_user()

# Load jobs
jobs_file = Path(__file__).parent / "kent_le_real_jobs_1000.json"
with open(jobs_file) as f:
    data = json.load(f)
    all_jobs = data.get('jobs', [])

log(f"Loaded {len(all_jobs)} jobs")

# Configuration
MAX_APPLICATIONS = 1000
BATCH_SIZE = 50
CONCURRENT_LIMIT = 3
RATE_LIMIT_DELAY = 5  # seconds between apps

current_stats = {
    'submitted': 0,
    'failed': 0,
    'skipped': 0,
    'errors': []
}

async def process_job(job: Dict, router, checker, db_path) -> dict:
    """Process a single job application"""
    job_url = job.get('url', '')
    job_title = job.get('title', 'Unknown')
    company = job.get('company', 'Unknown')
    
    result = {
        'success': False,
        'job_url': job_url,
        'job_title': job_title,
        'company': company,
        'error': None
    }
    
    # Check duplicates
    if checker.is_already_applied("kle4311@gmail.com", job_url):
        result['skipped'] = True
        return result
    
    try:
        # Attempt application
        app_result = await router.apply(job_url)
        
        # Record in database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO applications 
            (id, user_id, job_url, job_title, company, platform, status, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            f"kent_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(job_url) % 10000}",
            user_id,
            job_url,
            job_title,
            company,
            job.get('platform', 'unknown'),
            'submitted' if app_result.success else 'failed',
            app_result.error_message if not app_result.success else None
        ))
        conn.commit()
        conn.close()
        
        if app_result.success:
            result['success'] = True
            checker.record_application("kle4311@gmail.com", job_url, "kent_1000")
        else:
            result['error'] = app_result.error_message or app_result.status
            
    except Exception as e:
        result['error'] = str(e)
    
    return result

async def run_campaign():
    from ats_automation import ATSRouter
    from ats_automation.models import UserProfile
    from campaigns.duplicate_checker import DuplicateChecker
    
    db_path = Path(__file__).parent.parent / 'data' / 'job_applier.db'
    
    # Create profile
    profile = UserProfile(
        first_name="Kent",
        last_name="Le",
        email="kle4311@gmail.com",
        phone="404-934-0630",
        resume_path="Test Resumes/Kent_Le_Resume.pdf"
    )
    
    router = ATSRouter(profile)
    checker = DuplicateChecker()
    
    # Take first 1000 jobs
    jobs = all_jobs[:MAX_APPLICATIONS]
    total = len(jobs)
    
    log(f"Starting applications: {total} jobs")
    log(f"Config: concurrent={CONCURRENT_LIMIT}, delay={RATE_LIMIT_DELAY}s")
    
    start_time = datetime.now()
    
    # Process in batches
    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = jobs[batch_start:batch_end]
        
        log(f"\n📦 Batch {batch_start//BATCH_SIZE + 1}: jobs {batch_start+1}-{batch_end}")
        
        # Process batch with semaphore for concurrency control
        semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
        
        async def process_with_limit(job):
            async with semaphore:
                return await process_job(job, router, checker, db_path)
        
        tasks = [process_with_limit(job) for job in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                current_stats['failed'] += 1
                current_stats['errors'].append(str(result))
                log(f"  ❌ Exception: {str(result)[:60]}")
            elif result.get('skipped'):
                current_stats['skipped'] += 1
            elif result.get('success'):
                current_stats['submitted'] += 1
                log(f"  ✅ {result['company'][:20]:20} | {result['job_title'][:30]}")
            else:
                current_stats['failed'] += 1
                log(f"  ❌ {result['company'][:20]:20} | {result.get('error', 'Unknown')[:40]}")
        
        # Batch stats
        elapsed = (datetime.now() - start_time).total_seconds() / 60
        progress = batch_end / total * 100
        log(f"📊 Progress: {batch_end}/{total} ({progress:.1f}%) | "
            f"✅ {current_stats['submitted']} | ❌ {current_stats['failed']} | "
            f"⏭️  {current_stats['skipped']} | {elapsed:.1f} min")
        
        # Rate limiting between batches
        if batch_end < total:
            await asyncio.sleep(RATE_LIMIT_DELAY * 2)
        
        # Cleanup zombies periodically
        if batch_end % 200 == 0:
            os.system("pkill -9 -f 'playwright.*zombie' 2>/dev/null")
    
    # Cleanup
    await router.cleanup()
    
    # Final report
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60
    
    print("\n" + "="*70)
    print("✅ CAMPAIGN COMPLETE")
    print("="*70)
    print(f"Total jobs: {total}")
    print(f"✅ Submitted: {current_stats['submitted']}")
    print(f"❌ Failed: {current_stats['failed']}")
    print(f"⏭️  Skipped (duplicates): {current_stats['skipped']}")
    print(f"📈 Success rate: {(current_stats['submitted']/total*100):.1f}%")
    print(f"⏱️  Duration: {duration:.1f} minutes")
    print(f"📊 Rate: {current_stats['submitted']/duration:.1f} apps/min" if duration > 0 else "")
    print("="*70)
    print("\n📧 Check kle4311@gmail.com for confirmation emails!")
    
    log("Campaign complete!")
    log(f"Final stats: {current_stats}")

# Run
if __name__ == "__main__":
    asyncio.run(run_campaign())
