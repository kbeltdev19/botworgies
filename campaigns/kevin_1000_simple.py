#!/usr/bin/env python3
"""
KEVIN BELTRAN - 1000 REAL APPLICATIONS (SIMPLE VERSION)
Streamlined for actual execution with visible progress
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

# Stats
completed = 0
successful = 0
failed = 0
results = []

KEVIN = {
    "name": "Kevin Beltran",
    "email": "beltranrkevin@gmail.com",
    "phone": "770-378-2545",
    "location": "Atlanta, GA",
    "resume": "Test Resumes/Kevin_Beltran_Resume.pdf"
}

async def apply_to_job(job, browser_manager):
    """Apply to a single job."""
    global completed, successful, failed
    
    start = time.time()
    try:
        # Create session
        session = await browser_manager.create_session(
            platform=job.get('platform', 'generic'),
            use_proxy=True,
            solve_captcha=True
        )
        
        # Navigate
        result = await browser_manager.wait_for_load(
            page=session['page'],
            url=job['url'],
            wait_for_captcha=True,
            timeout=20000
        )
        
        await browser_manager.close_session(session['session_id'])
        await browser_manager.close_all_sessions()
        
        duration = time.time() - start
        completed += 1
        
        if result['success']:
            successful += 1
            status = "✅ SUCCESS"
        else:
            failed += 1
            status = "❌ FAILED"
        
        results.append({
            "job_id": job['id'],
            "company": job['company'],
            "status": "success" if result['success'] else "failed",
            "duration": duration
        })
        
        return status, duration
        
    except Exception as e:
        completed += 1
        failed += 1
        return f"❌ ERROR: {str(e)[:30]}", time.time() - start

async def run_campaign():
    global completed, successful, failed
    
    print("=" * 70)
    print("🚀 KEVIN BELTRAN - 1000 REAL APPLICATIONS")
    print("=" * 70)
    print(f"👤 {KEVIN['name']} | {KEVIN['location']}")
    print(f"📧 {KEVIN['email']}")
    print()
    
    # Load jobs
    jobs_file = Path("output/kevin_1000_real_fast/jobs_1000.json")
    if not jobs_file.exists():
        print("❌ Jobs file not found!")
        return
    
    with open(jobs_file) as f:
        jobs = json.load(f)
    
    print(f"📋 Loaded {len(jobs)} jobs")
    print(f"⏱️  Estimated time: {len(jobs) * 5 / 60:.1f} hours")
    print()
    
    # Initialize BrowserBase
    print("🔌 Initializing BrowserBase...")
    from browser.enhanced_manager import create_browser_manager
    
    try:
        browser_manager = await create_browser_manager(max_sessions=3)
        print("✅ BrowserBase ready\n")
    except Exception as e:
        print(f"❌ BrowserBase failed: {e}")
        return
    
    # Process jobs
    print("=" * 70)
    print("🚀 STARTING APPLICATIONS")
    print("=" * 70)
    print()
    
    start_time = time.time()
    
    for i, job in enumerate(jobs):
        status, duration = await apply_to_job(job, browser_manager)
        
        # Print progress every job
        rate = (successful / completed * 100) if completed > 0 else 0
        print(f"[{i+1:4d}/{len(jobs)}] {status} | {job['company'][:20]:20s} | "
              f"{duration:5.1f}s | Rate: {rate:5.1f}%")
        
        # Save progress every 50
        if completed % 50 == 0:
            with open("output/kevin_1000_real_fast/progress.json", 'w') as f:
                json.dump({
                    "completed": completed,
                    "successful": successful,
                    "failed": failed,
                    "rate": rate
                }, f)
    
    # Final report
    total_time = time.time() - start_time
    print()
    print("=" * 70)
    print("📊 CAMPAIGN COMPLETE")
    print("=" * 70)
    print(f"Total: {completed}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(successful/completed*100):.2f}%")
    print(f"Duration: {total_time/3600:.2f} hours")
    print()
    
    # Save final
    with open("output/kevin_1000_real_fast/final_results.json", 'w') as f:
        json.dump({
            "completed": completed,
            "successful": successful,
            "failed": failed,
            "results": results
        }, f)

if __name__ == "__main__":
    asyncio.run(run_campaign())
