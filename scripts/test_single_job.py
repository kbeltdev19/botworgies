#!/usr/bin/env python3
"""
Test single job application flow locally.
Run with: python scripts/test_single_job.py
"""

import os
import sys
import asyncio
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load secrets from tokens.env
def load_env():
    tokens_file = os.path.expanduser("~/.clawdbot/secrets/tokens.env")
    if os.path.exists(tokens_file):
        with open(tokens_file) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.strip().split("=", 1)
                    os.environ[key] = val
        print("✓ Loaded secrets from tokens.env")

load_env()

from browser.stealth_manager import StealthBrowserManager
from adapters.indeed import IndeedAdapter
from adapters import SearchConfig, UserProfile, Resume


async def test_search():
    """Test Indeed job search."""
    print("\n=== Testing Indeed Search ===")
    
    manager = StealthBrowserManager()
    adapter = IndeedAdapter(manager)
    
    criteria = SearchConfig(
        roles=["software engineer"],
        locations=["San Francisco"],
        posted_within_days=7,
        easy_apply_only=False
    )
    
    try:
        print("Searching for jobs...")
        start = time.time()
        jobs = await adapter.search_jobs(criteria)
        elapsed = time.time() - start
        
        print(f"\n✓ Found {len(jobs)} jobs in {elapsed:.1f}s")
        
        for i, job in enumerate(jobs[:5]):
            print(f"\n  [{i+1}] {job.title}")
            print(f"      Company: {job.company}")
            print(f"      Location: {job.location}")
            print(f"      Easy Apply: {job.easy_apply}")
            print(f"      URL: {job.url[:60]}...")
        
        return jobs
        
    finally:
        await adapter.close()
        await manager.close_all()


async def test_job_details(job_url: str):
    """Test getting job details."""
    print(f"\n=== Testing Job Details ===")
    print(f"URL: {job_url}")
    
    manager = StealthBrowserManager()
    adapter = IndeedAdapter(manager)
    
    try:
        start = time.time()
        job = await adapter.get_job_details(job_url)
        elapsed = time.time() - start
        
        print(f"\n✓ Got details in {elapsed:.1f}s")
        print(f"  Title: {job.title}")
        print(f"  Company: {job.company}")
        print(f"  Easy Apply: {job.easy_apply}")
        print(f"  Description: {job.description[:200] if job.description else 'N/A'}...")
        
        return job
        
    finally:
        await adapter.close()
        await manager.close_all()


async def main():
    print("🧪 Job Applier Local Test")
    print("=" * 50)
    
    # Test search
    jobs = await test_search()
    
    if jobs:
        # Test getting details for first job
        await test_job_details(jobs[0].url)
    
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
