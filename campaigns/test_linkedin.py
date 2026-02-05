#!/usr/bin/env python3
"""
Test script for LinkedIn Easy Apply and External Apply.
Tests 5 Easy Apply and 5 External Apply applications.

Usage:
    python campaigns/test_linkedin.py --profile campaigns/profiles/kevin_beltran.yaml
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.handlers.linkedin_easy_apply import get_linkedin_handler
from browser.stealth_manager import StealthBrowserManager


class LinkedInTester:
    """Test LinkedIn Easy Apply and External Apply."""
    
    def __init__(self, profile: dict):
        self.profile = profile
        self.resume_path = profile.get('resume_path', 'Test Resumes/Kevin_Beltran_Resume.pdf')
        self.results = {
            'easy_apply': [],
            'external_apply': [],
            'failed': [],
            'start_time': datetime.now().isoformat(),
        }
        
    async def test_job(self, browser_manager, job_url: str, job_type: str) -> dict:
        """Test a single job application."""
        result = {
            'url': job_url,
            'type': job_type,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'error': None,
            'apply_type_detected': None,
        }
        
        try:
            session = await browser_manager.create_stealth_session('linkedin')
            page = session.page
            
            # Load LinkedIn cookies
            handler = get_linkedin_handler()
            await handler.load_linkedin_cookies(session.context)
            
            # Navigate to job
            await page.goto(job_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)
            
            # Apply
            apply_result = await handler.apply(page, self.profile, self.resume_path)
            
            result['success'] = apply_result.success
            result['error'] = apply_result.error
            result['confirmation_id'] = apply_result.confirmation_id
            result['redirect_url'] = apply_result.redirect_url
            
            # Take screenshot
            screenshot_path = f"campaigns/output/test_{job_type}_{int(datetime.now().timestamp())}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            result['screenshot'] = screenshot_path
            
            await browser_manager.close_session(session.session_id)
            
        except Exception as e:
            result['error'] = str(e)
            
        return result
    
    async def run_tests(self, easy_apply_urls: list, external_urls: list):
        """Run all tests."""
        browser_manager = StealthBrowserManager(prefer_local=False)
        await browser_manager.initialize()
        
        print("="*70)
        print("LINKEDIN APPLICATION TESTER")
        print("="*70)
        print(f"Testing {len(easy_apply_urls)} Easy Apply jobs")
        print(f"Testing {len(external_urls)} External Apply jobs")
        print("="*70)
        
        # Test Easy Apply jobs
        print("\n📝 Testing EASY APPLY jobs...")
        for i, url in enumerate(easy_apply_urls, 1):
            print(f"\n  [{i}/{len(easy_apply_urls)}] Testing: {url[:60]}...")
            result = await self.test_job(browser_manager, url, 'easy_apply')
            self.results['easy_apply'].append(result)
            
            if result['success']:
                print(f"      ✓ SUCCESS - Confirmation: {result.get('confirmation_id', 'N/A')}")
            else:
                print(f"      ✗ FAILED - Error: {result.get('error', 'Unknown')[:50]}")
            
            await asyncio.sleep(5)  # Delay between tests
        
        # Test External Apply jobs
        print("\n🔗 Testing EXTERNAL APPLY jobs...")
        for i, url in enumerate(external_urls, 1):
            print(f"\n  [{i}/{len(external_urls)}] Testing: {url[:60]}...")
            result = await self.test_job(browser_manager, url, 'external')
            self.results['external_apply'].append(result)
            
            if result['success']:
                print(f"      ✓ SUCCESS - Redirected to: {result.get('redirect_url', 'N/A')[:40]}...")
            else:
                print(f"      ✗ FAILED - Error: {result.get('error', 'Unknown')[:50]}")
            
            await asyncio.sleep(5)
        
        await browser_manager.close_all()
        
        # Print summary
        self.print_summary()
        
        # Save results
        results_file = f"campaigns/output/linkedin_test_results_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n💾 Results saved to: {results_file}")
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        easy_success = sum(1 for r in self.results['easy_apply'] if r['success'])
        easy_total = len(self.results['easy_apply'])
        
        ext_success = sum(1 for r in self.results['external_apply'] if r['success'])
        ext_total = len(self.results['external_apply'])
        
        print(f"\n📊 EASY APPLY RESULTS:")
        if easy_total > 0:
            print(f"   Success: {easy_success}/{easy_total} ({easy_success/easy_total*100:.1f}%)")
        else:
            print(f"   No Easy Apply jobs tested")
        
        print(f"\n📊 EXTERNAL APPLY RESULTS:")
        if ext_total > 0:
            print(f"   Success: {ext_success}/{ext_total} ({ext_success/ext_total*100:.1f}%)")
        else:
            print(f"   No External Apply jobs tested")
        
        total_success = easy_success + ext_success
        total = easy_total + ext_total
        
        print(f"\n📊 OVERALL:")
        if total > 0:
            print(f"   Success: {total_success}/{total} ({total_success/total*100:.1f}%)")
        else:
            print(f"   No jobs tested")
        
        # List failures
        failures = [r for r in self.results['easy_apply'] + self.results['external_apply'] if not r['success']]
        if failures:
            print(f"\n⚠️  FAILURES:")
            for f in failures:
                print(f"   - {f['type']}: {f['error'][:60]}...")


async def scrape_test_jobs(browser_manager, query: str = "ServiceNow Manager", location: str = "Remote") -> tuple:
    """
    Scrape LinkedIn jobs for testing.
    Returns (easy_apply_urls, external_urls)
    """
    from adapters.job_boards.browserbase_scraper import BrowserBaseScraper
    
    scraper = BrowserBaseScraper(browser_manager)
    
    # Search for jobs
    from adapters.job_boards import SearchCriteria
    criteria = SearchCriteria(
        query=query,
        location=location,
        max_results=20
    )
    
    print(f"🔍 Scraping LinkedIn jobs: {query} in {location}...")
    jobs = await scraper.search(criteria)
    
    # Categorize jobs by type (we'll detect during test)
    job_urls = [job.url for job in jobs if hasattr(job, 'url')]
    
    print(f"   Found {len(job_urls)} jobs")
    
    # Return first 10 for testing (will detect Easy Apply vs External during test)
    return job_urls[:10]


def main():
    parser = argparse.ArgumentParser(description='Test LinkedIn applications')
    parser.add_argument('--profile', type=str, default='campaigns/profiles/kevin_beltran.yaml')
    parser.add_argument('--jobs', type=int, default=10, help='Number of jobs to test (default: 10)')
    
    args = parser.parse_args()
    
    # Load profile
    import yaml
    with open(args.profile) as f:
        profile_data = yaml.safe_load(f)
    
    profile = {
        'first_name': profile_data['name'].split()[0],
        'last_name': profile_data['name'].split()[-1],
        'email': profile_data['email'],
        'phone': profile_data['phone'].replace('-', '').replace('+1-', ''),
        'resume_path': profile_data['resume']['path'],
    }
    
    # Scrape jobs first
    async def run_with_scraping():
        browser_manager = StealthBrowserManager(prefer_local=False)
        await browser_manager.initialize()
        
        try:
            job_urls = await scrape_test_jobs(browser_manager)
            
            if len(job_urls) < 5:
                print("❌ Not enough jobs found for testing")
                return
            
            # Test all scraped jobs (will detect Easy Apply vs External during test)
            tester = LinkedInTester(profile)
            
            print("\n" + "="*70)
            print("TESTING SCRAPED LINKEDIN JOBS")
            print("="*70)
            
            # Test first 5 jobs
            test_jobs = job_urls[:min(args.jobs, len(job_urls))]
            
            easy_apply_urls = []
            external_urls = []
            
            for i, url in enumerate(test_jobs):
                print(f"\n  [{i+1}/{len(test_jobs)}] Analyzing: {url[:50]}...")
                
                # Pre-detect apply type
                session = await browser_manager.create_stealth_session('linkedin')
                page = session.page
                
                # Load LinkedIn cookies
                handler = get_linkedin_handler()
                cookies_loaded = await handler.load_linkedin_cookies(session.context)
                if not cookies_loaded:
                    print("      ⚠️  No cookies loaded - may need authentication")
                
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(3)  # Wait for page to fully load
                    
                    # Quick detect
                    apply_type = await handler._detect_apply_type(page)
                    
                    print(f"      Detected: {apply_type}")
                    
                    if apply_type == 'easy_apply':
                        easy_apply_urls.append(url)
                        print(f"      ✓ Added to Easy Apply list")
                    elif apply_type == 'external':
                        external_urls.append(url)
                        print(f"      ✓ Added to External list")
                    else:
                        print(f"      ⊘ Unknown apply type")
                
                except Exception as e:
                    print(f"      ✗ Error: {e}")
                
                finally:
                    await browser_manager.close_session(session.session_id)
                
                if len(easy_apply_urls) >= 5 and len(external_urls) >= 5:
                    break
                
                await asyncio.sleep(2)
            
            print(f"\n📊 DETECTED:")
            print(f"   Easy Apply jobs: {len(easy_apply_urls)}")
            print(f"   External Apply jobs: {len(external_urls)}")
            
            # Run tests
            await tester.run_tests(easy_apply_urls[:5], external_urls[:5])
            
        finally:
            await browser_manager.close_all()
    
    asyncio.run(run_with_scraping())


if __name__ == '__main__':
    main()
