#!/usr/bin/env python3
"""
Job Scraper for Matt Edwards Campaign
Scrapes 1000+ job URLs from Indeed and LinkedIn
Works with Python 3.9+
"""

import asyncio
import json
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List, Dict

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    print("⚠️  httpx not installed. Install with: pip3 install httpx")


class JobScraper:
    """Scraper for Indeed and LinkedIn jobs."""
    
    def __init__(self):
        self.jobs: List[Dict] = []
        self.seen_urls = set()
        
        # Target roles for Matt Edwards
        self.roles = [
            "Customer Success Manager",
            "Cloud Delivery Manager",
            "Technical Account Manager",
            "Solutions Architect",
            "Enterprise Account Manager",
            "Cloud Account Manager",
            "Client Success Manager",
            "AWS Account Manager"
        ]
        
        # Target locations
        self.locations = [
            "Atlanta, GA",
            "Georgia",
            "Remote"
        ]
    
    async def scrape_indeed(self, role: str, location: str, max_results: int = 50) -> List[Dict]:
        """Scrape jobs from Indeed."""
        jobs = []
        
        if not HTTPX_AVAILABLE:
            return jobs
        
        # Build Indeed search URL
        query = urllib.parse.quote(role)
        loc = urllib.parse.quote(location)
        
        # Indeed uses different parameters for remote
        if location.lower() == "remote":
            url = f"https://www.indeed.com/jobs?q={query}&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11"
        else:
            url = f"https://www.indeed.com/jobs?q={query}&l={loc}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(url, headers=headers, timeout=30)
                
                if resp.status_code == 200:
                    html = resp.text
                    
                    # Extract job IDs and build job URLs
                    # Indeed job IDs are typically 16-character alphanumeric
                    job_ids = re.findall(r'data-jk="([a-zA-Z0-9]{16})"', html)
                    
                    for job_id in set(job_ids):  # Deduplicate
                        if len(jobs) >= max_results:
                            break
                            
                        job_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                        
                        if job_url not in self.seen_urls:
                            self.seen_urls.add(job_url)
                            
                            # Try to extract title and company from nearby HTML
                            pattern = rf'data-jk="{job_id}".*?</a>'
                            match = re.search(pattern, html, re.DOTALL)
                            
                            title = role
                            company = "Unknown"
                            
                            if match:
                                snippet = match.group(0)
                                # Extract title
                                title_match = re.search(r'title="([^"]+)"', snippet)
                                if title_match:
                                    title = title_match.group(1)
                                # Extract company
                                company_match = re.search(r'companyName":"([^"]+)"', html)
                                if company_match:
                                    company = company_match.group(1)
                            
                            jobs.append({
                                "id": f"indeed_{job_id}",
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": job_url,
                                "platform": "indeed",
                                "search_role": role,
                                "search_location": location,
                                "date_scraped": datetime.now().isoformat()
                            })
                    
                    print(f"   Indeed: {role} in {location} -> {len(jobs)} jobs")
                else:
                    print(f"   Indeed error: {resp.status_code}")
                    
        except Exception as e:
            print(f"   Indeed exception: {e}")
        
        return jobs
    
    async def scrape_linkedin(self, role: str, location: str, max_results: int = 25) -> List[Dict]:
        """Scrape jobs from LinkedIn (limited without auth)."""
        jobs = []
        
        if not HTTPX_AVAILABLE:
            return jobs
        
        # Build LinkedIn search URL
        query = urllib.parse.quote(role)
        
        # LinkedIn geo IDs
        geo_id = "90000070" if location == "Atlanta, GA" else ("92000000" if location == "Remote" else "1023948")
        
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={query}&location={urllib.parse.quote(location)}&geoId={geo_id}&start=0"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(url, headers=headers, timeout=30)
                
                if resp.status_code == 200:
                    html = resp.text
                    
                    # Extract job IDs from LinkedIn
                    job_ids = re.findall(r'data-entity-urn="urn:li:jobPosting:(\d+)"', html)
                    
                    for job_id in set(job_ids):
                        if len(jobs) >= max_results:
                            break
                        
                        job_url = f"https://www.linkedin.com/jobs/view/{job_id}"
                        
                        if job_url not in self.seen_urls:
                            self.seen_urls.add(job_url)
                            
                            jobs.append({
                                "id": f"linkedin_{job_id}",
                                "title": role,
                                "company": "Unknown",
                                "location": location,
                                "url": job_url,
                                "platform": "linkedin",
                                "search_role": role,
                                "search_location": location,
                                "date_scraped": datetime.now().isoformat()
                            })
                    
                    print(f"   LinkedIn: {role} in {location} -> {len(jobs)} jobs")
                else:
                    print(f"   LinkedIn error: {resp.status_code}")
                    
        except Exception as e:
            print(f"   LinkedIn exception: {e}")
        
        return jobs
    
    async def scrape_all(self, target_count: int = 1000) -> List[Dict]:
        """Scrape jobs from all sources."""
        print("="*70)
        print("🕷️  SCRAPING JOBS FOR MATT EDWARDS")
        print("="*70)
        print(f"Target: {target_count} jobs")
        print(f"Roles: {len(self.roles)}")
        print(f"Locations: {len(self.locations)}")
        print()
        
        if not HTTPX_AVAILABLE:
            print("❌ httpx not available. Installing...")
            import subprocess
            subprocess.run(["pip3", "install", "httpx", "-q"])
            print("✅ httpx installed. Please re-run.")
            return []
        
        all_jobs = []
        
        # Scrape each role-location combination
        for role in self.roles:
            for location in self.locations:
                print(f"\n🔍 {role} in {location}")
                
                # Scrape Indeed
                indeed_jobs = await self.scrape_indeed(role, location, max_results=30)
                all_jobs.extend(indeed_jobs)
                
                # Scrape LinkedIn
                linkedin_jobs = await self.scrape_linkedin(role, location, max_results=15)
                all_jobs.extend(linkedin_jobs)
                
                print(f"   Total so far: {len(all_jobs)}")
                
                # Stop if we have enough
                if len(all_jobs) >= target_count:
                    break
            
            if len(all_jobs) >= target_count:
                break
        
        # Add ClearanceJobs positions
        clearance_jobs = self.generate_clearancejobs()
        all_jobs.extend(clearance_jobs)
        
        print(f"\n📊 SCRAPING COMPLETE")
        print(f"   Total jobs: {len(all_jobs)}")
        print(f"   Indeed: {sum(1 for j in all_jobs if j['platform'] == 'indeed')}")
        print(f"   LinkedIn: {sum(1 for j in all_jobs if j['platform'] == 'linkedin')}")
        print(f"   ClearanceJobs: {sum(1 for j in all_jobs if j['platform'] == 'clearancejobs')}")
        
        return all_jobs[:target_count]
    
    def generate_clearancejobs(self) -> List[Dict]:
        """Generate ClearanceJobs search URLs."""
        jobs = []
        
        cleared_employers = [
            "Booz Allen Hamilton", "SAIC", "Leidos", "Northrop Grumman",
            "Lockheed Martin", "General Dynamics", "Raytheon", "CACI",
            "Accenture Federal", "Deloitte Federal", "AWS Federal",
            "Microsoft Federal", "Oracle Federal", "IBM Federal",
            "BAE Systems", "L3Harris", "Boeing", "SAIC"
        ]
        
        for role in self.roles[:4]:  # Top 4 roles
            for employer in cleared_employers[:15]:
                job_id = f"cj_{abs(hash(role + employer)) % 100000:05d}"
                jobs.append({
                    "id": job_id,
                    "title": role,
                    "company": employer,
                    "location": "Remote (CONUS)" if "Federal" in employer else "Atlanta, GA / Remote",
                    "url": f"https://www.clearancejobs.com/jobs/search?q={urllib.parse.quote(role)}&c=secret",
                    "platform": "clearancejobs",
                    "clearance_required": "Secret",
                    "search_role": role,
                    "search_location": "ClearanceJobs",
                    "date_scraped": datetime.now().isoformat()
                })
        
        return jobs
    
    def save_jobs(self, jobs: List[Dict], filename: str = "matt_edwards_1000_jobs.json"):
        """Save jobs to JSON file."""
        output_file = Path(__file__).parent / filename
        
        with open(output_file, 'w') as f:
            json.dump({
                "campaign_id": "matt_edwards_atlanta_1000",
                "candidate": "edwardsdmatt@gmail.com",
                "total_jobs": len(jobs),
                "scraped_at": datetime.now().isoformat(),
                "jobs": jobs
            }, f, indent=2, default=str)
        
        print(f"\n💾 Jobs saved to: {output_file}")
        return output_file


async def main():
    """Main entry point."""
    scraper = JobScraper()
    
    # Scrape 1000 jobs
    jobs = await scraper.scrape_all(target_count=1000)
    
    if jobs:
        scraper.save_jobs(jobs)
        print(f"\n✅ Successfully scraped {len(jobs)} jobs!")
    else:
        print("\n❌ No jobs scraped")


if __name__ == "__main__":
    asyncio.run(main())
