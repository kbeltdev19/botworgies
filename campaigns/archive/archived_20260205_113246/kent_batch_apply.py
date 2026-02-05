#!/usr/bin/env python3
"""
Kent Le - Batch Job Application Runner
Apply to jobs in batches with automated browser submissions.

Usage:
    python kent_batch_apply.py 100    # Apply to 100 jobs
    python kent_batch_apply.py 500    # Apply to 500 jobs
    python kent_batch_apply.py 1000   # Full campaign
"""

import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters import JobSpyAdapter, SearchConfig


# Job search configurations optimized for Kent
SEARCH_CONFIGS = [
    # High priority - Customer Success
    {"term": "Customer Success Manager", "locations": ["Remote"], "priority": 1},
    {"term": "Customer Success Manager", "locations": ["Atlanta, GA"], "priority": 1},
    {"term": "Client Success Manager", "locations": ["Remote"], "priority": 1},
    
    # High priority - Account Management
    {"term": "Account Manager", "locations": ["Remote"], "priority": 1},
    {"term": "Account Manager", "locations": ["Atlanta, GA"], "priority": 1},
    {"term": "Account Executive", "locations": ["Remote"], "priority": 2},
    
    # Sales roles
    {"term": "Sales Representative", "locations": ["Remote"], "priority": 2},
    {"term": "Business Development Representative", "locations": ["Remote"], "priority": 2},
    {"term": "Sales Development Representative", "locations": ["Remote"], "priority": 2},
    
    # Local/regional
    {"term": "Account Manager", "locations": ["Columbus, GA"], "priority": 3},
    {"term": "Sales Representative", "locations": ["Auburn, AL"], "priority": 3},
    {"term": "Customer Success", "locations": ["Birmingham, AL"], "priority": 3},
]


async def collect_jobs(target_count: int) -> list:
    """Collect jobs from multiple searches."""
    print(f"\n🔍 Collecting jobs for Kent Le...")
    print(f"Target: {target_count} jobs\n")
    
    all_jobs = []
    seen_urls = set()
    
    adapter = JobSpyAdapter(sites=["indeed", "zip_recruiter"])
    
    for config in SEARCH_CONFIGS:
        if len(all_jobs) >= target_count * 1.5:  # Get 50% extra for filtering
            break
        
        print(f"Searching: {config['term']} ({', '.join(config['locations'])})...", end=" ", flush=True)
        
        try:
            criteria = SearchConfig(
                roles=[config['term']],
                locations=config['locations'],
                posted_within_days=14,
                easy_apply_only=False,
            )
            
            jobs = await adapter.search_jobs(criteria)
            
            # Add unique jobs
            new_count = 0
            for job in jobs:
                if job.url not in seen_urls:
                    seen_urls.add(job.url)
                    job.priority = config['priority']
                    all_jobs.append(job)
                    new_count += 1
            
            print(f"Added {new_count} new jobs (total: {len(all_jobs)})")
            
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    print(f"\n✅ Collected {len(all_jobs)} unique jobs")
    return all_jobs


def prioritize_jobs(jobs: list) -> list:
    """Sort jobs by priority and quality."""
    def score_job(job):
        score = 0
        
        # Priority from search config
        score += (4 - getattr(job, 'priority', 3)) * 10
        
        # Easy apply bonus
        if job.easy_apply:
            score += 20
        
        # Remote bonus
        if job.remote or "remote" in job.location.lower():
            score += 15
        
        # Salary bonus
        if job.salary_range:
            salary_str = str(job.salary_range).lower()
            if '80000' in salary_str or '90000' in salary_str or '100000' in salary_str:
                score += 10
            elif '75000' in salary_str or '70000' in salary_str:
                score += 5
        
        # Title relevance
        title = job.title.lower()
        if 'customer success' in title:
            score += 8
        elif 'account manager' in title:
            score += 7
        elif 'account executive' in title:
            score += 6
        elif 'sales' in title:
            score += 4
        
        return score
    
    return sorted(jobs, key=score_job, reverse=True)


def save_job_list(jobs: list, target: int):
    """Save the prioritized job list."""
    output_dir = Path(__file__).parent / "output" / f"kent_batch_{target}_{datetime.now().strftime('%Y%m%d_%H%M')}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save as JSON
    jobs_data = []
    for i, job in enumerate(jobs[:target], 1):
        jobs_data.append({
            "id": i,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "salary": job.salary_range,
            "url": job.url,
            "easy_apply": job.easy_apply,
            "remote": job.remote,
            "priority": getattr(job, 'priority', 3),
        })
    
    jobs_file = output_dir / "jobs_to_apply.json"
    with open(jobs_file, 'w') as f:
        json.dump(jobs_data, f, indent=2)
    
    # Save as CSV for easy viewing
    csv_file = output_dir / "jobs_to_apply.csv"
    with open(csv_file, 'w') as f:
        f.write("ID,Title,Company,Location,Salary,EasyApply,Remote,URL\n")
        for job in jobs_data:
            f.write(f'"{job["id"]}","{job["title"]}","{job["company"]}","{job["location"]}","{job["salary"]}","{job["easy_apply"]}","{job["remote"]}","{job["url"]}"\n')
    
    print(f"\n💾 Saved {len(jobs_data)} jobs to:")
    print(f"   JSON: {jobs_file}")
    print(f"   CSV: {csv_file}")
    
    return output_dir, jobs_data


def print_summary(jobs: list, output_dir: Path):
    """Print summary of jobs to apply."""
    print("\n" + "="*80)
    print("📋 JOBS READY FOR APPLICATION")
    print("="*80)
    
    # Count by category
    easy_apply = sum(1 for j in jobs if j.get('easy_apply', False))
    remote = sum(1 for j in jobs if j.get('remote', False))
    
    print(f"\nTotal: {len(jobs)} jobs")
    print(f"Easy Apply: {easy_apply}")
    print(f"Remote: {remote}")
    print()
    
    # Top 10 preview
    print("Top 10 Jobs:")
    for job in jobs[:10]:
        print(f"\n  {job['id']}. {job['title']}")
        print(f"     Company: {job['company']}")
        print(f"     Location: {job['location']}")
        print(f"     Salary: {job['salary'] or 'Not listed'}")
        print(f"     Easy Apply: {'✅' if job['easy_apply'] else '❌'}")
    
    print(f"\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print(f"1. Review jobs in: {output_dir}/jobs_to_apply.csv")
    print("2. Apply using the application script:")
    print(f"   python campaigns/kent_apply_to_jobs.py {output_dir}/jobs_to_apply.json")
    print("3. Track progress in the generated files")
    print("="*80)


async def main():
    """Main entry point."""
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    
    print("\n" + "🚀"*30)
    print(f"  KENT LE - BATCH JOB COLLECTION")
    print(f"  Target: {target} jobs")
    print("  " + "🚀"*30)
    
    # Collect jobs
    jobs = await collect_jobs(target)
    
    if not jobs:
        print("\n❌ No jobs found!")
        return
    
    # Prioritize
    prioritized = prioritize_jobs(jobs)
    
    # Save
    output_dir, jobs_data = save_job_list(prioritized, target)
    
    # Print summary
    print_summary(jobs_data, output_dir)


if __name__ == "__main__":
    asyncio.run(main())
