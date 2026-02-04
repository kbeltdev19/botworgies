#!/usr/bin/env python3
"""
KEVIN BELTRAN - 1000 PRODUCTION APPLICATIONS
Uses working jobspy scraper + new validation framework
"""

import os
import sys
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
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
    "summary": "ServiceNow Business Analyst with federal and VA experience"
}

print("=" * 80)
print("🚀 KEVIN BELTRAN - 1000 PRODUCTION APPLICATIONS")
print("=" * 80)
print(f"👤 {KEVIN['first_name']} {KEVIN['last_name']}")
print(f"📧 {KEVIN['email']}")
print(f"📍 {KEVIN['location']}")
print()


async def scrape_real_jobs(target: int = 1000) -> list:
    """Scrape real jobs using jobspy."""
    from jobspy import scrape_jobs
    
    print("📋 SCRAPING REAL JOBS FROM LINKEDIN/INDEED")
    print("=" * 80)
    
    all_jobs = []
    
    searches = [
        ("ServiceNow Business Analyst", "Remote"),
        ("ServiceNow Business Analyst", "Atlanta, GA"),
        ("ServiceNow Consultant", "Remote"),
        ("ServiceNow Consultant", ""),
        ("ITSM Analyst", "Remote"),
        ("ServiceNow Administrator", ""),
    ]
    
    for term, location in searches:
        if len(all_jobs) >= target:
            break
        
        try:
            print(f"\n🔍 Searching: '{term}' in '{location or 'Any'}'")
            
            df = scrape_jobs(
                site_name=["linkedin", "indeed"],
                search_term=term,
                location=location,
                results_wanted=200,
                hours_old=168,
                is_remote=(location == "Remote")
            )
            
            if len(df) > 0:
                for _, row in df.iterrows():
                    job = {
                        "id": f"job_{len(all_jobs):05d}",
                        "title": str(row.get('title', '')),
                        "company": str(row.get('company', '')),
                        "location": str(row.get('location', '')),
                        "url": str(row.get('job_url', '')),
                        "platform": str(row.get('site', 'unknown')),
                        "description": str(row.get('description', ''))[:200],
                        "is_remote": bool(row.get('is_remote', False)),
                        "date_posted": str(row.get('date_posted', ''))
                    }
                    # Only add if has real URL
                    if job['url'] and job['url'].startswith('http'):
                        all_jobs.append(job)
                
                print(f"   ✅ Added {len(df)} jobs (total: {len(all_jobs)})")
                
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
            continue
    
    # Deduplicate by URL
    seen = set()
    unique = []
    for job in all_jobs:
        if job['url'] not in seen:
            seen.add(job['url'])
            unique.append(job)
    
    print(f"\n✅ Total unique jobs: {len(unique)}")
    return unique[:target]


async def apply_with_validation(job: dict) -> dict:
    """Apply to a job with validation."""
    from browser.stealth_manager import StealthBrowserManager
    from adapters.validation import SubmissionValidator
    
    result = {
        "job_id": job['id'],
        "company": job['company'],
        "title": job['title'],
        "url": job['url'],
        "status": "attempted",
        "validated": False,
        "confirmation_id": None,
        "error": None
    }
    
    try:
        manager = StealthBrowserManager()
        await manager.initialize()
        
        session = await manager.create_stealth_session(
            platform=job.get('platform', 'generic'),
            use_proxy=True
        )
        
        page = session.page
        
        # Navigate
        try:
            await page.goto(job['url'], timeout=20000, wait_until="domcontentloaded")
            await asyncio.sleep(3)
        except Exception as e:
            result["error"] = f"Navigation failed: {str(e)[:30]}"
            await manager.close_all()
            return result
        
        # Click apply
        apply_clicked = False
        for selector in ['button:has-text("Apply")', 'a:has-text("Apply")', '.apply-button']:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    apply_clicked = True
                    await asyncio.sleep(3)
                    break
            except:
                continue
        
        if not apply_clicked:
            result["error"] = "No apply button"
            await manager.close_all()
            return result
        
        # Fill form
        fields = [
            ('input[name*="first"]', KEVIN['first_name']),
            ('input[name*="last"]', KEVIN['last_name']),
            ('input[type="email"]', KEVIN['email']),
        ]
        
        for selector, value in fields:
            try:
                field = page.locator(selector).first
                if await field.count() > 0:
                    await field.fill(value)
            except:
                continue
        
        # Submit
        try:
            submit = page.locator('button[type="submit"]').first
            if await submit.count() > 0:
                await submit.click()
                await asyncio.sleep(5)
        except:
            pass
        
        # Validate
        validation = await SubmissionValidator.validate(
            page=page,
            job_id=job['id'],
            platform=job.get('platform', 'generic'),
            screenshot_dir="/tmp/kevin_submissions"
        )
        
        result["validated"] = validation.get('success', False)
        result["confirmation_id"] = validation.get('confirmation_id')
        
        await manager.close_all()
        
    except Exception as e:
        result["error"] = str(e)[:50]
    
    return result


async def main():
    # Scrape jobs
    jobs = await scrape_real_jobs(1000)
    
    if len(jobs) == 0:
        print("❌ No jobs found!")
        return
    
    print(f"\n🎯 Processing {len(jobs)} jobs...")
    print("=" * 80)
    
    stats = {
        "attempted": 0,
        "successful": 0,
        "failed": 0,
        "confirmations": []
    }
    
    for i, job in enumerate(jobs):
        print(f"[{i+1:4d}/{len(jobs)}] {job['company'][:25]:25s} | ", end="", flush=True)
        
        result = await apply_with_validation(job)
        stats["attempted"] += 1
        
        if result["validated"]:
            stats["successful"] += 1
            print(f"✅ CONFIRMED", end="")
            if result["confirmation_id"]:
                print(f" | {result['confirmation_id'][:15]}", end="")
                stats["confirmations"].append(result["confirmation_id"])
        else:
            stats["failed"] += 1
            print(f"❌ {result.get('error', 'Fail')[:20]}", end="")
        
        print()
        
        # Progress every 25
        if stats["attempted"] % 25 == 0:
            print(f"\n📊 Progress: {stats['attempted']} | "
                  f"✅ {stats['successful']} | "
                  f"❌ {stats['failed']} | "
                  f"Rate: {stats['successful']/stats['attempted']*100:.1f}%\n")
        
        await asyncio.sleep(2)
    
    # Final report
    print("\n" + "=" * 80)
    print("📊 FINAL REPORT")
    print("=" * 80)
    print(f"Attempted: {stats['attempted']}")
    print(f"Successful: {stats['successful']}")
    print(f"Confirmations: {len(stats['confirmations'])}")
    print(f"Rate: {stats['successful']/stats['attempted']*100:.2f}%")


if __name__ == "__main__":
    asyncio.run(main())
