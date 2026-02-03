#!/usr/bin/env python3
"""
Kent Le - 1000 Application Batch
Uses 100 parallel BrowserBase sessions
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from browserbase import Browserbase
from playwright.async_api import async_playwright

# Kent's profile
KENT = {
    "first_name": "Kent",
    "last_name": "Le",
    "email": "kle4311@gmail.com",
    "phone": "+1 (404) 934-0630",
    "resume": "data/kent_le_resume.pdf"
}

# Stats
stats = {
    "started": None,
    "submitted": 0,
    "failed": 0,
    "in_progress": 0
}


async def apply_single(job, profile, semaphore):
    """Apply to a single job using BrowserBase."""
    async with semaphore:
        stats["in_progress"] += 1
        
        try:
            bb = Browserbase(api_key=os.environ["BROWSERBASE_API_KEY"])
            session = bb.sessions.create(
                project_id=os.environ["BROWSERBASE_PROJECT_ID"],
                proxies=True,
            )
            
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(session.connect_url)
                context = await browser.new_context()
                page = await context.new_page()
                
                try:
                    await page.goto(job['url'], timeout=25000, wait_until='domcontentloaded')
                    await asyncio.sleep(1.5)
                    
                    filled = 0
                    
                    # Fill form
                    fn = page.locator('#first_name')
                    if await fn.count() > 0:
                        await fn.fill(profile['first_name'])
                        filled += 1
                    
                    ln = page.locator('#last_name')
                    if await ln.count() > 0:
                        await ln.fill(profile['last_name'])
                        filled += 1
                    
                    em = page.locator('#email')
                    if await em.count() > 0:
                        await em.fill(profile['email'])
                        filled += 1
                    
                    phone = page.locator('#phone, input[name*="phone"]')
                    if await phone.count() > 0:
                        await phone.first.fill(profile['phone'])
                        filled += 1
                    
                    resume = page.locator('input[type="file"]')
                    if await resume.count() > 0:
                        try:
                            await resume.first.set_input_files(profile['resume'])
                            filled += 1
                        except:
                            pass
                    
                    if filled >= 3:
                        submit = page.locator('#submit_app, button[type="submit"]')
                        if await submit.count() > 0:
                            await submit.first.click()
                            await asyncio.sleep(2)
                            stats["submitted"] += 1
                            return {"status": "submitted", "job": job['title'], "company": job['company']}
                    
                    stats["failed"] += 1
                    return {"status": "incomplete", "job": job['title']}
                    
                except Exception as e:
                    stats["failed"] += 1
                    return {"status": "error", "error": str(e)[:50]}
                finally:
                    await browser.close()
                    
        except Exception as e:
            stats["failed"] += 1
            return {"status": "error", "error": str(e)[:50]}
        finally:
            stats["in_progress"] -= 1


async def progress_reporter():
    """Report progress every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        elapsed = (datetime.now() - stats["started"]).total_seconds() / 60
        rate = stats["submitted"] / elapsed if elapsed > 0 else 0
        print(f"\n📊 Progress: {stats['submitted']} submitted, {stats['failed']} failed, {stats['in_progress']} in progress | Rate: {rate:.1f}/min", flush=True)


async def main():
    print("=" * 70, flush=True)
    print("KENT LE - 1000 APPLICATION BATCH (100 parallel BrowserBase sessions)", flush=True)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("=" * 70, flush=True)
    
    stats["started"] = datetime.now()
    
    # Load jobs
    with open('campaigns/kent_le_jobs.json') as f:
        data = json.load(f)
    
    # Get Greenhouse jobs (direct forms work best)
    greenhouse_jobs = [j for j in data.get('greenhouse_jobs', []) if 'greenhouse.io' in j.get('url', '')]
    print(f"\nDirect Greenhouse jobs: {len(greenhouse_jobs)}", flush=True)
    
    # Limit to 1000
    jobs = greenhouse_jobs[:1000]
    print(f"Processing: {len(jobs)} jobs", flush=True)
    
    # Semaphore for 100 concurrent sessions
    semaphore = asyncio.Semaphore(100)
    
    # Start progress reporter
    reporter = asyncio.create_task(progress_reporter())
    
    # Process all jobs
    print("\n🚀 Starting batch...\n", flush=True)
    
    tasks = [apply_single(job, KENT, semaphore) for job in jobs]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Cancel reporter
    reporter.cancel()
    
    # Final stats
    elapsed = (datetime.now() - stats["started"]).total_seconds()
    
    print("\n" + "=" * 70, flush=True)
    print("FINAL RESULTS", flush=True)
    print("=" * 70, flush=True)
    print(f"✅ Submitted: {stats['submitted']}", flush=True)
    print(f"❌ Failed: {stats['failed']}", flush=True)
    print(f"⏱️  Duration: {elapsed/60:.1f} minutes", flush=True)
    print(f"📈 Rate: {stats['submitted']/(elapsed/60):.1f} apps/minute", flush=True)
    
    # Save results
    with open('campaigns/kent_le_batch_results.json', 'w') as f:
        json.dump({
            "candidate": "Kent Le",
            "completed_at": datetime.now().isoformat(),
            "submitted": stats["submitted"],
            "failed": stats["failed"],
            "duration_seconds": elapsed,
            "rate_per_minute": stats['submitted']/(elapsed/60) if elapsed > 0 else 0
        }, f, indent=2)
    
    print("\nResults saved to: campaigns/kent_le_batch_results.json", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
