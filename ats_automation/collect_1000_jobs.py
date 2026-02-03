"""
Collect 1000 Job URLs for Kent Le Production Campaign

Target: 1000 jobs
Location: Auburn, AL + Remote
Roles: Customer Success, Account Manager, Sales, Business Development
Sources: Indeed, LinkedIn, ZipRecruiter
"""

import sys
sys.path.insert(0, '../..')

from jobspy import scrape_jobs
import pandas as pd
from datetime import datetime
import time

# Kent Le's search criteria
SEARCH_TERMS = [
    "Customer Success Manager",
    "Account Manager", 
    "Client Success Manager",
    "Customer Success Specialist",
    "Business Development Representative",
    "Sales Development Representative",
    "Account Executive",
    "Client Relationship Manager"
]

LOCATIONS = [
    "Auburn, AL",
    "Alabama",
    "Remote"
]

TARGET_TOTAL = 1000
collected_jobs = []

print("🚀 Collecting 1000 Job URLs for Kent Le Production Campaign")
print("="*70)

for search_term in SEARCH_TERMS:
    for location in LOCATIONS:
        if len(collected_jobs) >= TARGET_TOTAL:
            break
            
        remaining = TARGET_TOTAL - len(collected_jobs)
        to_fetch = min(remaining, 150)  # Fetch up to 150 per search
        
        print(f"\nSearching: '{search_term}' in '{location}'")
        print(f"Remaining: {remaining} jobs to collect")
        
        try:
            jobs = scrape_jobs(
                site_name=["indeed", "linkedin", "zip_recruiter"],
                search_term=search_term,
                location=location,
                results_wanted=to_fetch,
                hours_old=168,  # Jobs posted in last 7 days
                job_type="fulltime"
            )
            
            if len(jobs) > 0:
                # Get job URLs
                if 'job_url' in jobs.columns:
                    urls = jobs['job_url'].dropna().tolist()
                elif 'url' in jobs.columns:
                    urls = jobs['url'].dropna().tolist()
                else:
                    print(f"No URL column found. Columns: {jobs.columns.tolist()}")
                    continue
                
                # Add unique URLs
                new_urls = [url for url in urls if url not in collected_jobs]
                collected_jobs.extend(new_urls)
                
                print(f"✅ Found {len(urls)} jobs, {len(new_urls)} new unique")
                print(f"Total collected: {len(collected_jobs)}/{TARGET_TOTAL}")
            else:
                print("No jobs found for this search")
                
        except Exception as e:
            print(f"⚠️ Error: {e}")
            continue
        
        # Rate limiting
        time.sleep(2)
    
    if len(collected_jobs) >= TARGET_TOTAL:
        break

# Save results
print("\n" + "="*70)
print(f"✅ COLLECTION COMPLETE: {len(collected_jobs)} jobs")
print("="*70)

# Save to file
output_file = "testing/job_urls_1000.txt"
with open(output_file, 'w') as f:
    for url in collected_jobs[:TARGET_TOTAL]:
        f.write(f"{url}\n")

print(f"\n💾 Saved to: {output_file}")

# Show breakdown
indeed_count = sum(1 for url in collected_jobs if 'indeed.com' in url)
linkedin_count = sum(1 for url in collected_jobs if 'linkedin.com' in url)
other_count = len(collected_jobs) - indeed_count - linkedin_count

print(f"\n📊 Platform Breakdown:")
print(f"   Indeed:   {indeed_count} ({indeed_count/len(collected_jobs)*100:.1f}%)")
print(f"   LinkedIn: {linkedin_count} ({linkedin_count/len(collected_jobs)*100:.1f}%)")
print(f"   Other:    {other_count} ({other_count/len(collected_jobs)*100:.1f}%)")
