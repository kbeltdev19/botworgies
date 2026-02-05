#!/usr/bin/env python3
"""
KENT LE - 1000 REAL APPLICATIONS (OPTIMIZED)
Target: 10 jobs/minute with 85%+ success rate
Features: Zombie handling, concurrency, session reuse
"""

import sys
import os
import asyncio
import json
import sqlite3
import psutil
import signal
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

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

# =============================================================================
# CONFIGURATION - TUNED FOR SPEED & SUCCESS
# =============================================================================
CONFIG = {
    'max_applications': 1000,
    'concurrent_limit': 5,          # 5 browsers at once (BrowserBase max ~50)
    'jobs_per_minute': 10,          # Target rate
    'delay_between_jobs': 6,        # 6 seconds = 10 jobs/minute
    'job_timeout': 45,              # 45 seconds max per job
    'batch_size': 50,               # Process in batches
    'zombie_check_interval': 25,    # Kill zombies every 25 jobs
    'max_retries': 2,               # Retry failed jobs once
    'recovery_delay': 10,           # Pause after errors
}

# =============================================================================
# ZOMBIE PROCESS HANDLER
# =============================================================================
class ZombieKiller:
    """Kills stuck Python and browser processes"""
    
    @staticmethod
    def kill_zombies():
        """Kill all zombie Python and browser processes"""
        killed = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                name = proc.info['name'].lower() if proc.info['name'] else ''
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                
                # Kill criteria
                should_kill = False
                
                # Old Python campaign processes (>5 min)
                if 'python' in name and ('campaign' in cmdline or 'kent' in cmdline):
                    if proc.info['create_time']:
                        age_min = (datetime.now().timestamp() - proc.info['create_time']) / 60
                        if age_min > 5:
                            should_kill = True
                
                # Playwright/node zombie processes
                if 'playwright' in cmdline or 'browserbase' in cmdline:
                    should_kill = True
                    
                # Orphaned node processes from playwright
                if name == 'node' and ('cli.js' in cmdline or 'playwright' in cmdline):
                    should_kill = True
                
                if should_kill:
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                        killed.append(proc.info['pid'])
                    except:
                        try:
                            proc.kill()
                            killed.append(proc.info['pid'])
                        except:
                            pass
                            
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return killed
    
    @staticmethod
    def force_cleanup():
        """Force kill all browser-related processes"""
        os.system("pkill -9 -f 'playwright' 2>/dev/null")
        os.system("pkill -9 -f 'chrome' 2>/dev/null")
        os.system("pkill -9 -f 'chromium' 2>/dev/null")
        os.system("pkill -9 -f 'node.*cli.js' 2>/dev/null")

# =============================================================================
# SESSION MANAGER WITH POOLING
# =============================================================================
class SessionPool:
    """Manages browser session pool for reuse"""
    
    def __init__(self, max_sessions=5):
        self.max_sessions = max_sessions
        self.available = []
        self.in_use = {}
        self.total_created = 0
        
    async def get_session(self, browser_manager, platform="generic"):
        """Get session from pool or create new"""
        # Return available session if exists
        if self.available:
            session = self.available.pop()
            self.in_use[session['session_id']] = session
            return session
        
        # Create new if under limit
        if len(self.in_use) < self.max_sessions:
            session = await browser_manager.create_stealth_session(platform)
            self.in_use[session['session_id']] = session
            self.total_created += 1
            return session
        
        # Wait for available session
        while not self.available:
            await asyncio.sleep(0.5)
        
        session = self.available.pop()
        self.in_use[session['session_id']] = session
        return session
    
    def release_session(self, session_id):
        """Return session to pool"""
        if session_id in self.in_use:
            session = self.in_use.pop(session_id)
            self.available.append(session)
    
    async def cleanup_all(self, browser_manager):
        """Close all sessions"""
        for session in list(self.in_use.values()) + self.available:
            try:
                await browser_manager.close_session(session['session_id'])
            except:
                pass
        self.in_use.clear()
        self.available.clear()

