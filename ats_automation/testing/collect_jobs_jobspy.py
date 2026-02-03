"""
Collect Job URLs using JobSpy for Kent Le's 500-Job Test

Searches multiple platforms and locations, filters by criteria,
exports URLs for testing.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from jobspy import scrape_jobs
import pandas as pd


@dataclass
class JobSearchCriteria:
    """Search criteria for Kent Le"""
    roles: List[str]
    locations: List[str]
    min_salary: int = 75000
    job_type: str = "fulltime"
    remote: bool = True
    hours_old: int = 168  # Last 7 days


# Kent Le's search criteria
KENT_CRITERIA = JobSearchCriteria(
    roles=[
        "Customer Success Manager",
        "Client Success Manager", 
        "Account Manager",
        "Sales Representative",
        "Business Development Representative",
        "Account Executive",
        "Client Relationship Manager",
        "Customer Success Specialist"
    ],
    locations=[
        "Auburn, AL",
        "Atlanta, GA",
        "Birmingham, AL",
        "Montgomery, AL",
        "Remote"
    ],
    min_salary=75000,
    job_type="fulltime",
    remote=True,
    hours_old=168
)


class JobURLCollector:
    """Collects job URLs using JobSpy"""
    
    def __init__(self, criteria: JobSearchCriteria):
        self.criteria = criteria
        self.collected_jobs: List[Dict] = []
        self.stats = {
            "total_found": 0,
            "by_platform": {},
            "by_location": {},
            "salary_meeting_criteria": 0
        }
    
    async def collect_all(self, target_count: int = 500) -> List[Dict]:
        """
        Collect job URLs from all platforms
        
        Args:
            target_count: Target number of jobs to collect
            
        Returns:
            List of job dictionaries with URLs and metadata
        """
        print("\n" + "="*70)
        print("🔍 COLLECTING JOB URLs WITH JOBSPY")
        print("="*70)
        print(f"\nCandidate: Kent Le")
        print(f"Location: Auburn, AL + Remote")
        print(f"Target: {target_count} jobs")
        print(f"Min Salary: ${self.criteria.min_salary:,}")
        print(f"Roles: {len(self.criteria.roles)}")
        print(f"Locations: {len(self.criteria.locations)}")
        print(f"\n{'='*70}\n")
        
        seen_urls = set()
        
        # Search each role + location combination
        for role in self.criteria.roles:
            for location in self.criteria.locations:
                if len(self.collected_jobs) >= target_count:
                    break
                
                print(f"Searching: {role} in {location}...")
                
                try:
                    jobs = self._search_jobs(role, location)
                    
                    new_jobs = 0
                    for _, job in jobs.iterrows():
                        url = job.get('job_url', '')
                        
                        # Skip duplicates
                        if not url or url in seen_urls:
                            continue
                        
                        # Check salary if available
                        min_amt = job.get('min_amount')
                        if min_amt and not self._meets_salary(min_amt, job.get('interval', '')):
                            continue
                        
                        seen_urls.add(url)
                        
                        job_data = {
                            "id": str(hash(url))[:12],
                            "title": job.get('title', ''),
                            "company": job.get('company', ''),
                            "location": job.get('location', ''),
                            "url": url,
                            "description": str(job.get('description', ''))[:200],
                            "is_remote": job.get('is_remote', False),
                            "min_amount": job.get('min_amount'),
                            "max_amount": job.get('max_amount'),
                            "currency": job.get('currency', 'USD'),
                            "interval": job.get('interval'),
                            "site": job.get('site', 'unknown'),
                            "date_posted": str(job.get('date_posted', '')),
                            "search_role": role,
                            "search_location": location
                        }
                        
                        self.collected_jobs.append(job_data)
                        new_jobs += 1
                        
                        # Update stats
                        self._update_stats(job_data)
                        
                        if len(self.collected_jobs) >= target_count:
                            break
                    
                    print(f"  ✓ Found {new_jobs} new jobs (total: {len(self.collected_jobs)})")
                    
                except Exception as e:
                    print(f"  ✗ Error: {e}")
                    continue
            
            if len(self.collected_jobs) >= target_count:
                break
        
        print(f"\n{'='*70}")
        print(f"✅ COLLECTION COMPLETE")
        print(f"{'='*70}")
        print(f"Total jobs collected: {len(self.collected_jobs)}")
        
        return self.collected_jobs
    
    def _search_jobs(self, role: str, location: str) -> pd.DataFrame:
        """Search jobs using JobSpy"""
        is_remote = location == "Remote"
        
        jobs = scrape_jobs(
            site_name=["linkedin", "indeed", "zip_recruiter"],
            search_term=role,
            location="" if is_remote else location,
            is_remote=is_remote,
            results_wanted=100,  # Per site
            hours_old=self.criteria.hours_old,
            job_type=self.criteria.job_type
        )
        
        return jobs
    
    def _meets_salary(self, min_amount: float, interval: str) -> bool:
        """Check if salary meets minimum requirement"""
        if not min_amount:
            return True  # Include if no salary listed
        
        interval_lower = str(interval).lower()
        
        # Convert to yearly
        if 'hour' in interval_lower:
            yearly = min_amount * 2080  # 40 hrs * 52 weeks
        else:
            yearly = min_amount
        
        return yearly >= self.criteria.min_salary
    
    def _update_stats(self, job: Dict):
        """Update collection statistics"""
        self.stats["total_found"] += 1
        
        # By platform
        site = job.get('site', 'unknown')
        self.stats["by_platform"][site] = self.stats["by_platform"].get(site, 0) + 1
        
        # By location
        loc = job.get('search_location', 'unknown')
        self.stats["by_location"][loc] = self.stats["by_location"].get(loc, 0) + 1
        
        # Salary meeting criteria
        if job.get('min_amount'):
            self.stats["salary_meeting_criteria"] += 1
    
    def save_urls(self, filepath: str = "job_urls.txt"):
        """Save just URLs to text file"""
        urls = [job['url'] for job in self.collected_jobs if job.get('url')]
        
        with open(filepath, 'w') as f:
            for url in urls:
                f.write(f"{url}\n")
        
        print(f"\n✅ Saved {len(urls)} URLs to: {filepath}")
    
    def save_full_data(self, filepath: str = "collected_jobs.json"):
        """Save full job data to JSON"""
        output = {
            "collection_date": datetime.now().isoformat(),
            "criteria": {
                "roles": self.criteria.roles,
                "locations": self.criteria.locations,
                "min_salary": self.criteria.min_salary
            },
            "stats": self.stats,
            "jobs": self.collected_jobs
        }
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"✅ Saved full data to: {filepath}")
    
    def print_summary(self):
        """Print collection summary"""
        print(f"\n📊 COLLECTION SUMMARY:")
        print(f"  Total jobs: {self.stats['total_found']}")
        print(f"  With salary data: {self.stats['salary_meeting_criteria']}")
        
        print(f"\n  By Platform:")
        for platform, count in sorted(self.stats["by_platform"].items(), key=lambda x: -x[1]):
            print(f"    {platform}: {count}")
        
        print(f"\n  By Location:")
        for location, count in sorted(self.stats["by_location"].items(), key=lambda x: -x[1]):
            print(f"    {location}: {count}")
        
        # Top companies
        companies = {}
        for job in self.collected_jobs:
            company = job.get('company', 'Unknown')
            companies[company] = companies.get(company, 0) + 1
        
        print(f"\n  Top Companies:")
        for company, count in sorted(companies.items(), key=lambda x: -x[1])[:10]:
            print(f"    {company}: {count}")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Collect job URLs for testing")
    parser.add_argument('--count', type=int, default=500, help='Target number of jobs')
    parser.add_argument('--output', default='job_urls.txt', help='Output file for URLs')
    parser.add_argument('--json', default='collected_jobs.json', help='Output file for full data')
    args = parser.parse_args()
    
    # Create collector
    collector = JobURLCollector(KENT_CRITERIA)
    
    # Collect jobs
    jobs = await collector.collect_all(target_count=args.count)
    
    # Print summary
    collector.print_summary()
    
    # Save outputs
    collector.save_urls(args.output)
    collector.save_full_data(args.json)
    
    print(f"\n{'='*70}")
    print("NEXT STEPS:")
    print(f"{'='*70}")
    print(f"1. URLs saved to: {args.output}")
    print(f"2. Full data saved to: {args.json}")
    print(f"3. Run test with: python quick_test.py --urls {args.output}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
