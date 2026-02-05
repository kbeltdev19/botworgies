#!/usr/bin/env python3
"""
KEVIN BELTRAN - REAL APPLICATIONS (Working Version)
Honest implementation with proper submission tracking
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
    "full_name": "Kevin Beltran",
    "email": "beltranrkevin@gmail.com",
    "phone": "770-378-2545",
    "location": "Atlanta, GA",
    "resume_path": "Test Resumes/Kevin_Beltran_Resume.pdf"
}

print("=" * 75)
print("🚀 KEVIN BELTRAN - REAL JOB APPLICATIONS")
print("=" * 75)
print()
print("⚠️  REALITY CHECK:")
print("   - Job application forms vary greatly")
print("   - Many require LinkedIn login")
print("   - Some redirect to external ATS")
print("   - Success = reaching application form, not guaranteed submission")
print()

# Stats
stats = {
    "started": datetime.now().isoformat(),
    "attempted": 0,
    "forms_reached": 0,
    "fields_filled": 0,
    "submitted": 0,
    "errors": 0,
    "companies": []
}

async def try_apply(job, manager):
    """Attempt to apply to a job."""
    result = {
        "job_id": job['id'],
        "company": job['company'],
        "title": job['title'],
        "url": job['url'],
        "status": "attempted",
        "form_reached": False,
        "fields_filled": [],
        "submitted": False,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Create session
        session = await manager.create_stealth_session(
            platform=job.get('platform', 'generic'),
            use_proxy=True
        )
        page = session.page
        
        # Navigate
        try:
            response = await page.goto(job['url'], timeout=20000, wait_until="domcontentloaded")
            await asyncio.sleep(3)
        except Exception as e:
            result["error"] = f"Navigation failed: {str(e)[:50]}"
            await manager.close_session(session.session_id)
            return result
        
        # Get page info
        try:
            title = await page.title()
            url = page.url
            result["page_title"] = title
            result["final_url"] = url
        except:
            pass
        
        # Look for apply button
        apply_found = False
        apply_selectors = [
            'button:has-text("Apply")',
            'a:has-text("Apply")', 
            'button:has-text("Easy Apply")',
            'a:has-text("Easy Apply")',
            '[data-testid*="apply"]',
            '.apply-button',
            '#apply-button'
        ]
        
        for selector in apply_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    if await btn.is_visible():
                        await btn.click()
                        apply_found = True
                        result["form_reached"] = True
                        await asyncio.sleep(3)
                        break
            except:
                continue
        
        if not apply_found:
            # Check if already on application form
            form_selectors = [
                'input[type="email"]',
                'input[name*="email"]',
                'form',
                '.application-form'
            ]
            for sel in form_selectors:
                try:
                    if await page.locator(sel).first.count() > 0:
                        result["form_reached"] = True
                        break
                except:
                    continue
        
        # If form reached, try to fill
        if result["form_reached"]:
            fields_to_fill = [
                ('input[name*="first"]', KEVIN['first_name']),
                ('input[name*="last"]', KEVIN['last_name']),
                ('input[type="email"]', KEVIN['email']),
                ('input[name*="email"]', KEVIN['email']),
                ('input[type="tel"]', KEVIN['phone']),
                ('input[name*="phone"]', KEVIN['phone']),
                ('input[name*="location"]', KEVIN['location']),
                ('input[name*="city"]', "Atlanta"),
            ]
            
            for selector, value in fields_to_fill:
                try:
                    field = page.locator(selector).first
                    if await field.count() > 0:
                        if await field.is_visible() and await field.is_enabled():
                            await field.fill(value)
                            result["fields_filled"].append(selector.split('[')[1].split(']')[0] if '[' in selector else selector)
                            await asyncio.sleep(0.3)
                except:
                    continue
            
            # Try to upload resume
            try:
                resume_path = Path(KEVIN['resume_path']).resolve()
                if resume_path.exists():
                    file_inputs = [
                        'input[type="file"][accept*="pdf"]',
                        'input[type="file"][name*="resume"]',
                        'input[type="file"]'
                    ]
                    for sel in file_inputs:
                        try:
                            inp = page.locator(sel).first
                            if await inp.count() > 0:
                                await inp.set_input_files(str(resume_path))
                                result["resume_uploaded"] = True
                                break
                        except:
                            continue
            except:
                pass
            
            # Try to submit
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Submit")',
                'button:has-text("Send Application")',
                'input[type="submit"]'
            ]
            
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        # Don't actually click submit in this version - too risky
                        result["submit_button_found"] = True
                        break
                except:
                    continue
        
        await manager.close_session(session.session_id)
        
    except Exception as e:
        result["error"] = str(e)[:100]
        try:
            await manager.close_session(session.session_id)
        except:
            pass
    
    return result

async def main():
    from browser.stealth_manager import StealthBrowserManager
    
    # Load jobs
    jobs_file = Path("output/kevin_1000_real_fast/jobs_1000.json")
    with open(jobs_file) as f:
        all_jobs = json.load(f)
    
    # Use only first 50 for realistic test
    jobs = all_jobs[:50]
    
    print(f"📋 Processing {len(jobs)} jobs (realistic test)")
    print(f"👤 {KEVIN['full_name']} | {KEVIN['email']}")
    print()
    
    print("🔌 Connecting to BrowserBase...")
    manager = StealthBrowserManager()
    await manager.initialize()
    print("✅ Connected\n")
    
    print("=" * 75)
    print("🚀 STARTING APPLICATIONS")
    print("=" * 75)
    print()
    
    results = []
    start_time = time.time()
    
    for i, job in enumerate(jobs):
        print(f"[{i+1:2d}/{len(jobs)}] {job['company'][:25]:25s} | ", end="", flush=True)
        
        result = await try_apply(job, manager)
        results.append(result)
        
        stats["attempted"] += 1
        if result["form_reached"]:
            stats["forms_reached"] += 1
            print(f"📋 Form reached", end="")
        else:
            stats["errors"] += 1
            print(f"❌ No form", end="")
        
        if result["fields_filled"]:
            stats["fields_filled"] += len(result["fields_filled"])
            print(f" | Filled {len(result['fields_filled'])} fields", end="")
        
        if result.get("submit_button_found"):
            print(f" | 📤 Submit ready", end="")
        
        if result["error"]:
            print(f" | ⚠️  {result['error'][:30]}", end="")
        
        print()
        
        # Save progress
        if (i + 1) % 10 == 0:
            with open("output/kevin_1000_real_fast/real_results.json", 'w') as f:
                json.dump({
                    "stats": stats,
                    "results": results,
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2, default=str)
        
        await asyncio.sleep(2)  # Be polite
    
    await manager.close_all()
    
    # Final report
    elapsed = time.time() - start_time
    
    print()
    print("=" * 75)
    print("📊 FINAL REPORT")
    print("=" * 75)
    print(f"Jobs Attempted: {stats['attempted']}")
    print(f"Application Forms Reached: {stats['forms_reached']} ({stats['forms_reached']/stats['attempted']*100:.1f}%)")
    print(f"Form Fields Filled: {stats['fields_filled']}")
    print(f"Errors/Redirects: {stats['errors']}")
    print(f"Duration: {elapsed/60:.1f} minutes")
    print()
    print("⚠️  NOTE: Form submissions were NOT sent (safety)")
    print("   To actually submit, manual review and click required")
    print()
    
    # Save final
    with open("output/kevin_1000_real_fast/final_report.json", 'w') as f:
        json.dump({
            "stats": stats,
            "results": results,
            "candidate": KEVIN,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2, default=str)

if __name__ == "__main__":
    asyncio.run(main())
