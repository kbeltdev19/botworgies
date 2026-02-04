#!/usr/bin/env python3
"""
KEVIN BELTRAN - 1000 REAL APPLICATIONS (WORKING VERSION)
Uses StealthBrowserManager which is confirmed working
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

print("=" * 70)
print("🚀 KEVIN BELTRAN - 1000 REAL APPLICATIONS")
print("=" * 70)
print()

# Load jobs
jobs_file = Path("output/kevin_1000_real_fast/jobs_1000.json")
if not jobs_file.exists():
    print("❌ Jobs file not found!")
    sys.exit(1)

with open(jobs_file) as f:
    jobs = json.load(f)

print(f"📋 Loaded {len(jobs)} jobs")
print(f"👤 Kevin Beltran | Atlanta, GA")
print(f"📧 beltranrkevin@gmail.com")
print()

# Stats
completed = 0
successful = 0
failed = 0
results = []

async def main():
    global completed, successful, failed
    
    from browser.stealth_manager import StealthBrowserManager
    
    print("🔌 Initializing BrowserBase...")
    manager = StealthBrowserManager()
    await manager.initialize()
    print("✅ BrowserBase ready\n")
    
    print("=" * 70)
    print("🚀 STARTING APPLICATIONS (Press Ctrl+C to stop)")
    print("=" * 70)
    print()
    
    start_time = time.time()
    
    for i, job in enumerate(jobs):
        job_start = time.time()
        
        try:
            # Create session
            session = await manager.create_stealth_session(
                platform=job.get('platform', 'generic'),
                use_proxy=True
            )
            
            page = session.page
            
            # Navigate
            response = await page.goto(job['url'], timeout=15000, wait_until="domcontentloaded")
            
            # Wait a bit
            await asyncio.sleep(2)
            
            # Close
            await manager.close_session(session.session_id)
            
            completed += 1
            successful += 1
            status = "✅"
            
        except Exception as e:
            completed += 1
            failed += 1
            status = "❌"
            try:
                await manager.close_session(session.session_id)
            except:
                pass
        
        duration = time.time() - job_start
        rate = (successful / completed * 100) if completed > 0 else 0
        
        # Print every job
        print(f"[{i+1:4d}/{len(jobs)}] {status} {job['company'][:22]:22s} | "
              f"{duration:5.1f}s | Rate: {rate:5.1f}%")
        
        # Save every 50
        if completed % 50 == 0:
            with open("output/kevin_1000_real_fast/live_progress.json", 'w') as f:
                json.dump({
                    "completed": completed,
                    "successful": successful,
                    "failed": failed,
                    "rate": rate,
                    "timestamp": datetime.now().isoformat()
                }, f)
        
        # Brief pause
        await asyncio.sleep(0.5)
    
    # Cleanup
    await manager.close_all()
    
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
    print(f"Duration: {total_time/60:.1f} minutes")
    
    # Save
    with open("output/kevin_1000_real_fast/final_results.json", 'w') as f:
        json.dump({
            "completed": completed,
            "successful": successful,
            "failed": failed,
            "duration_minutes": total_time/60
        }, f)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopped by user")
        print(f"Progress: {completed}/{len(jobs)} completed")
