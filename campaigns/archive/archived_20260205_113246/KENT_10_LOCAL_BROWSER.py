#!/usr/bin/env python3
"""
KENT LE - 10 REAL APPLICATIONS (LOCAL BROWSER)
Uses local Playwright when BrowserBase is rate-limited
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

# Unset BrowserBase to force local browser
os.environ['BROWSERBASE_API_KEY'] = ''
os.environ['BROWSERBASE_PROJECT_ID'] = ''

print("="*70)
print("🚀 KENT LE - 10 REAL APPLICATIONS (LOCAL BROWSER)")
print("="*70)
print("⚠️  Using local Playwright (BrowserBase rate-limited)")
print("="*70)

# Load jobs
jobs_file = Path(__file__).parent / "kent_test_10_jobs.json"
with open(jobs_file) as f:
    test_jobs = json.load(f)['jobs'][:10]

print(f"\n📋 {len(test_jobs)} jobs loaded")
print(f"👤 Kent Le (kle4311@gmail.com)")
print()

# Show jobs
for i, job in enumerate(test_jobs, 1):
    icon = "💼" if job['platform'] == 'workday' else "🌱" if job['platform'] == 'greenhouse' else "🔗"
    print(f"  {i:2d}. {icon} {job['company'][:15]:15} | {job['title'][:35]}")

print()
print("⚠️  WARNING: This will submit ACTUAL applications!")
print("⚠️  Confirmation emails to: kle4311@gmail.com")
print()
print("Starting in 5 seconds... (Ctrl+C to cancel)")

import time
try:
    time.sleep(5)
except KeyboardInterrupt:
    print("\n❌ Cancelled")
    sys.exit(0)

# Simple local browser implementation
class LocalBrowserManager:
    """Local Playwright browser manager (fallback)"""
    
    def __init__(self):
        self.active_sessions = {}
        self._playwright = None
        
    async def create_stealth_session(self, platform="generic"):
        from playwright.async_api import async_playwright
        
        self._playwright = await async_playwright().start()
        browser = await self._playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        # Add stealth scripts
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {name: 'Chrome PDF Plugin'},
                    {name: 'Chrome PDF Viewer'},
                    {name: 'Native Client'}
                ]
            });
            window.chrome = window.chrome || {};
            window.chrome.runtime = window.chrome.runtime || {};
        """)
        
        session_id = f"local_{id(page)}"
        session = {
            'browser': browser,
            'context': context,
            'page': page,
            'session_id': session_id,
            'platform': platform
        }
        self.active_sessions[session_id] = session
        return session
    
    async def close_session(self, session_id):
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            try:
                await session['context'].close()
                await session['browser'].close()
            except:
                pass
            del self.active_sessions[session_id]
    
    async def close_all_sessions(self):
        for session_id in list(self.active_sessions.keys()):
            await self.close_session(session_id)
        if self._playwright:
            await self._playwright.stop()
    
    def get_active_session_count(self):
        return len(self.active_sessions)
    
    async def solve_captcha_if_present(self, session_id, page):
        return True  # No captcha solving in local mode

async def run_tests():
    from ats_automation.models import UserProfile, ApplicationResult, ATSPlatform
    from ats_automation.handlers.greenhouse import GreenhouseHandler
    from ats_automation.generic_mapper import GenericFieldMapper
    
    profile = UserProfile(
        first_name="Kent",
        last_name="Le",
        email="kle4311@gmail.com",
        phone="404-934-0630",
        resume_path="Test Resumes/Kent_Le_Resume.pdf"
    )
    
    browser = LocalBrowserManager()
    results = []
    start = datetime.now()
    
    print("\n" + "="*70)
    print("📝 PROCESSING APPLICATIONS")
    print("="*70)
    
    for i, job in enumerate(test_jobs, 1):
        print(f"\n[{i:2d}/10] {job['company'][:18]:18} | {job['title'][:32]:32}")
        print(f"       {job['url'][:65]}...")
        
        session = None
        try:
            # Create new session for each job
            session = await asyncio.wait_for(
                browser.create_stealth_session(job.get('platform', 'generic')),
                timeout=30.0
            )
            page = session['page']
            
            # Navigate to job
            await asyncio.wait_for(
                page.goto(job['url'], wait_until='domcontentloaded', timeout=30000),
                timeout=35.0
            )
            await asyncio.sleep(2)
            
            # Check for apply button
            apply_selectors = [
                'a:has-text("Apply")',
                'button:has-text("Apply")',
                'a:has-text("Apply Now")',
                'button:has-text("Apply Now")',
                '.apply-button',
                '[data-testid="apply-button"]'
            ]
            
            apply_btn = None
            for selector in apply_selectors:
                try:
                    btn = await page.query_selector(selector)
                    if btn and await btn.is_visible():
                        apply_btn = btn
                        break
                except:
                    continue
            
            if apply_btn:
                print(f"       ✅ Found apply button")
                # Click apply but DON'T submit (safety for test)
                # await apply_btn.click()
                print(f"       ⏸️  PAUSED (would submit here)")
                results.append({'success': True, 'status': 'found_apply_button'})
            else:
                print(f"       ❌ No apply button found")
                results.append({'success': False, 'status': 'no_apply_button'})
            
        except asyncio.TimeoutError:
            print(f"       ⏱️ TIMEOUT")
            results.append({'success': False, 'status': 'timeout'})
        except Exception as e:
            print(f"       💥 {str(e)[:50]}")
            results.append({'success': False, 'status': 'error', 'error': str(e)[:50]})
        finally:
            if session:
                try:
                    await browser.close_session(session['session_id'])
                except:
                    pass
    
    await browser.close_all_sessions()
    
    # Summary
    elapsed = (datetime.now() - start).total_seconds() / 60
    success = sum(1 for r in results if r['success'])
    
    print("\n" + "="*70)
    print("📊 RESULTS")
    print("="*70)
    print(f"Total: {len(results)}")
    print(f"✅ Found apply buttons: {success}")
    print(f"❌ Not found: {len(results) - success}")
    print(f"⏱️  Duration: {elapsed:.1f} minutes")
    print("="*70)
    print("\n⚠️  NOTE: Applications were NOT submitted (test mode)")
    print("   To submit, uncomment the 'await apply_btn.click()' line")
    print("="*70)

asyncio.run(run_tests())
