#!/usr/bin/env python3
"""
KENT LE - DICE.COM REAL APPLICATIONS (OPTIMIZED)
Searches Dice for real Easy Apply jobs and submits applications
Target: 10 jobs/minute with zombie handling
"""

import sys
import os
import asyncio
import json
import sqlite3
import psutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict

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

# =============================================================================
# CONFIGURATION
# =============================================================================
CONFIG = {
    'max_applications': 10,      # Start with 10 for test
    'concurrent_limit': 3,       # 3 browsers max
    'job_timeout': 60,           # 60 seconds per job
    'delay_between': 6,          # 6 seconds = 10/minute
    'search_terms': [
        'Customer Success Manager',
        'Account Manager',
        'Sales Development Representative',
        'Business Development Representative'
    ]
}

# =============================================================================
# ZOMBIE HANDLER
# =============================================================================
def kill_zombies():
    """Kill stuck processes"""
    killed = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name'].lower() if proc.info['name'] else ''
            cmdline = ' '.join(proc.info['cmdline'] or []).lower()
            
            if any(x in cmdline for x in ['playwright', 'browserbase', 'chrome', 'chromium']):
                proc.kill()
                killed.append(proc.info['pid'])
        except:
            pass
    return killed

# =============================================================================
# DICE JOB SEARCH & APPLY
# =============================================================================
async def search_dice_jobs(browser_manager, query: str, location: str = "Remote", max_jobs: int = 5) -> List[Dict]:
    """Search Dice.com for real Easy Apply jobs"""
    jobs = []
    
    try:
        session = await asyncio.wait_for(
            browser_manager.create_stealth_session("dice"),
            timeout=30.0
        )
        page = session["page"]
        
        # Build search URL
        search_url = f"https://www.dice.com/jobs?q={query.replace(' ', '+')}&location={location}&remote=true"
        print(f"   Searching: {search_url[:60]}...")
        
        await asyncio.wait_for(
            page.goto(search_url, wait_until='networkidle'),
            timeout=45.0
        )
        await asyncio.sleep(3)
        
        # Extract job cards
        job_cards = await page.query_selector_all('[data-cy="search-result"]')
        print(f"   Found {len(job_cards)} jobs")
        
        for card in job_cards[:max_jobs]:
            try:
                # Get job link
                link_el = await card.query_selector('a[id*="position-title"]')
                if not link_el:
                    continue
                
                href = await link_el.get_attribute('href')
                if not href:
                    continue
                
                if href.startswith('/'):
                    href = f"https://www.dice.com{href}"
                
                # Get details
                title = await link_el.inner_text()
                title = title.strip() if title else query
                
                company_el = await card.query_selector('[data-cy="company-name"]')
                company = await company_el.inner_text() if company_el else "Unknown"
                
                # Check for Easy Apply
                easy_apply = await card.query_selector('text="Easy Apply"') is not None
                
                jobs.append({
                    'url': href,
                    'title': title,
                    'company': company.strip(),
                    'platform': 'dice',
                    'easy_apply': easy_apply,
                    'source_query': query
                })
                
            except Exception as e:
                continue
        
        await browser_manager.close_session(session['session_id'])
        
    except Exception as e:
        print(f"   Search error: {e}")
    
    return jobs

async def apply_to_dice_job(browser_manager, profile, job: Dict) -> Dict:
    """Apply to a single Dice job"""
    result = {
        'success': False,
        'job': job,
        'status': 'unknown',
        'error': None
    }
    
    try:
        session = await asyncio.wait_for(
            browser_manager.create_stealth_session("dice"),
            timeout=30.0
        )
        page = session["page"]
        
        # Navigate to job
        await asyncio.wait_for(
            page.goto(job['url'], wait_until='networkidle'),
            timeout=45.0
        )
        await asyncio.sleep(2)
        
        # Look for Easy Apply button
        easy_apply_btn = await page.query_selector('text="Easy Apply"')
        
        if easy_apply_btn:
            print(f"      🖱️  Clicking Easy Apply...")
            await easy_apply_btn.click()
            await asyncio.sleep(3)
            
            # Check if login required
            login_form = await page.query_selector('input[type="email"]')
            if login_form:
                print(f"      📝 Filling email...")
                await login_form.fill(profile['email'])
                
                continue_btn = await page.query_selector('button:has-text("Continue"), button:has-text("Next")')
                if continue_btn:
                    await continue_btn.click()
                    await asyncio.sleep(2)
            
            # Look for submit
            submit_btn = await page.query_selector('button:has-text("Submit"), button:has-text("Send Application")')
            
            if submit_btn:
                # NOTE: Uncomment below to actually submit
                # await submit_btn.click()
                # await asyncio.sleep(3)
                # result['success'] = True
                # result['status'] = 'submitted'
                
                print(f"      ⏸️  READY TO SUBMIT (commented out for safety)")
                result['success'] = True
                result['status'] = 'ready_to_submit'
            else:
                result['status'] = 'no_submit_button'
        else:
            result['status'] = 'no_easy_apply'
        
        await browser_manager.close_session(session['session_id'])
        
    except asyncio.TimeoutError:
        result['status'] = 'timeout'
        result['error'] = '60s timeout'
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)[:100]
    
    return result

