"""
Fast 500 Job Collection for Kent Le Test
Uses broader searches to collect jobs quickly
"""

import sys
from pathlib import Path
from jobspy import scrape_jobs
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

print("🔍 FAST 500 JOB COLLECTION FOR KENT LE")
print("="*70)

all_jobs = []
seen_urls = set()

# Broader search queries for faster collection
search_configs = [
    # (query, location, remote, results_wanted)
    ("Customer Success", "United States", True, 150),
    ("Account Manager", "United States", True, 150),
    ("Sales", "United States", True, 100),
    ("Customer Success Manager", "Georgia", False, 50),
    ("Account Manager", "Alabama", False, 50),
]

for query, location, remote, wanted in search_configs:
    if len(all_jobs) >= 500:
        break
    
    print(f"\nSearching: '{query}' in {location} (Remote: {remote})...")
    
    try:
        jobs = scrape_jobs(
            site_name=["linkedin", "indeed", "zip_recruiter"],
            search_term=query,
            location=location,
            is_remote=remote,
            results_wanted=wanted,
            hours_old=168,
            job_type="fulltime"
        )
        
        before_count = len(all_jobs)
        
        for _, job in jobs.iterrows():
            if len(all_jobs) >= 500:
                break
            
            url = job.get('job_url', '')
            if not url or url in seen_urls:
                continue
            
            seen_urls.add(url)
            
            all_jobs.append({
                "title": job.get('title', ''),
                "company": job.get('company', ''),
                "location": job.get('location', ''),
                "url": url,
                "is_remote": job.get('is_remote', False),
                "site": job.get('site', 'unknown')
            })
        
        added = len(all_jobs) - before_count
        print(f"  ✓ Added {added} jobs (Total: {len(all_jobs)})")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")

print(f"\n{'='*70}")
print(f"✅ COLLECTED {len(all_jobs)} JOBS")
print(f"{'='*70}")

# Save URLs
with open("job_urls_500.txt", "w") as f:
    for job in all_jobs:
        f.write(f"{job['url']}\n")

print(f"\nSaved to: job_urls_500.txt")

# Save full data
output = {
    "collection_date": datetime.now().isoformat(),
    "total_jobs": len(all_jobs),
    "candidate": "Kent Le",
    "location": "Auburn, AL / Remote",
    "jobs": all_jobs
}

with open("collected_jobs_500.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"Saved to: collected_jobs_500.json")

# Stats
by_platform = {}
for job in all_jobs:
    site = job['site']
    by_platform[site] = by_platform.get(site, 0) + 1

print(f"\nBy Platform:")
for platform, count in sorted(by_platform.items(), key=lambda x: -x[1]):
    print(f"  {platform}: {count}")

print(f"\n✅ Ready for testing!")
