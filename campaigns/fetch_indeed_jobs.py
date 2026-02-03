#!/usr/bin/env python3
"""
Fetch real job URLs from Indeed using browser automation
"""

import sys
import os
import asyncio
import json
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

from ats_automation.browserbase_manager import BrowserBaseManager

async def fetch_indeed_jobs():
    """Fetch real job listings from Indeed"""
    browser = BrowserBaseManager()
    jobs = []
    
    session = await browser.create_stealth_session("indeed")
    page = session["page"]
    session_id = session["session_id"]
    
    try:
        print("🔍 Searching Indeed for Customer Success Manager jobs...")
        
        # Navigate to Indeed search
        search_url = "https://www.indeed.com/jobs?q=Customer+Success+Manager&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11"
        await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(5)
        
        # Get page content
        content = await page.content()
        
        # Try different selectors for job cards
        selectors = [
            '[data-testid="jobTitle"]',
            '.jobTitle a',
            'h2.jobTitle a',
            'a[href*="/rc/clk"]',
            'a[href*="/viewjob"]',
            '.slider_container .slider_item a',
            '[data-jk]'
        ]
        
        job_links = []
        for selector in selectors:
            job_links = await page.query_selector_all(selector)
            if job_links:
                print(f"  Found jobs with selector: {selector} ({len(job_links)} results)")
                break
        
        if not job_links:
            print("  Trying generic link search...")
            all_links = await page.query_selector_all('a[href*="/viewjob"]')
            job_links = all_links
        
        print(f"Processing {len(job_links)} job links...")
        
        seen_urls = set()
        for link in job_links[:20]:
            try:
                href = await link.get_attribute('href')
                if not href:
                    continue
                
                # Make absolute URL
                if href.startswith('/'):
                    href = f"https://www.indeed.com{href}"
                elif not href.startswith('http'):
                    continue
                
                # Skip duplicates
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                
                # Get job ID from URL
                job_id_match = re.search(r'jk=([a-f0-9]+)', href)
                job_id = job_id_match.group(1) if job_id_match else ""
                
                # Get title
                title = await link.inner_text()
                title = title.strip() if title else "Unknown"
                
                # Try to find company (may be in parent)
                company = "Unknown"
                try:
                    parent = await link.evaluate('el => el.closest("[class*=job]").textContent')
                    if parent:
                        # Try to extract company name
                        company_match = re.search(r'([^\n]+)\n', parent)
                        if company_match:
                            company = company_match.group(1).strip()[:50]
                except:
                    pass
                
                jobs.append({
                    'url': href,
                    'title': title,
                    'company': company,
                    'platform': 'indeed',
                    'job_id': job_id,
                    'location': 'Remote'
                })
                
                print(f"  ✅ {company[:20]:20} | {title[:40]}")
                
            except Exception as e:
                print(f"  Error: {e}")
                continue
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close_session(session_id)
    
    return jobs

async def main():
    print("="*70)
    print("🔍 FETCHING REAL JOB URLs FROM INDEED")
    print("="*70)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    jobs = await fetch_indeed_jobs()
    
    print(f"\n{'='*70}")
    print(f"✅ FOUND {len(jobs)} REAL JOBS")
    print(f"{'='*70}")
    
    # Save to file
    output_file = Path(__file__).parent / "kent_real_indeed_jobs.json"
    with open(output_file, 'w') as f:
        json.dump({
            'scraped_at': datetime.now().isoformat(),
            'total_jobs': len(jobs),
            'jobs': jobs
        }, f, indent=2)
    
    print(f"💾 Saved to: {output_file}")
    
    return jobs

if __name__ == "__main__":
    jobs = asyncio.run(main())
