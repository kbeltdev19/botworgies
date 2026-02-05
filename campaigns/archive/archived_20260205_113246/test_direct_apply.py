#!/usr/bin/env python3
"""Test direct application to known job URLs."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

# Test job URLs - mix of direct ATS and Indeed
TEST_JOBS = [
    {
        "title": "Software Engineer",
        "company": "Test Company 1",
        "url": "https://www.indeed.com/viewjob?jk=a677144fd480a6d4",
        "platform": "indeed"
    },
    {
        "title": "IT Project Manager", 
        "company": "Test Company 2",
        "url": "https://www.indeed.com/viewjob?jk=d6a3b095df9bb0d4",
        "platform": "indeed"
    },
]

async def test_applications():
    from campaigns.campaign_runner_v2 import CampaignRunnerV2, CampaignConfig
    
    config = CampaignConfig(
        profile_path="campaigns/profiles/kevin_beltran.yaml",
        resume_path="Test Resumes/Kevin_Beltran_Resume.pdf",
        target_jobs=2,
        daily_limit=10
    )
    
    runner = CampaignRunnerV2(config)
    await runner.initialize()
    
    print(f"Testing {len(TEST_JOBS)} direct job applications...")
    
    for i, job in enumerate(TEST_JOBS, 1):
        print(f"\n[{i}/{len(TEST_JOBS)}] {job['title']} @ {job['company']}")
        result = await runner._apply_to_job(job)
        print(f"Result: {'✅ SUCCESS' if result.get('success') else '❌ FAILED'}")
        if result.get('error'):
            print(f"Error: {result['error']}")
    
    await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(test_applications())
