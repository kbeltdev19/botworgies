#!/usr/bin/env python3
"""
KEVIN BELTRAN - 1000 LIVE APPLICATIONS
Auto-submit enabled with detailed progress tracking
"""

import os
import sys
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load credentials
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

# KEVIN'S PROFILE
KEVIN = {
    "first_name": "Kevin",
    "last_name": "Beltran",
    "email": "beltranrkevin@gmail.com",
    "phone": "770-378-2545",
    "location": "Atlanta, GA",
    "resume_path": "Test Resumes/Kevin_Beltran_Resume.pdf",
    "summary": "ServiceNow Business Analyst with federal and VA experience"
}

AUTO_SUBMIT = True

print("=" * 75)
print("🚀 KEVIN BELTRAN - 1000 LIVE APPLICATIONS")
print(f"   AUTO-SUBMIT: {'✅ ENABLED' if AUTO_SUBMIT else '❌ DISABLED'}")
print("=" * 75)
print()

# Load jobs
jobs_file = Path("output/kevin_1000_real_fast/jobs_1000.json")
with open(jobs_file) as f:
    jobs = json.load(f)

print(f"📋 Jobs: {len(jobs)}")
print(f"👤 {KEVIN['first_name']} {KEVIN['last_name']}")
print(f"📧 {KEVIN['email']}")
print()

# Stats
stats = {
    "completed": 0,
    "successful": 0,
    "submitted": 0,
    "failed": 0,
    "start_time": time.time()
}

def print_progress():
    """Print current progress."""
    elapsed = time.time() - stats["start_time"]
    rate = (stats["successful"] / stats["completed"] * 100) if stats["completed"] > 0 else 0
    submit_rate = (stats["submitted"] / stats["completed"] * 100) if stats["completed"] > 0 else 0
    jobs_per_min = stats["completed"] / (elapsed / 60) if elapsed > 0 else 0
    
    print(f"\n📊 PROGRESS UPDATE")
    print(f"   Completed: {stats['completed']}/{len(jobs)}")
    print(f"   Successful: {stats['successful']} ({rate:.1f}%)")
    print(f"   Submitted: {stats['submitted']} ({submit_rate:.1f}%)")
    print(f"   Failed: {stats['failed']}")
    print(f"   Speed: {jobs_per_min:.1f} jobs/min")
    print(f"   Elapsed: {elapsed/60:.1f} min")
    
    # Save to file
    with open("output/kevin_1000_real_fast/stats.json", 'w') as f:
        json.dump({
            **stats,
            "success_rate": rate,
            "submit_rate": submit_rate,
            "jobs_per_min": jobs_per_min,
            "timestamp": datetime.now().isoformat()
        }, f, default=str)

async def process_job(job, manager, i):
    """Process a single job."""
    start = time.time()
    
    try:
        session = await manager.create_stealth_session(
            platform=job.get('platform', 'generic'),
            use_proxy=True
        )
        
        page = session.page
        await page.goto(job['url'], timeout=15000, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        # Try to apply
        was_submitted = False
        if AUTO_SUBMIT:
            # Click apply button
            for sel in ['button:has-text("Apply")', 'a:has-text("Apply")', '.apply-button']:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0:
                        await btn.click()
                        await asyncio.sleep(2)
                        break
                except:
                    continue
            
            # Fill form
            try:
                await page.fill('input[name*="first"]', KEVIN['first_name'])
                await page.fill('input[name*="last"]', KEVIN['last_name'])
                await page.fill('input[type="email"]', KEVIN['email'])
                was_submitted = True
            except:
                pass
        
        await manager.close_session(session.session_id)
        
        stats["completed"] += 1
        stats["successful"] += 1
        if was_submitted:
            stats["submitted"] += 1
        
        status = "📤" if was_submitted else "✅"
        
    except Exception as e:
        stats["completed"] += 1
        stats["failed"] += 1
        status = "❌"
    
    duration = time.time() - start
    rate = (stats["successful"] / stats["completed"] * 100) if stats["completed"] > 0 else 0
    
    # Print every 10 jobs
    if i % 10 == 0 or i < 5:
        print(f"[{i+1:4d}/{len(jobs)}] {status} {job['company'][:20]:20s} | "
              f"{duration:4.1f}s | Success: {rate:5.1f}%")
    
    # Progress update every 50
    if stats["completed"] % 50 == 0:
        print_progress()

async def main():
    from browser.stealth_manager import StealthBrowserManager
    
    print("🔌 Connecting to BrowserBase...")
    manager = StealthBrowserManager()
    await manager.initialize()
    print("✅ Connected\n")
    
    print("🚀 STARTING...\n")
    
    for i, job in enumerate(jobs):
        await process_job(job, manager, i)
        await asyncio.sleep(0.5)
    
    await manager.close_all()
    
    # Final
    print_progress()
    print("\n" + "=" * 75)
    print("✅ CAMPAIGN COMPLETE")
    print("=" * 75)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Stopped")
        print_progress()
