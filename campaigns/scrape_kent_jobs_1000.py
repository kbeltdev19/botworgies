#!/usr/bin/env python3
"""
Scrape 1000+ REAL jobs for Kent Le
Uses jobspy with Python 3.11
"""

import sys
sys.path.insert(0, '/Users/tech4/.local/python/lib/python3.11/site-packages')

import json
from pathlib import Path
from datetime import datetime

try:
    from jobspy import scrape_jobs
    print("✅ jobspy loaded")
except ImportError as e:
    print(f"❌ jobspy import failed: {e}")
    sys.exit(1)

# Kent's search criteria
ROLES = [
    "Customer Success Manager",
    "Account Manager",
    "Client Success Manager",
    "Sales Representative",
    "Business Development Representative",
    "Account Executive",
    "Customer Success Specialist",
    "Client Relationship Manager"
]

LOCATIONS = [
    "Auburn, AL",
    "Atlanta, GA",
    "Remote",
    "Alabama",
    "Georgia"
]

def scrape_all_jobs():
    """Scrape 1000+ real jobs"""
    print("="*70)
    print("🕷️  SCRAPING 1000+ REAL JOBS FOR KENT LE")
    print("="*70)
    print(f"Roles: {len(ROLES)}")
    print(f"Locations: {len(LOCATIONS)}")
    print()
    
    all_jobs = []
    seen_urls = set()
    
    for role in ROLES:
        for location in LOCATIONS:
            print(f"🔍 {role} in {location}...")
            
            try:
                jobs = scrape_jobs(
                    site_name=["linkedin", "indeed", "zip_recruiter"],
                    search_term=role,
                    location=location,
                    results_wanted=50,  # 50 per site
                    hours_old=72,  # Last 3 days
                    job_type="fulltime"
                )
                
                if len(jobs) > 0:
                    new_count = 0
                    for _, row in jobs.iterrows():
                        url = row.get('job_url', '')
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            
                            job = {
                                "id": f"{row.get('site', 'unknown')}_{hash(url) % 1000000:06d}",
                                "title": row.get('title', role),
                                "company": row.get('company', 'Unknown'),
                                "location": row.get('location', location),
                                "url": url,
                                "description": str(row.get('description', ''))[:200],
                                "platform": row.get('site', 'unknown'),
                                "date_posted": str(row.get('date_posted', '')),
                                "search_role": role,
                                "is_remote": row.get('is_remote', False),
                                "scraped_at": datetime.now().isoformat()
                            }
                            all_jobs.append(job)
                            new_count += 1
                    
                    print(f"   ✅ +{new_count} new jobs (Total: {len(all_jobs)})")
                else:
                    print(f"   ⚠️  No jobs found")
                    
            except Exception as e:
                print(f"   ❌ Error: {str(e)[:50]}")
                continue
            
            # Stop if we have enough
            if len(all_jobs) >= 1200:
                break
        
        if len(all_jobs) >= 1200:
            break
    
    print(f"\n📊 Scraping complete!")
    print(f"Total unique jobs: {len(all_jobs)}")
    
    # Save to file
    output_file = Path(__file__).parent / "kent_le_real_jobs_1000.json"
    with open(output_file, 'w') as f:
        json.dump({
            "candidate": "Kent Le",
            "email": "kle4311@gmail.com",
            "total_jobs": len(all_jobs),
            "scraped_at": datetime.now().isoformat(),
            "jobs": all_jobs
        }, f, indent=2, default=str)
    
    print(f"💾 Saved to: {output_file}")
    return all_jobs

if __name__ == "__main__":
    jobs = scrape_all_jobs()
    print(f"\n✅ Ready for REAL applications!")
