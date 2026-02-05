#!/usr/bin/env python3
"""Test VisualFormAgentV2 with a single job."""
import asyncio
import sys
sys.path.insert(0, '.')

from adapters.handlers.browser_manager import BrowserManager
from ai.visual_form_agent_v2 import VisualFormAgentV2
import yaml

async def test():
    # Load profile
    with open('campaigns/profiles/kevin_beltran.yaml') as f:
        profile = yaml.safe_load(f)
    
    # Test job - Greenhouse
    job_url = "https://grnh.se/5dqpfgbb6us"
    resume_path = "Test Resumes/Kevin_Beltran_Resume.pdf"
    
    print("Testing VisualFormAgentV2")
    print(f"Job: {job_url}")
    print(f"Email: {profile.get('email')}")
    print(f"Resume: {resume_path}")
    print()
    
    browser = BrowserManager(headless=False)
    _, page = await browser.create_context()
    
    print("1. Navigating...")
    await page.goto(job_url, wait_until='networkidle', timeout=60000)
    await asyncio.sleep(3)
    
    print(f"   URL: {page.url}")
    print(f"   Title: {await page.title()}")
    
    # Screenshot before
    await page.screenshot(path='campaigns/output/v2_before.png')
    print("   Screenshot: v2_before.png")
    
    print("\n2. Running VisualFormAgentV2...")
    agent = VisualFormAgentV2()
    await agent.initialize()
    
    result = await agent.apply(
        page=page,
        profile=profile,
        job_data={'title': 'ServiceNow Developer', 'company': 'Accenture'},
        resume_path=resume_path
    )
    
    print(f"\n3. Result:")
    print(f"   Success: {result.get('success')}")
    print(f"   Verified: {result.get('verified')}")
    print(f"   Confirmation: {result.get('confirmation_id')}")
    print(f"   Error: {result.get('error')}")
    print(f"   Fields filled: {result.get('fields_filled', [])}")
    
    # Screenshot after
    await asyncio.sleep(5)
    await page.screenshot(path='campaigns/output/v2_after.png', full_page=True)
    print("\n   Final screenshot: v2_after.png")
    
    # Check what happened
    final_url = page.url
    print(f"\n   Final URL: {final_url}")
    
    content = await page.content()
    if 'thank you' in content.lower():
        print("   ✅ Found 'thank you' in page!")
    if 'confirmation' in content.lower():
        print("   ✅ Found 'confirmation' in page!")
    
    print("\n✅ Test complete - check screenshots to verify!")

if __name__ == "__main__":
    asyncio.run(test())
