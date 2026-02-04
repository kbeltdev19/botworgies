#!/usr/bin/env python3
"""
Scrape 1000+ jobs for Matt Edwards using JobSpy
Target: Customer Success, Cloud, Account Manager roles
Filter: Easy Apply, Greenhouse, Lever, Workday preferred
"""

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from jobspy import scrape_jobs
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

# Matt's target roles
SEARCH_QUERIES = [
    ("Customer Success Manager", "Remote"),
    ("Customer Success Manager", "Atlanta, GA"),
    ("Cloud Delivery Manager", "Remote"),
    ("Technical Account Manager", "Remote"),
    ("Solutions Architect", "Remote"),
    ("Enterprise Account Manager", "Remote"),
    ("Cloud Account Manager", "Remote"),
    ("AWS Account Manager", "Remote"),
    ("Client Success Manager", "Remote"),
    ("Cloud Customer Success Manager", "Remote"),
]

print("="*80)
print("🕷️  SCRAPING 1000+ JOBS FOR MATT EDWARDS")
print("="*80)

all_jobs = []
seen_urls = set()

for idx, (role, location) in enumerate(SEARCH_QUERIES, 1):
    print(f"\n[{idx}/{len(SEARCH_QUERIES)}] Searching: {role} in {location}")
    
    try:
        jobs = scrape_jobs(
            site_name=['linkedin', 'indeed', 'zip_recruiter'],
            search_term=role,
            location=location,
            results_wanted=150,  # Per site
            hours_old=168,  # Last 7 days
            job_type="fulltime",
            is_remote=True if location == "Remote" else False
        )
        
        print(f"   Found {len(jobs)} jobs")
        
        # Deduplicate and filter
        for _, job in jobs.iterrows():
            url = job.get('job_url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                
                # Determine platform from URL
                platform = "unknown"
                if 'greenhouse.io' in url:
                    platform = "greenhouse"
                elif 'lever.co' in url:
                    platform = "lever"
                elif 'workday.com' in url or 'myworkdayjobs.com' in url:
                    platform = "workday"
                elif 'ashbyhq.com' in url:
                    platform = "ashby"
                elif 'smartrecruiters.com' in url:
                    platform = "smartrecruiters"
                elif 'indeed.com' in url:
                    platform = "indeed"
                elif 'linkedin.com' in url:
                    platform = "linkedin"
                elif 'ziprecruiter.com' in url:
                    platform = "ziprecruiter"
                
                job_data = {
                    'id': f"job_{len(all_jobs)+1:06d}",
                    'title': job.get('title', ''),
                    'company': job.get('company', ''),
                    'location': job.get('location', ''),
                    'url': url,
                    'platform': platform,
                    'description': str(job.get('description', ''))[:500],
                    'is_remote': job.get('is_remote', False),
                    'min_amount': job.get('min_amount'),
                    'max_amount': job.get('max_amount'),
                    'date_posted': str(job.get('date_posted', '')),
                    'search_role': role,
                    'search_location': location
                }
                all_jobs.append(job_data)
        
        print(f"   Total unique: {len(all_jobs)}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        continue

print(f"\n{'='*80}")
print(f"📊 SCRAPING COMPLETE: {len(all_jobs)} total unique jobs")
print("="*80)

# Platform breakdown
from collections import Counter
platforms = Counter(j['platform'] for j in all_jobs)
print("\nBy Platform:")
for platform, count in platforms.most_common():
    print(f"   {platform:15} {count:4d}")

# Save full results
output_dir = Path(__file__).parent / "output" / "matt_edwards_real"
output_dir.mkdir(parents=True, exist_ok=True)

# Save as JSON
jobs_file = output_dir / "scraped_jobs_1000.json"
with open(jobs_file, 'w') as f:
    json.dump({
        'scraped_at': datetime.now().isoformat(),
        'total_jobs': len(all_jobs),
        'candidate': 'Matt Edwards',
        'search_queries': SEARCH_QUERIES,
        'jobs': all_jobs
    }, f, indent=2, default=str)

print(f"\n💾 Saved: {jobs_file}")

# Create filtered list for high-success platforms (Greenhouse, Lever, etc.)
preferred_platforms = ['greenhouse', 'lever', 'ashby', 'workday', 'smartrecruiters']
preferred_jobs = [j for j in all_jobs if j['platform'] in preferred_platforms]

print(f"\n🎯 HIGH-SUCCESS PLATFORMS ({len(preferred_jobs)} jobs):")
for platform in preferred_platforms:
    count = sum(1 for j in preferred_jobs if j['platform'] == platform)
    if count > 0:
        print(f"   {platform:15} {count:4d}")

# Save preferred jobs
preferred_file = output_dir / "preferred_jobs.json"
with open(preferred_file, 'w') as f:
    json.dump({
        'scraped_at': datetime.now().isoformat(),
        'total_jobs': len(preferred_jobs),
        'platforms': preferred_platforms,
        'jobs': preferred_jobs
    }, f, indent=2, default=str)

print(f"\n💾 Saved: {preferred_file}")

# Also save as CSV for easy viewing
df = pd.DataFrame(all_jobs)
csv_file = output_dir / "scraped_jobs_1000.csv"
df.to_csv(csv_file, index=False)
print(f"💾 Saved: {csv_file}")

print("\n✅ Ready for campaign!")
