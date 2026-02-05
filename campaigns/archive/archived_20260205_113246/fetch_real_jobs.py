#!/usr/bin/env python3
"""
Fetch real job URLs from Dice.com using browser automation
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from datetime import datetime

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

async def fetch_dice_jobs():
    """Fetch real job listings from Dice.com"""
    browser = BrowserBaseManager()
    jobs = []
    
    session = await browser.create_stealth_session("dice")
    page = session["page"]
    session_id = session["session_id"]
    
    try:
        print("🔍 Searching Dice.com for Customer Success Manager jobs...")
        
        # Navigate to Dice search
        search_url = "https://www.dice.com/jobs?q=Customer+Success+Manager&location=Remote&remote=true"
        await page.goto(search_url, wait_until='networkidle', timeout=60000)
        await asyncio.sleep(5)
        
        # Scroll to load more
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
        
        # Extract job cards
        job_cards = await page.query_selector_all('[data-cy="search-result"]')
        print(f"Found {len(job_cards)} job cards")
        
        for card in job_cards[:15]:
            try:
                # Get job link
                link_el = await card.query_selector('a[id*="position-title"], a[data-cy="job-title"]')
                if not link_el:
                    continue
                
                href = await link_el.get_attribute('href')
                if not href:
                    continue
                
                # Make absolute URL
                if href.startswith('/'):
                    href = f"https://www.dice.com{href}"
                
                # Get title
                title = await link_el.inner_text()
                title = title.strip() if title else "Unknown"
                
                # Get company
                company_el = await card.query_selector('[data-cy="company-name"], .company-name')
                company = await company_el.inner_text() if company_el else "Unknown"
                company = company.strip() if company else "Unknown"
                
                # Check for Easy Apply
                easy_apply_el = await card.query_selector('text="Easy Apply"')
                easy_apply = easy_apply_el is not None
                
                jobs.append({
                    'url': href,
                    'title': title,
                    'company': company,
                    'platform': 'dice',
                    'easy_apply': easy_apply,
                    'location': 'Remote'
                })
                
                print(f"  ✅ {company[:20]:20} | {title[:40]}")
                
            except Exception as e:
                print(f"  Error extracting job: {e}")
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
    print("🔍 FETCHING REAL JOB URLs FROM DICE.COM")
    print("="*70)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    jobs = await fetch_dice_jobs()
    
    print(f"\n{'='*70}")
    print(f"✅ FOUND {len(jobs)} REAL JOBS")
    print(f"{'='*70}")
    
    # Save to file
    output_file = Path(__file__).parent / "kent_real_dice_jobs.json"
    with open(output_file, 'w') as f:
        json.dump({
            'scraped_at': datetime.now().isoformat(),
            'total_jobs': len(jobs),
            'jobs': jobs
        }, f, indent=2)
    
    print(f"💾 Saved to: {output_file}")
    
    # Also save as the main test file
    test_file = Path(__file__).parent / "kent_10_test_jobs.json"
    with open(test_file, 'w') as f:
        json.dump({
            'scraped_at': datetime.now().isoformat(),
            'total_jobs': len(jobs),
            'jobs': jobs
        }, f, indent=2)
    
    print(f"💾 Also saved to: {test_file}")
    
    return jobs

if __name__ == "__main__":
    jobs = asyncio.run(main())
