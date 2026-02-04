#!/usr/bin/env python3
"""
Test single job submission with screenshot verification.
Use this to validate the submission flow before running the full campaign.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from browser.stealth_manager import StealthBrowserManager


async def test_greenhouse_submission():
    """Test a single Greenhouse application with full verification."""
    
    # Test job - find a real Greenhouse job URL for testing
    # Replace with an actual job URL when running
    test_job = {
        'id': 'test_001',
        'title': 'Test Position',
        'company': 'Test Company',
        'url': 'https://boards.greenhouse.io/demo/jobs/12345',  # Replace with real URL
        'platform': 'greenhouse',
    }
    
    profile = {
        'first_name': 'Kevin',
        'last_name': 'Beltran',
        'email': 'beltranrkevin@gmail.com',
        'phone': '770-378-2545',
        'resume_path': '../Test Resumes/Kevin_Beltran_Resume.pdf',
    }
    
    print("="*70)
    print("🧪 SINGLE SUBMISSION TEST")
    print("="*70)
    print(f"Job: {test_job['title']} at {test_job['company']}")
    print(f"URL: {test_job['url']}")
    print(f"Profile: {profile['first_name']} {profile['last_name']} ({profile['email']})")
    print("="*70)
    print("\n⚠️  This will perform a REAL application!")
    print("Press Ctrl+C to cancel, or wait 5 seconds to continue...")
    
    try:
        for i in range(5, 0, -1):
            print(f"  Starting in {i}...")
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return
    
    # Create browser session
    manager = StealthBrowserManager(prefer_local=False)
    await manager.initialize()
    
    try:
        session = await manager.create_stealth_session('greenhouse', use_proxy=True)
        page = session.page
        
        print("\n🌐 Navigating to job URL...")
        await page.goto(test_job['url'], wait_until='domcontentloaded', timeout=20000)
        await asyncio.sleep(2)
        
        # Take initial screenshot
        screenshot_dir = Path("campaigns/output/test_screenshots")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        initial_screenshot = str(screenshot_dir / "01_initial_page.png")
        await page.screenshot(path=initial_screenshot, full_page=True)
        print(f"  📸 Initial screenshot: {initial_screenshot}")
        
        # Check for apply button
        apply_btn = page.locator('#apply_button, .apply-button').first
        if await apply_btn.count() > 0:
            print("  ✅ Apply button found")
            await apply_btn.click()
            await asyncio.sleep(1)
        else:
            print("  ❌ No apply button found - job may be expired or URL invalid")
            return
        
        # Fill form
        print("\n📝 Filling form...")
        
        fields = {
            '#first_name': profile['first_name'],
            '#last_name': profile['last_name'],
            '#email': profile['email'],
            '#phone': profile['phone'],
        }
        
        for selector, value in fields.items():
            field = page.locator(selector).first
            if await field.count() > 0:
                await field.fill(value)
                print(f"  ✓ {selector}: {value}")
            else:
                print(f"  ⚠️ {selector}: not found")
        
        # Resume upload
        resume = page.locator('input[type="file"]').first
        if await resume.count() > 0:
            if Path(profile['resume_path']).exists():
                await resume.set_input_files(profile['resume_path'])
                print(f"  ✓ Resume uploaded: {profile['resume_path']}")
            else:
                print(f"  ⚠️ Resume not found: {profile['resume_path']}")
        
        # Pre-submit screenshot
        pre_submit = str(screenshot_dir / "02_pre_submit.png")
        await page.screenshot(path=pre_submit, full_page=True)
        print(f"\n  📸 Pre-submit screenshot: {pre_submit}")
        
        # Find submit button
        submit = page.locator('input[type="submit"], #submit_app, button[type="submit"]').first
        if await submit.count() > 0:
            print("\n🚀 Clicking submit...")
            await submit.click()
            await asyncio.sleep(3)
        else:
            print("  ❌ No submit button found")
            return
        
        # Post-submit screenshot
        post_submit = str(screenshot_dir / "03_post_submit.png")
        await page.screenshot(path=post_submit, full_page=True)
        print(f"  📸 Post-submit screenshot: {post_submit}")
        
        # Verify success
        current_url = page.url
        print(f"\n🔗 Final URL: {current_url}")
        
        success_indicators = [
            '.thank-you', '.confirmation', '.applied',
            'h1:has-text("Thank")', 'h2:has-text("Thank")',
            '.success-message', '[data-testid="application-success"]'
        ]
        
        success = False
        for indicator in success_indicators:
            if await page.locator(indicator).count() > 0:
                print(f"  ✅ Success indicator found: {indicator}")
                success = True
                break
        
        url_success = 'applied' in current_url.lower() or 'success' in current_url.lower() or 'confirmation' in current_url.lower()
        if url_success:
            print(f"  ✅ URL indicates success: {current_url}")
            success = True
        
        if success:
            print("\n" + "="*70)
            print("✅ TEST PASSED - Application appears successful")
            print("="*70)
            print("\nCheck your email for confirmation!")
        else:
            print("\n" + "="*70)
            print("❌ TEST FAILED - No confirmation detected")
            print("="*70)
            print("\nReview screenshots in campaigns/output/test_screenshots/")
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await manager.close()
        print("\n🧹 Browser closed")


if __name__ == "__main__":
    asyncio.run(test_greenhouse_submission())