# =============================================================================
# MAIN
# =============================================================================
async def main():
    from ats_automation.browserbase_manager import BrowserBaseManager
    
    print("="*70)
    print("🚀 KENT LE - DICE.COM REAL APPLICATIONS")
    print("="*70)
    print(f"⚡ Target: {60//CONFIG['delay_between']} jobs/minute")
    print(f"🔧 Concurrent: {CONFIG['concurrent_limit']}")
    print("="*70)
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    killed = kill_zombies()
    if killed:
        print(f"   Killed {len(killed)} processes")
    
    # Profile
    profile = {
        'first_name': 'Kent',
        'last_name': 'Le',
        'email': 'kle4311@gmail.com',
        'phone': '404-934-0630',
        'resume_path': 'Test Resumes/Kent_Le_Resume.pdf'
    }
    
    print(f"\n👤 {profile['first_name']} {profile['last_name']}")
    print(f"📧 {profile['email']}")
    
    # Init browser manager
    print("\n🌐 Initializing BrowserBase...")
    try:
        browser = BrowserBaseManager()
        print(f"   ✅ Active sessions: {browser.get_active_session_count()}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Search for jobs
    print("\n🔍 Searching Dice.com for jobs...")
    all_jobs = []
    
    for query in CONFIG['search_terms']:
        if len(all_jobs) >= CONFIG['max_applications']:
            break
        
        print(f"\n   Query: '{query}'")
        jobs = await search_dice_jobs(browser, query, max_jobs=3)
        
        # Only keep Easy Apply jobs
        easy_apply_jobs = [j for j in jobs if j.get('easy_apply')]
        print(f"   ✅ {len(easy_apply_jobs)} Easy Apply jobs")
        
        all_jobs.extend(easy_apply_jobs)
        
        if len(all_jobs) >= CONFIG['max_applications']:
            break
        
        await asyncio.sleep(2)
    
    # Limit to max
    all_jobs = all_jobs[:CONFIG['max_applications']]
    
    print(f"\n📋 Total jobs to apply: {len(all_jobs)}")
    for i, job in enumerate(all_jobs, 1):
        print(f"   {i:2d}. {job['company'][:18]:18} | {job['title'][:35]:35}")
    
    # Warning
    print(f"\n⚠️  WARNING: Will process {len(all_jobs)} REAL applications!")
    print("⚠️  Submissions currently PAUSED (edit code to enable)")
    print("\n   Press Ctrl+C in 5 seconds to cancel...")
    
    try:
        import time
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n❌ Cancelled")
        await browser.close_all_sessions()
        return
    
    # Apply to jobs
    print("\n" + "="*70)
    print("📝 PROCESSING APPLICATIONS")
    print("="*70 + "\n")
    
    semaphore = asyncio.Semaphore(CONFIG['concurrent_limit'])
    stats = {'success': 0, 'failed': 0}
    start = datetime.now()
    
    async def process_job(job, idx):
        async with semaphore:
            print(f"[{idx:2d}/{len(all_jobs)}] {job['company'][:18]:18} | {job['title'][:30]:30}")
            
            result = await apply_to_dice_job(browser, profile, job)
            
            if result['success']:
                stats['success'] += 1
                icon = "✅"
            else:
                stats['failed'] += 1
                icon = "❌"
            
            print(f"       {icon} {result['status']}")
            if result['error']:
                print(f"       {result['error'][:50]}")
            
            # Rate limiting
            await asyncio.sleep(CONFIG['delay_between'])
            
            return result
    
    tasks = [process_job(job, i+1) for i, job in enumerate(all_jobs)]
    results = await asyncio.gather(*tasks)
    
    # Cleanup
    await browser.close_all_sessions()
    kill_zombies()
    
    # Stats
    duration = (datetime.now() - start).total_seconds() / 60
    rate = stats['success'] / duration if duration > 0 else 0
    
    print("\n" + "="*70)
    print("📊 RESULTS")
    print("="*70)
    print(f"✅ Ready/Submitted: {stats['success']}")
    print(f"❌ Failed: {stats['failed']}")
    print(f"⏱️  Duration: {duration:.1f} minutes")
    print(f"⚡ Rate: {rate:.1f} jobs/minute")
    print("="*70)
    
    if stats['success'] > 0:
        print(f"\n📧 Check {profile['email']} for confirmations!")
        print("\n⚠️  NOTE: To ACTUALLY submit applications, uncomment:")
        print("   'await submit_btn.click()' in the code")

if __name__ == "__main__":
    asyncio.run(main())
