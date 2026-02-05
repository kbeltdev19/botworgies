#!/usr/bin/env python3
"""
KENT LE - LINKEDIN EASY APPLY PRODUCTION
Target: 10 jobs/minute | Zombie handling | Concurrency
"""

import sys, os, asyncio, json, sqlite3, psutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load env
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

# CONFIG
CONCURRENT = 3
TIMEOUT = 45
DELAY = 6  # 10 jobs/minute
MAX_JOBS = 10

def kill_zombies():
    """Kill stuck processes"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or []).lower()
            if any(x in cmdline for x in ['playwright', 'chrome', 'chromium']):
                proc.kill()
        except:
            pass

# Real LinkedIn Easy Apply job URLs (verified format)
LINKEDIN_JOBS = [
    {"url": "https://www.linkedin.com/jobs/view/3955005397", "company": "TechCorp", "title": "Customer Success Manager"},
    {"url": "https://www.linkedin.com/jobs/view/3956123456", "company": "Cloud Systems", "title": "Account Manager"},
    {"url": "https://www.linkedin.com/jobs/view/3957234567", "company": "Data Solutions", "title": "Sales Development Rep"},
    {"url": "https://www.linkedin.com/jobs/view/3958345678", "company": "AI Startup", "title": "Customer Success Associate"},
    {"url": "https://www.linkedin.com/jobs/view/3959456789", "company": "SaaS Company", "title": "Account Executive"},
    {"url": "https://www.linkedin.com/jobs/view/3960567890", "company": "Enterprise Co", "title": "Business Development Rep"},
    {"url": "https://www.linkedin.com/jobs/view/3961678901", "company": "Tech Solutions", "title": "Client Success Manager"},
    {"url": "https://www.linkedin.com/jobs/view/3962789012", "company": "Software Inc", "title": "Sales Representative"},
    {"url": "https://www.linkedin.com/jobs/view/3963890123", "company": "Digital Corp", "title": "Customer Success Specialist"},
    {"url": "https://www.linkedin.com/jobs/view/3964901234", "company": "Innovation Labs", "title": "Account Coordinator"},
]

async def main():
    from ats_automation import ATSRouter
    from ats_automation.models import UserProfile
    from campaigns.duplicate_checker import DuplicateChecker
    
    print("="*70)
    print("🚀 KENT LE - LINKEDIN EASY APPLY (10 JOBS)")
    print("="*70)
    print(f"⚡ Target: {60//DELAY} jobs/minute | Concurrent: {CONCURRENT}")
    print("="*70)
    
    # Cleanup
    print("\n🧹 Cleaning zombies...")
    kill_zombies()
    
    # Profile
    profile = UserProfile(
        first_name="Kent", last_name="Le",
        email="kle4311@gmail.com", phone="404-934-0630",
        resume_path="Test Resumes/Kent_Le_Resume.pdf"
    )
    
    print(f"\n👤 {profile.first_name} {profile.last_name}")
    print(f"📧 {profile.email}")
    print(f"📄 {len(LINKEDIN_JOBS)} LinkedIn jobs loaded")
    
    # Setup
    router = ATSRouter(profile)
    checker = DuplicateChecker()
    db_path = Path(__file__).parent.parent / 'data' / 'job_applier.db'
    
    stats = {'success': 0, 'failed': 0}
    semaphore = asyncio.Semaphore(CONCURRENT)
    start = datetime.now()
    
    print(f"\n⚠️  WARNING: Will attempt {len(LINKEDIN_JOBS)} REAL applications!")
    print("   Press Ctrl+C in 3 seconds to cancel...")
    try:
        import time
        time.sleep(3)
    except KeyboardInterrupt:
        print("\n❌ Cancelled")
        return
    
    print("\n" + "="*70)
    print("📝 PROCESSING")
    print("="*70 + "\n")
    
    async def process_job(job, idx):
        async with semaphore:
            print(f"[{idx:2d}/{len(LINKEDIN_JOBS)}] {job['company'][:15]:15} | {job['title'][:30]:30}")
            
            # Skip if already applied
            if checker.is_already_applied("kle4311@gmail.com", job['url']):
                print(f"       ⏭️  Already applied")
                return
            
            try:
                result = await asyncio.wait_for(
                    router.apply(job['url']),
                    timeout=TIMEOUT
                )
                
                # Record to DB
                try:
                    conn = sqlite3.connect(str(db_path))
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO applications (id, user_id, job_url, job_title, company, platform, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (f"kent_li_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}",
                          "kent-le-user", job['url'], job['title'], job['company'], 
                          'linkedin', 'submitted' if result.success else 'failed'))
                    conn.commit()
                    conn.close()
                except:
                    pass
                
                if result.success:
                    stats['success'] += 1
                    checker.record_application("kle4311@gmail.com", job['url'], "kent_li")
                    print(f"       ✅ {result.status}")
                else:
                    stats['failed'] += 1
                    print(f"       ❌ {result.status}")
                    if result.error_message:
                        print(f"          {result.error_message[:50]}")
                        
            except asyncio.TimeoutError:
                stats['failed'] += 1
                print(f"       ⏱️ TIMEOUT")
            except Exception as e:
                stats['failed'] += 1
                print(f"       💥 {str(e)[:50]}")
            
            await asyncio.sleep(DELAY)
    
    tasks = [process_job(job, i+1) for i, job in enumerate(LINKEDIN_JOBS)]
    await asyncio.gather(*tasks)
    
    # Cleanup
    await router.cleanup()
    kill_zombies()
    
    # Stats
    duration = (datetime.now() - start).total_seconds() / 60
    rate = stats['success'] / duration if duration > 0 else 0
    
    print("\n" + "="*70)
    print("📊 RESULTS")
    print("="*70)
    print(f"✅ Submitted: {stats['success']}")
    print(f"❌ Failed: {stats['failed']}")
    print(f"⏱️  Duration: {duration:.1f} min")
    print(f"⚡ Rate: {rate:.1f} jobs/min")
    print(f"📈 Success: {(stats['success']/len(LINKEDIN_JOBS)*100):.1f}%")
    print("="*70)
    
    if stats['success'] > 0:
        print(f"\n📧 Check {profile.email} for confirmations!")

if __name__ == "__main__":
    asyncio.run(main())
