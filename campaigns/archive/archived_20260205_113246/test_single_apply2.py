#!/usr/bin/env python3
"""Test a single application with full debugging."""
import asyncio
import sys
sys.path.insert(0, '.')

from adapters.handlers.browser_manager import BrowserManager
from ai.visual_form_agent import VisualFormAgent

async def test_accenture_application():
    """Test applying to Accenture job with screenshots."""
    
    job_url = "https://grnh.se/5dqpfgbb6us"
    
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
        browser = BrowserManager(headless=False)
        context, page = await browser.create_context()
        
        # Navigate to job
        print("1. Navigating to job page...")
        await page.goto(job_url, wait_until='networkidle', timeout=60000)
        await asyncio.sleep(3)
        
        title = await page.title()
        print(f"   Page title: {title}")
        
        # Click Apply button
        print("\n2. Clicking Apply button...")
        apply_btn = page.locator('a:has-text("Apply")').first
        if await apply_btn.count() > 0:
            await apply_btn.click()
            print("   Clicked Apply")
        else:
            print("   Apply button not found, may already be on form")
        
        await asyncio.sleep(3)
        await page.screenshot(path='campaigns/output/test_form_before.png')
        print("   Screenshot: test_form_before.png")
        
        # Use Visual Form Agent
        print("\n3. Running Visual Form Agent...")
        agent = VisualFormAgent()
        await agent.initialize()
        
        result = await agent.apply(
            page=page,
            profile=profile,
            job_data={'title': 'ServiceNow Developer', 'company': 'Accenture'},
            max_steps=15
        )
        
        print(f"\n4. Result: {result}")
        
        # Wait and screenshot
        await asyncio.sleep(5)
        await page.screenshot(path='campaigns/output/test_form_after.png', full_page=True)
        print("\n   Final screenshot: test_form_after.png")
        
        # Check page content
        content = await page.content()
        if 'thank' in content.lower() or 'received' in content.lower():
            print("\n   ✅ SUCCESS INDICATOR FOUND!")
        else:
            print("\n   ❌ No success indicator found")
            print(f"   Current URL: {page.url}")
        
        await browser.close()
        
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
