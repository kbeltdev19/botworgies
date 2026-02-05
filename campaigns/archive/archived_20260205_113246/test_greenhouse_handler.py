#!/usr/bin/env python3
"""
Test the optimized Greenhouse handler.

Usage:
    python campaigns/test_greenhouse_handler.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.handlers.greenhouse_optimized import get_greenhouse_handler
from browser.stealth_manager import StealthBrowserManager


async def test_greenhouse_handler():
    """Test the optimized Greenhouse handler with a real job."""
    
    # Test job URL (replace with actual Greenhouse job)
    test_jobs = [
        {
            'id': 'test_001',
            'title': 'Software Engineer',
            'company': 'Test Company',
            'url': 'https://boards.greenhouse.io/demo/jobs/12345',  # Replace with real URL
        }
    ]
    
    # Profile
    profile = {
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'test@example.com',
        'phone': '555-123-4567',
        'linkedin': 'https://linkedin.com/in/testuser',
    }
    
    # Resume path (placeholder)
    resume_path = 'Test Resumes/Kevin_Beltran_Resume.pdf'
    
    print("="*70)
    print("🧪 TESTING GREENHOUSE OPTIMIZED HANDLER")
    print("="*70)
    
    # Get handler
    handler = get_greenhouse_handler()
    print(f"\n✅ Handler initialized")
    print(f"   Stats: {handler.get_stats()}")
    
    # Create browser session
    print("\n🌐 Creating browser session...")
    manager = StealthBrowserManager(prefer_local=True)
    await manager.initialize()
    
    try:
        session = await manager.create_stealth_session('greenhouse', use_proxy=False)
        page = session.page
        
        print(f"✅ Browser session created")
        
        # Navigate to test job
        job = test_jobs[0]
        print(f"\n📄 Testing with job: {job['title']} at {job['company']}")
        print(f"   URL: {job['url']}")
        
        # Note: This would actually apply if the URL was real
        print("\n⚠️  SKIPPING: Test URL is not a real job posting")
        print("   To test with a real job, replace the URL with an actual Greenhouse job URL")
        
        # Print what would happen
        print("\n📋 Handler would:")
        print("   1. Navigate to the job URL")
        print("   2. Click the apply button")
        print("   3. Fill in form fields (first_name, last_name, email, phone)")
        print("   4. Upload resume")
        print("   5. Submit the application")
        print("   6. Verify success with confirmation indicators")
        
        print(f"\n📊 Handler Stats: {handler.get_stats()}")
        
    finally:
        await manager.close()
        print("\n🧹 Browser closed")


if __name__ == "__main__":
    asyncio.run(test_greenhouse_handler())
