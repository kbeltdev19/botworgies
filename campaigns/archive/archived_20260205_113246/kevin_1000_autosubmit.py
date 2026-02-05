#!/usr/bin/env python3
"""
KEVIN BELTRAN - 1000 REAL APPLICATIONS (AUTO-SUBMIT ENABLED)
Actually fills forms and submits applications
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
    "linkedin": "",
    "website": "",
    "summary": "ServiceNow Business Analyst with federal and VA experience",
    "skills": "ServiceNow, ITSM, ITIL, Business Analysis, Federal Contracting"
}

AUTO_SUBMIT = True  # ⭐ AUTO-SUBMIT ENABLED

print("=" * 70)
print("🚀 KEVIN BELTRAN - 1000 REAL APPLICATIONS")
print(f"   AUTO-SUBMIT: {'✅ ENABLED' if AUTO_SUBMIT else '❌ DISABLED'}")
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
print(f"👤 {KEVIN['first_name']} {KEVIN['last_name']} | {KEVIN['location']}")
print(f"📧 {KEVIN['email']}")
print(f"📄 Resume: {KEVIN['resume_path']}")
print()

if AUTO_SUBMIT:
    print("⚠️  WARNING: Auto-submit is ENABLED")
    print("   This will ACTUALLY submit job applications!")
    print()

# Stats
completed = 0
successful = 0
failed = 0
submitted = 0

async def fill_and_submit(page, job, manager):
    """Fill application form and submit."""
    
    # Look for apply button
    apply_selectors = [
        'button:has-text("Apply")',
        'button:has-text("Easy Apply")',
        'a:has-text("Apply")',
        '[data-testid="apply-button"]',
        '.apply-button',
        '#applyButton'
    ]
    
    for selector in apply_selectors:
        try:
            button = page.locator(selector).first
            if await button.count() > 0 and await button.is_visible():
                await manager.human_like_click(page, selector)
                await asyncio.sleep(2)
                break
        except:
            continue
    
    # Fill basic fields
    field_mappings = {
        'input[name="firstName"], input[id*="first"], input[placeholder*="First"]': KEVIN['first_name'],
        'input[name="lastName"], input[id*="last"], input[placeholder*="Last"]': KEVIN['last_name'],
        'input[type="email"], input[name*="email"], input[id*="email"]': KEVIN['email'],
        'input[type="tel"], input[name*="phone"], input[id*="phone"]': KEVIN['phone'],
        'input[name*="location"], input[id*="location"]': KEVIN['location'],
        'input[name*="city"]': "Atlanta",
        'input[name*="state"]': "GA",
    }
    
    for selector, value in field_mappings.items():
        try:
            field = page.locator(selector).first
            if await field.count() > 0 and await field.is_visible():
                await manager.human_like_type(page, selector, value)
                await asyncio.sleep(0.5)
        except:
            continue
    
    # Upload resume if file input exists
    resume_selectors = [
        'input[type="file"][accept*="pdf"]',
        'input[type="file"][name*="resume"]',
        'input[type="file"][id*="resume"]'
    ]
    
    for selector in resume_selectors:
        try:
            file_input = page.locator(selector).first
            if await file_input.count() > 0:
                resume_path = Path(KEVIN['resume_path']).resolve()
                if resume_path.exists():
                    await file_input.set_input_files(str(resume_path))
                    await asyncio.sleep(2)
                    break
        except:
            continue
    
    # Submit if auto_submit enabled
    if AUTO_SUBMIT:
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Send")',
            'input[type="submit"]'
        ]
        
        for selector in submit_selectors:
            try:
                submit_btn = page.locator(selector).first
                if await submit_btn.count() > 0 and await submit_btn.is_visible():
                    await manager.human_like_click(page, selector)
                    await asyncio.sleep(3)
                    return True
            except:
                continue
    
    return False

async def main():
    global completed, successful, failed, submitted
    
    from browser.stealth_manager import StealthBrowserManager
    
    print("🔌 Initializing BrowserBase...")
    manager = StealthBrowserManager()
    await manager.initialize()
    print("✅ BrowserBase ready\n")
    
    print("=" * 70)
    print("🚀 STARTING APPLICATIONS")
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
            
            # Navigate to job
            response = await page.goto(job['url'], timeout=15000, wait_until="domcontentloaded")
            
            # Wait for load
            await manager.wait_for_cloudflare(page, timeout=10)
            await asyncio.sleep(2)
            
            # Fill form and submit
            was_submitted = await fill_and_submit(page, job, manager)
            
            # Close session
            await manager.close_session(session.session_id)
            
            completed += 1
            successful += 1
            if was_submitted:
                submitted += 1
                status = "📤 SUBMITTED"
            else:
                status = "✅ FILLED"
            
        except Exception as e:
            completed += 1
            failed += 1
            status = f"❌ {str(e)[:20]}"
            try:
                await manager.close_session(session.session_id)
            except:
                pass
        
        duration = time.time() - job_start
        rate = (successful / completed * 100) if completed > 0 else 0
        
        # Print progress
        print(f"[{i+1:4d}/{len(jobs)}] {status:15s} | {job['company'][:20]:20s} | "
              f"{duration:5.1f}s | Rate: {rate:5.1f}%")
        
        # Save progress every 50
        if completed % 50 == 0:
            with open("output/kevin_1000_real_fast/live_progress.json", 'w') as f:
                json.dump({
                    "completed": completed,
                    "successful": successful,
                    "failed": failed,
                    "submitted": submitted,
                    "rate": rate,
                    "timestamp": datetime.now().isoformat()
                }, f)
        
        # Brief pause between jobs
        await asyncio.sleep(1)
    
    # Cleanup
    await manager.close_all()
    
    # Final report
    total_time = time.time() - start_time
    print()
    print("=" * 70)
    print("📊 CAMPAIGN COMPLETE")
    print("=" * 70)
    print(f"Total Processed: {completed}")
    print(f"Successful: {successful}")
    print(f"Actually Submitted: {submitted}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(successful/completed*100):.2f}%")
    print(f"Duration: {total_time/60:.1f} minutes")
    print()
    print(f"👤 Candidate: {KEVIN['first_name']} {KEVIN['last_name']}")
    print(f"📧 Email: {KEVIN['email']}")
    print(f"📞 Phone: {KEVIN['phone']}")
    
    # Save
    with open("output/kevin_1000_real_fast/final_results.json", 'w') as f:
        json.dump({
            "completed": completed,
            "successful": successful,
            "submitted": submitted,
            "failed": failed,
            "duration_minutes": total_time/60,
            "candidate": KEVIN
        }, f)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopped by user")
        print(f"Progress: {completed}/{len(jobs)} completed, {submitted} submitted")
