#!/usr/bin/env python3
"""
Kent Le - Find Jobs for Application
Quick job discovery using JobSpy
"""

import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters import JobSpyAdapter, SearchConfig


async def find_jobs():
    """Find jobs for Kent Le."""
    print("\n" + "="*70)
    print("🔍 FINDING JOBS FOR KENT LE")
    print("="*70)
    print("\n📋 Search Criteria:")
    print("  • Location: Auburn, AL / Atlanta / Birmingham / Remote")
    print("  • Salary: $75k+")
    print("  • Roles: Customer Success, Account Management, Sales")
    print("  • Posted: Last 7 days")
    print()
    
    adapter = JobSpyAdapter(sites=["indeed"])  # Start with Indeed only
    
    search_terms = [
        "Customer Success Manager",
        "Account Manager",
        "Client Success Manager",
        "Sales Representative",
        "Business Development Representative"
    ]
    
    all_jobs = []
    
    for term in search_terms:
        print(f"Searching: {term}...", end=" ", flush=True)
        
        criteria = SearchConfig(
            roles=[term],
            locations=["Auburn, AL", "Atlanta, GA", "Birmingham, AL", "Remote"],
            posted_within_days=7,
            easy_apply_only=False,
        )
        
        try:
            jobs = await adapter.search_jobs(criteria)
            print(f"Found {len(jobs)} jobs")
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    # Deduplicate
    seen = set()
    unique = []
    for job in all_jobs:
        if job.url not in seen:
            seen.add(job.url)
            unique.append(job)
    
    print(f"\n{'='*70}")
    print(f"✅ Total Unique Jobs Found: {len(unique)}")
    print(f"{'='*70}\n")
    
    # Save results
    output_dir = Path(__file__).parent / "output" / "kent_le_10_real"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    jobs_data = []
    for i, job in enumerate(unique[:20], 1):
        print(f"{i}. {job.title}")
        print(f"   Company: {job.company}")
        print(f"   Location: {job.location}")
        print(f"   Salary: {job.salary_range or 'Not listed'}")
        print(f"   Easy Apply: {job.easy_apply}")
        print(f"   Remote: {job.remote}")
        print(f"   URL: {job.url}")
        print()
        
        jobs_data.append({
            "id": i,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "salary": job.salary_range,
            "easy_apply": job.easy_apply,
            "remote": job.remote,
            "url": job.url,
            "description": job.description[:500] if job.description else "",
        })
    
    # Save to file
    output_file = output_dir / f"found_jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(output_file, 'w') as f:
        json.dump(jobs_data, f, indent=2)
    
    print(f"💾 Saved to: {output_file}")
    
    return unique[:20]


if __name__ == "__main__":
    jobs = asyncio.run(find_jobs())
