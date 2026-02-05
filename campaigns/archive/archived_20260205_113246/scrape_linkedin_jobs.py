#!/usr/bin/env python3
"""
Scrape real job URLs from LinkedIn using Playwright
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

async def scrape_linkedin_jobs():
    """Scrape LinkedIn for real job URLs"""
    
    print("🔍 Scraping LinkedIn for real jobs...")
    
    jobs = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        # LinkedIn job search URL
        search_url = "https://www.linkedin.com/jobs/search?keywords=Customer%20Success%20Manager&location=Remote&f_WT=2"
        
        print(f"   Navigating: {search_url[:60]}...")
        
        try:
            await page.goto(search_url, wait_until='domcontentloaded', timeout=45000)
            await asyncio.sleep(5)
            
            # Extract job cards
            job_cards = await page.query_selector_all('.job-card-container, [data-job-id]')
            print(f"   Found {len(job_cards)} job cards")
            
            for card in job_cards[:15]:
                try:
                    # Get job ID
                    job_id = await card.get_attribute('data-job-id')
                    if not job_id:
                        continue
                    
                    # Build job URL
                    job_url = f"https://www.linkedin.com/jobs/view/{job_id}"
                    
                    # Get title
                    title_el = await card.query_selector('a.job-card-list__title, .job-card-container__link')
                    title = await title_el.inner_text() if title_el else "Unknown"
                    title = title.strip().replace('\n', ' ')
                    
                    # Get company
                    company_el = await card.query_selector('.job-card-container__company-name, .artdeco-entity-lockup__subtitle')
                    company = await company_el.inner_text() if company_el else "Unknown"
                    company = company.strip()
                    
                    jobs.append({
                        'url': job_url,
                        'title': title[:100],
                        'company': company[:50],
                        'platform': 'linkedin',
                        'job_id': job_id
                    })
                    
                    print(f"   ✅ {company[:20]:20} | {title[:35]:35}")
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"   Error: {e}")
        
        await browser.close()
    
    return jobs

async def main():
    print("="*70)
    print("🔍 LINKEDIN JOB SCRAPER")
    print("="*70)
    
    jobs = await scrape_linkedin_jobs()
    
    print(f"\n✅ Total jobs found: {len(jobs)}")
    
    # Save
    output = Path(__file__).parent / "kent_scraped_jobs.json"
    with open(output, 'w') as f:
        json.dump({
            'scraped_at': datetime.now().isoformat(),
            'total_jobs': len(jobs),
            'jobs': jobs
        }, f, indent=2)
    
    print(f"💾 Saved to: {output}")
    
    # Show sample
    print("\n📋 Sample:")
    for job in jobs[:5]:
        print(f"   {job['company'][:18]:18} | {job['title'][:35]:35}")

if __name__ == "__main__":
    asyncio.run(main())
