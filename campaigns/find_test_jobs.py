#!/usr/bin/env python3
"""
Find real test jobs from direct ATS sources for validation.
This script finds actual jobs that we can use to test the submission flow.
"""

import asyncio
import aiohttp
import json
from pathlib import Path


async def find_greenhouse_jobs():
    """Find actual Greenhouse jobs from companies with open positions."""
    
    # List of companies known to use Greenhouse with open roles
    target_companies = [
        'stripe', 'airbnb', 'notion', 'figma', 'linear', 'vercel',
        'datadog', 'mongodb', 'hashicorp', 'gitlab', 'twilio',
        'segment', 'launchdarkly', 'slack', 'uber', 'lyft',
    ]
    
    jobs = []
    
    async with aiohttp.ClientSession() as session:
        for company in target_companies:
            url = f"https://boards.greenhouse.io/{company}.json"
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        company_name = data.get('name', company)
                        
                        for job in data.get('jobs', [])[:3]:  # Get first 3 jobs
                            jobs.append({
                                'company': company_name,
                                'title': job.get('title'),
                                'location': job.get('location', {}).get('name', 'Unknown'),
                                'url': job.get('absolute_url'),
                                'platform': 'greenhouse',
                            })
                        print(f"✅ {company}: {len(data.get('jobs', []))} jobs")
                    else:
                        print(f"⚠️ {company}: HTTP {resp.status}")
            except Exception as e:
                print(f"❌ {company}: {str(e)[:50]}")
                
    return jobs


async def find_lever_jobs():
    """Find actual Lever jobs from companies with open positions."""
    
    target_companies = [
        'netlify', 'prisma', 'planetscale', 'supabase', 'calcom',
    ]
    
    jobs = []
    
    async with aiohttp.ClientSession() as session:
        for company in target_companies:
            url = f"https://api.lever.co/v0/postings/{company}?mode=json"
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        postings = await resp.json()
                        for posting in postings[:3]:
                            jobs.append({
                                'company': company,
                                'title': posting.get('text'),
                                'location': ', '.join([l for l in posting.get('categories', {}).get('location', [])]),
                                'url': posting.get('hostedUrl') or posting.get('applyUrl'),
                                'platform': 'lever',
                            })
                        print(f"✅ {company}: {len(postings)} jobs")
                    else:
                        print(f"⚠️ {company}: HTTP {resp.status}")
            except Exception as e:
                print(f"❌ {company}: {str(e)[:50]}")
                
    return jobs


async def main():
    print("="*70)
    print("🔍 FINDING TEST JOBS")
    print("="*70)
    print("\nSearching for actual jobs from direct ATS sources...")
    print("These can be used to test the application submission flow.\n")
    
    print("📋 Greenhouse jobs:")
    greenhouse_jobs = await find_greenhouse_jobs()
    
    print("\n📋 Lever jobs:")
    lever_jobs = await find_lever_jobs()
    
    all_jobs = greenhouse_jobs + lever_jobs
    
    # Save to file
    output_dir = Path("campaigns/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "test_jobs.json", 'w') as f:
        json.dump(all_jobs, f, indent=2)
    
    print(f"\n" + "="*70)
    print(f"✅ Found {len(all_jobs)} test jobs")
    print(f"📁 Saved to: campaigns/output/test_jobs.json")
    print("="*70)
    
    # Print sample jobs
    print("\n📝 Sample jobs for testing:")
    for i, job in enumerate(all_jobs[:5], 1):
        print(f"\n{i}. {job['title']}")
        print(f"   Company: {job['company']}")
        print(f"   Platform: {job['platform']}")
        print(f"   URL: {job['url']}")
    
    print("\n⚠️  IMPORTANT: Use these URLs in test_single_submission.py")
    print("   to validate the submission flow before running the full campaign.")


if __name__ == "__main__":
    asyncio.run(main())
