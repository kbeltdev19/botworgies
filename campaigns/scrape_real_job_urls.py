#!/usr/bin/env python3
"""
Scrape real job URLs from company career pages
Converts search page URLs to actual job listing URLs
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from urllib.parse import urljoin, urlparse

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

# Company-specific scrapers
async def scrape_salesforce_jobs(browser, search_term: str, max_jobs: int = 5) -> List[Dict]:
    """Scrape Salesforce career page for actual job URLs"""
    jobs = []
    session = await browser.create_stealth_session("salesforce")
    page = session["page"]
    session_id = session["session_id"]
    
    try:
        search_url = f"https://careers.salesforce.com/en/jobs/?search={search_term.replace(' ', '%20')}&remote=true"
        print(f"  Navigating: {search_url[:70]}...")
        
        await page.goto(search_url, wait_until='networkidle', timeout=30000)
        await asyncio.sleep(3)
        
        # Salesforce uses job cards with links
        job_links = await page.query_selector_all('a[href*="/jobs/"]')
        print(f"  Found {len(job_links)} potential job links")
        
        seen = set()
        for link in job_links[:max_jobs * 2]:  # Get extra for filtering
            try:
                href = await link.get_attribute('href')
                if not href or '/jobs/' not in href:
                    continue
                
                # Make absolute URL
                if href.startswith('/'):
                    href = f"https://careers.salesforce.com{href}"
                elif not href.startswith('http'):
                    continue
                
                # Get job title
                title_el = await link.query_selector('h2, h3, .job-title, span')
                title = await title_el.inner_text() if title_el else search_term
                title = title.strip()
                
                # Skip if already seen
                if href in seen:
                    continue
                seen.add(href)
                
                jobs.append({
                    'url': href,
                    'title': title,
                    'company': 'Salesforce',
                    'platform': 'workday',
                    'source_search': search_term
                })
                
                if len(jobs) >= max_jobs:
                    break
                    
            except Exception as e:
                continue
        
    except Exception as e:
        print(f"  Error scraping Salesforce: {e}")
    finally:
        await browser.close_session(session_id)
    
    return jobs

async def scrape_generic_workday(browser, company: str, search_url: str, search_term: str, max_jobs: int = 3) -> List[Dict]:
    """Generic scraper for Workday-based career sites"""
    jobs = []
    session = await browser.create_stealth_session("workday")
    page = session["page"]
    session_id = session["session_id"]
    
    try:
        print(f"  Navigating: {search_url[:70]}...")
        await page.goto(search_url, wait_until='networkidle', timeout=30000)
        await asyncio.sleep(3)
        
        # Workday job links
        job_links = await page.query_selector_all('a[href*="/job/"], a[href*="/jobs/"], [data-automation-id="jobTitle"], .job-title a')
        print(f"  Found {len(job_links)} potential links")
        
        seen = set()
        for link in job_links[:max_jobs * 2]:
            try:
                href = await link.get_attribute('href')
                if not href:
                    continue
                
                # Make absolute
                if href.startswith('/'):
                    parsed = urlparse(search_url)
                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                elif not href.startswith('http'):
                    continue
                
                if href in seen:
                    continue
                seen.add(href)
                
                # Get title
                title = await link.inner_text() if link else search_term
                title = title.strip()[:100]
                
                jobs.append({
                    'url': href,
                    'title': title or search_term,
                    'company': company,
                    'platform': 'workday',
                    'source_search': search_term
                })
                
                if len(jobs) >= max_jobs:
                    break
                    
            except:
                continue
        
    except Exception as e:
        print(f"  Error scraping {company}: {e}")
    finally:
        await browser.close_session(session_id)
    
    return jobs

async def main():
    print("="*70)
    print("🔍 SCRAPING REAL JOB URLs")
    print("="*70)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    browser = BrowserBaseManager()
    all_jobs = []
    
    # Salesforce searches
    salesforce_searches = [
        "Customer Success Manager",
        "Account Manager",
        "Sales Development Representative"
    ]
    
    print("🏢 Scraping Salesforce...")
    for search in salesforce_searches:
        jobs = await scrape_salesforce_jobs(browser, search, max_jobs=3)
        print(f"  ✅ Found {len(jobs)} jobs for '{search}'")
        all_jobs.extend(jobs)
        await asyncio.sleep(2)
    
    # Other major companies with Workday
    companies = [
        ("Adobe", "https://careers.adobe.com/us/en/search-results", "Customer Success"),
        ("Microsoft", "https://careers.microsoft.com/us/en/search-results", "Account Manager"),
        ("Oracle", "https://careers.oracle.com/jobs/#en/sites/jobsearch", "Customer Success"),
        ("SAP", "https://jobs.sap.com/search/?q=customer+success", "Customer Success"),
        ("HubSpot", "https://www.hubspot.com/careers/jobs", "Customer Success"),
        ("Zoom", "https://careers.zoom.us/jobs", "Customer Success Manager"),
        ("Slack", "https://salesforce.wd12.myworkdayjobs.com/en-US/Slack", "Customer Success"),
        ("AWS", "https://www.amazon.jobs/en/search?base_query=customer+success", "Customer Success"),
    ]
    
    for company, base_url, search_term in companies:
        print(f"\n🏢 Scraping {company}...")
        search_url = f"{base_url}?keywords={search_term.replace(' ', '%20')}"
        jobs = await scrape_generic_workday(browser, company, search_url, search_term, max_jobs=3)
        print(f"  ✅ Found {len(jobs)} jobs")
        all_jobs.extend(jobs)
        await asyncio.sleep(2)
    
    # Cleanup
    await browser.close_all_sessions()
    
    # Save results
    print(f"\n{'='*70}")
    print(f"✅ SCRAPING COMPLETE")
    print(f"{'='*70}")
    print(f"Total real job URLs found: {len(all_jobs)}")
    
    # Save to file
    output_file = Path(__file__).parent / "kent_real_job_urls.json"
    with open(output_file, 'w') as f:
        json.dump({
            'scraped_at': datetime.now().isoformat(),
            'total_jobs': len(all_jobs),
            'jobs': all_jobs
        }, f, indent=2)
    
    print(f"💾 Saved to: {output_file}")
    
    # Show sample
    print(f"\n📋 Sample jobs:")
    for job in all_jobs[:5]:
        print(f"  • {job['company'][:15]:15} | {job['title'][:40]:40} | {job['url'][:50]}...")
    
    return all_jobs

if __name__ == "__main__":
    jobs = asyncio.run(main())
