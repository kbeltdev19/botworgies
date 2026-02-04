#!/usr/bin/env python3
"""
KEVIN BELTRAN - APPLY TO REAL SCRAPED JOBS ONLY
Only uses actual job URLs from jobspy
"""

import os
import sys
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

KEVIN = {
    "first_name": "Kevin",
    "last_name": "Beltran", 
    "email": "beltranrkevin@gmail.com",
    "phone": "770-378-2545",
    "location": "Atlanta, GA"
}

print("=" * 70)
print("🚀 KEVIN BELTRAN - REAL SCRAPED JOBS ONLY")
print("=" * 70)
print()

# Scrape real jobs
print("🕷️  Scraping REAL jobs from LinkedIn/Indeed...")
print("   (This may take 2-3 minutes)")
print()

try:
    from jobspy import scrape_jobs
    
    all_jobs = []
    searches = [
        ("ServiceNow Business Analyst", "Remote"),
        ("ServiceNow Consultant", ""),
        ("ITSM Analyst", "Atlanta, GA"),
    ]
    
    for term, location in searches:
        try:
            df = scrape_jobs(
                site_name=["linkedin", "indeed"],
                search_term=term,
                location=location,
                results_wanted=50,
                hours_old=168
            )
            if len(df) > 0:
                for _, row in df.iterrows():
                    all_jobs.append({
                        "title": str(row.get('title', '')),
                        "company": str(row.get('company', '')),
                        "url": str(row.get('job_url', '')),
                        "platform": str(row.get('site', '')),
                        "location": str(row.get('location', ''))
                    })
                print(f"   ✅ '{term}': {len(df)} jobs")
        except Exception as e:
            print(f"   ⚠️  '{term}': {e}")
    
    # Deduplicate
    seen = set()
    jobs = []
    for job in all_jobs:
        if job['url'] not in seen and job['url'].startswith('http'):
            seen.add(job['url'])
            jobs.append(job)
    
    print(f"\n📋 Total UNIQUE real jobs: {len(jobs)}")
    
except ImportError:
    print("❌ jobspy not installed")
    jobs = []

if len(jobs) == 0:
    print("\n❌ No real jobs found. Cannot continue.")
    sys.exit(1)

print()
print("👤 Candidate:")
print(f"   Name: {KEVIN['first_name']} {KEVIN['last_name']}")
print(f"   Email: {KEVIN['email']}")
print(f"   Phone: {KEVIN['phone']}")
print()
print("⚠️  This will attempt to fill forms on REAL job sites.")
print("   Press Ctrl+C within 5 seconds to cancel...")
print()

time.sleep(5)

# Apply to real jobs
async def main():
    from browser.stealth_manager import StealthBrowserManager
    
    print("🔌 Starting BrowserBase...")
    manager = StealthBrowserManager()
    await manager.initialize()
    print("✅ Ready\n")
    
    results = {
        "attempted": 0,
        "forms_reached": 0,
        "fields_filled": 0,
        "errors": 0,
        "jobs": []
    }
    
    print("=" * 70)
    print("🚀 APPLYING TO REAL JOBS")
    print("=" * 70)
    print()
    
    for i, job in enumerate(jobs[:20]):  # Start with 20 for safety
        print(f"[{i+1:2d}/{len(jobs[:20])}] {job['company'][:20]:20s} | {job['platform'][:8]:8s} | ", end="", flush=True)
        
        result = {
            "company": job['company'],
            "title": job['title'],
            "url": job['url'],
            "status": "attempted",
            "form_found": False,
            "filled": []
        }
        
        try:
            session = await manager.create_stealth_session(platform=job['platform'], use_proxy=True)
            page = session.page
            
            # Navigate
            resp = await page.goto(job['url'], timeout=15000, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            # Look for apply button
            for sel in ['button:has-text("Apply")', 'a:has-text("Apply")', '.apply-button']:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        result["form_found"] = True
                        await asyncio.sleep(2)
                        break
                except:
                    continue
            
            # Check for form fields
            if result["form_found"]:
                fields = [
                    ('input[name*="first"]', KEVIN['first_name']),
                    ('input[name*="last"]', KEVIN['last_name']),
                    ('input[type="email"]', KEVIN['email']),
                    ('input[type="tel"]', KEVIN['phone']),
                ]
                
                for sel, val in fields:
                    try:
                        fld = page.locator(sel).first
                        if await fld.count() > 0 and await fld.is_visible():
                            await fld.fill(val)
                            result["filled"].append(sel)
                    except:
                        pass
            
            await manager.close_session(session.session_id)
            
            results["attempted"] += 1
            if result["form_found"]:
                results["forms_reached"] += 1
                print(f"📋 Form + {len(result['filled'])} fields")
            else:
                print("❌ No apply form")
                
        except Exception as e:
            results["errors"] += 1
            print(f"❌ Error: {str(e)[:30]}")
        
        results["jobs"].append(result)
        await asyncio.sleep(3)
    
    await manager.close_all()
    
    # Report
    print()
    print("=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    print(f"Attempted: {results['attempted']}")
    print(f"Forms reached: {results['forms_reached']}")
    print(f"Errors: {results['errors']}")
    
    # Save
    with open("output/kevin_real_applied.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Saved to output/kevin_real_applied.json")

asyncio.run(main())