# =============================================================================
# APPLICATION WORKER
# =============================================================================
class ApplicationWorker:
    """Worker that processes jobs with retry logic"""
    
    def __init__(self, router, checker, db_path, user_id, stats):
        self.router = router
        self.checker = checker
        self.db_path = db_path
        self.user_id = user_id
        self.stats = stats
        
    async def apply_with_retry(self, job: Dict, max_retries=2) -> Dict:
        """Apply to job with retry logic"""
        job_url = job['url']
        
        for attempt in range(max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self.router.apply(job_url),
                    timeout=CONFIG['job_timeout']
                )
                
                # Record in database
                self._record_application(job, result)
                
                if result.success:
                    self.stats['submitted'] += 1
                    self.checker.record_application("kle4311@gmail.com", job_url, "kent_optimized")
                    return {'success': True, 'job': job, 'result': result, 'attempts': attempt + 1}
                
                # Retry on certain failures
                if result.status in ['timeout', 'network_error', 'rate_limited'] and attempt < max_retries:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                
                self.stats['failed'] += 1
                return {'success': False, 'job': job, 'result': result, 'attempts': attempt + 1}
                
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    await asyncio.sleep(5)
                    continue
                self.stats['failed'] += 1
                self._record_application(job, None, error="Timeout")
                return {'success': False, 'job': job, 'error': 'timeout', 'attempts': attempt + 1}
                
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(5)
                    continue
                self.stats['failed'] += 1
                self._record_application(job, None, error=str(e)[:100])
                return {'success': False, 'job': job, 'error': str(e), 'attempts': attempt + 1}
    
    def _record_application(self, job, result, error=None):
        """Record to database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO applications (id, user_id, job_url, job_title, company, platform, status, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                f"kent_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(job['url']) % 10000}",
                self.user_id,
                job['url'],
                job['title'],
                job['company'],
                job.get('platform', 'unknown'),
                'submitted' if result and result.success else 'failed',
                error or (result.error_message if result and not result.success else None)
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB error: {e}")

# =============================================================================
# MAIN CAMPAIGN RUNNER
# =============================================================================
async def run_campaign():
    from ats_automation import ATSRouter
    from ats_automation.models import UserProfile
    from campaigns.duplicate_checker import DuplicateChecker
    
    print("="*70)
    print("🚀 KENT LE - 1000 REAL APPLICATIONS (OPTIMIZED)")
    print("="*70)
    print(f"⚡ Target: {CONFIG['jobs_per_minute']} jobs/minute")
    print(f"🔧 Concurrent: {CONFIG['concurrent_limit']} | Timeout: {CONFIG['job_timeout']}s")
    print("="*70)
    
    # Initial cleanup
    print("\n🧹 Initial zombie cleanup...")
    killed = ZombieKiller.kill_zombies()
    if killed:
        print(f"   Killed {len(killed)} zombie processes")
    ZombieKiller.force_cleanup()
    
    # Load jobs
    jobs_file = Path(__file__).parent / "kent_test_10_jobs.json"  # Start with 10 for testing
    # jobs_file = Path(__file__).parent / "kent_le_real_jobs_1000.json"  # Full list
    
    with open(jobs_file) as f:
        data = json.load(f)
        all_jobs = data.get('jobs', [])[:CONFIG['max_applications']]
    
    print(f"\n📋 Loaded {len(all_jobs)} jobs")
    
    # Ensure Kent user exists
    db_path = Path(__file__).parent.parent / 'data' / 'job_applier.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", ("kle4311@gmail.com",))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (id, email, hashed_password, is_active) VALUES (?, ?, ?, 1)",
                      ("kent-le-prod", "kle4311@gmail.com", "kent_hash_2024"))
        cursor.execute("INSERT INTO profiles (user_id, first_name, last_name, email, phone) VALUES (?, ?, ?, ?, ?)",
                      ("kent-le-prod", "Kent", "Le", "kle4311@gmail.com", "404-934-0630"))
        conn.commit()
        user_id = "kent-le-prod"
    else:
        user_id = user[0]
    conn.close()
    
    # Setup
    profile = UserProfile(
        first_name="Kent", last_name="Le",
        email="kle4311@gmail.com", phone="404-934-0630",
        resume_path="Test Resumes/Kent_Le_Resume.pdf"
    )
    
    router = ATSRouter(profile)
    checker = DuplicateChecker()
    
    stats = {'submitted': 0, 'failed': 0, 'skipped': 0, 'retried': 0}
    worker = ApplicationWorker(router, checker, db_path, user_id, stats)
    
    # Warning
    print(f"\n⚠️  THIS WILL SUBMIT {len(all_jobs)} REAL APPLICATIONS!")
    print(f"   Email: kle4311@gmail.com")
    print(f"\n   Press Ctrl+C in 5 seconds to cancel...")
    
    try:
        import time
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n❌ Cancelled")
        return
    
    print("\n🚀 Starting optimized campaign!")
    start_time = datetime.now()
    
    # Process with semaphore for concurrency
    semaphore = asyncio.Semaphore(CONFIG['concurrent_limit'])
    processed = 0
    
    async def process_job(job):
        nonlocal processed
        async with semaphore:
            # Check duplicate
            if checker.is_already_applied("kle4311@gmail.com", job['url']):
                stats['skipped'] += 1
                return {'success': False, 'skipped': True}
            
            # Apply
            result = await worker.apply_with_retry(job, CONFIG['max_retries'])
            processed += 1
            
            # Progress output
            icon = "✅" if result.get('success') else "❌"
            print(f"[{processed:4d}/{len(all_jobs)}] {icon} {job['company'][:15]:15} | {job['title'][:30]:30} "
                  f"(attempts: {result.get('attempts', 1)})")
            
            # Rate limiting for 10 jobs/minute target
            await asyncio.sleep(CONFIG['delay_between_jobs'])
            
            return result
    
    # Process all jobs
    tasks = [process_job(job) for job in all_jobs]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Cleanup
    await router.cleanup()
    ZombieKiller.force_cleanup()
    
    # Final stats
    duration = (datetime.now() - start_time).total_seconds() / 60
    actual_rate = stats['submitted'] / duration if duration > 0 else 0
    
    print("\n" + "="*70)
    print("✅ CAMPAIGN COMPLETE")
    print("="*70)
    print(f"Total: {len(all_jobs)}")
    print(f"✅ Submitted: {stats['submitted']}")
    print(f"❌ Failed: {stats['failed']}")
    print(f"⏭️  Skipped: {stats['skipped']}")
    print(f"🔄 Retried: {stats['retried']}")
    print(f"📈 Success Rate: {(stats['submitted']/len(all_jobs)*100):.1f}%")
    print(f"⏱️  Duration: {duration:.1f} minutes")
    print(f"⚡ Actual Rate: {actual_rate:.1f} jobs/minute")
    print("="*70)
    
    if stats['submitted'] > 0:
        print(f"\n📧 Check kle4311@gmail.com for {stats['submitted']} confirmation emails!")

# Run
if __name__ == "__main__":
    asyncio.run(run_campaign())
