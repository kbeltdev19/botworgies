#!/usr/bin/env python3
"""Test a single application with full debugging."""
import asyncio
import sys
sys.path.insert(0, '.')

from adapters.handlers.browser_manager import BrowserManager
from ai.visual_form_agent import VisualFormAgent
from playwright.async_api import async_playwright

async def test_accenture_application():
    """Test applying to Accenture job with screenshots."""
    
    # Test job - Accenture Greenhouse
    job_url = "https://grnh.se/5dqpfgbb6us"  # ServiceNow Developer, Jr.
    
    profile = {
        'first_name': 'Kevin',
        'last_name': 'Beltran',
        'email': 'beltranrkevin@gmail.com',
        'phone': '+1-770-378-2545'
    }
    
    print(f"Testing application to: {job_url}")
    print(f"Profile email: {profile['email']}")
    print()
    
    browser = None
    try:
        # Initialize browser
        browser = BrowserManager(headless=False)  # Visible for debugging
        context, page = await browser.create_context()
        
        # Navigate to job
        print("1. Navigating to job page...")
        await page.goto(job_url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(3)
        
        # Take screenshot of initial page
        await page.screenshot(path='campaigns/output/test_1_initial.png')
        print("   Screenshot saved: test_1_initial.png")
        
        # Get page title
        title = await page.title()
        print(f"   Page title: {title}")
        
        # Check if it's a job page
        content = await page.content()
        if "404" in content or "Not Found" in content:
            print("   ❌ ERROR: Job page not found (404)")
            return
        
        # Look for apply button
        print("\n2. Looking for apply button...")
        apply_selectors = [
            'a:has-text("Apply")',
            'button:has-text("Apply")',
            'a[href*="apply"]',
            '[data-qa="btn-apply"]',
        ]
        
        apply_button = None
        for selector in apply_selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    apply_button = element
                    print(f"   Found apply button: {selector}")
                    break
            except:
                continue
        
        if not apply_button:
            print("   ❌ ERROR: No apply button found")
            # Take screenshot
            await page.screenshot(path='campaigns/output/test_2_no_apply.png')
            return
        
        # Click apply
        print("\n3. Clicking apply button...")
        await apply_button.click()
        await asyncio.sleep(3)
        
        await page.screenshot(path='campaigns/output/test_3_after_apply_click.png')
        print("   Screenshot saved: test_3_after_apply_click.png")
        
        # Check current URL
        current_url = page.url
        print(f"   Current URL: {current_url}")
        
        # Look for form fields
        print("\n4. Looking for form fields...")
        form_fields = {
            'name': ['input[name*="name"]', 'input[placeholder*="name" i]', '#first_name', '#name'],
            'email': ['input[type="email"]', 'input[name*="email"]', '#email'],
            'phone': ['input[type="tel"]', 'input[name*="phone"]', '#phone'],
        }
        
        for field_name, selectors in form_fields.items():
            found = False
            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        print(f"   Found {field_name} field: {selector}")
                        found = True
                        break
                except:
                    continue
            if not found:
                print(f"   ❌ {field_name} field NOT found")
        
        # Use Visual Form Agent
        print("\n5. Using Visual Form Agent...")
        agent = VisualFormAgent()
        await agent.initialize()
        
        job_data = {
            'title': 'ServiceNow Developer',
            'company': 'Accenture Federal Services'
        }
        
        result = await agent.apply(
            page=page,
            profile=profile,
            job_data=job_data,
            max_steps=10
        )
        
        print(f"\n6. Visual Agent Result:")
        print(f"   Success: {result.get('success')}")
        print(f"   Confirmation ID: {result.get('confirmation_id')}")
        print(f"   Actions taken: {len(result.get('actions', []))}")
        
        # Take final screenshot
        await asyncio.sleep(2)
        await page.screenshot(path='campaigns/output/test_4_final.png', full_page=True)
        print("\n   Final screenshot saved: test_4_final.png")
        
        # Check for success indicators
        print("\n7. Checking for success indicators...")
        content = await page.content()
        
        success_indicators = [
            'thank you',
            'application received',
            'successfully submitted',
            'confirmation',
            'we have received',
        ]
        
        found_indicator = False
        for indicator in success_indicators:
            if indicator.lower() in content.lower():
                print(f"   ✅ Found success indicator: '{indicator}'")
                found_indicator = True
                break
        
        if not found_indicator:
            print("   ❌ No success indicator found on page")
            print("   Page may show form errors or still be on application page")
        
        await browser.close()
        print("\n✅ Test complete!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        if browser:
            try:
                await browser.close()
            except:
                pass

if __name__ == "__main__":
    asyncio.run(test_accenture_application())
