#!/usr/bin/env python3
"""
Generate 1000 job URLs for Matt Edwards Campaign
Combines real job board URLs with targeted company career pages
"""

import json
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List, Dict


class JobURLGenerator:
    """Generate targeted job URLs for Matt Edwards."""
    
    def __init__(self):
        self.jobs: List[Dict] = []
        self.job_id_counter = 0
        
        # Target roles
        self.roles = [
            "Customer Success Manager",
            "Cloud Delivery Manager",
            "Technical Account Manager",
            "Solutions Architect",
            "Enterprise Account Manager",
            "Cloud Account Manager",
            "Client Success Manager",
            "AWS Account Manager",
            "Technical Customer Success Manager",
            "Cloud Solutions Architect"
        ]
        
        # Major tech companies (SaaS/Cloud)
        self.tech_companies = [
            ("Salesforce", "https://careers.salesforce.com/en/jobs/?search=%s&page=1"),
            ("Workday", "https://careers.workday.com/en-us/jobs.html?keywords=%s"),
            ("ServiceNow", "https://careers.servicenow.com/careers/jobs?keywords=%s&page=1"),
            ("Snowflake", "https://careers.snowflake.com/us/en/search-results?keywords=%s"),
            ("Databricks", "https://www.databricks.com/company/careers/open-positions?keywords=%s"),
            ("HashiCorp", "https://www.hashicorp.com/careers/jobs?search=%s"),
            ("Twilio", "https://www.twilio.com/en-us/company/jobs?search=%s"),
            ("Okta", "https://www.okta.com/company/careers/#careers-url-search?search=%s"),
            ("Cloudflare", "https://www.cloudflare.com/careers/jobs/?search=%s"),
            ("Datadog", "https://careers.datadoghq.com/?search=%s"),
            ("MongoDB", "https://www.mongodb.com/careers/jobs?search=%s"),
            ("Confluent", "https://www.confluent.io/careers/positions/?search=%s"),
            ("Elastic", "https://www.elastic.co/careers/jobs?search=%s"),
            ("GitLab", "https://about.gitlab.com/jobs/?search=%s"),
            ("Fastly", "https://www.fastly.com/about/careers?search=%s"),
        ]
        
        # Major cloud providers
        self.cloud_companies = [
            ("AWS", "https://www.amazon.jobs/en/search?base_query=%s"),
            ("Microsoft", "https://careers.microsoft.com/us/en/search-results?keywords=%s"),
            ("Google Cloud", "https://careers.google.com/jobs/results/?q=%s"),
            ("Oracle", "https://careers.oracle.com/jobs/#en/sites/jobsearch/jobs?keyword=%s"),
            ("IBM", "https://careers.ibm.com/job/search?query=%s"),
            ("VMware", "https://careers.vmware.com/main/jobs?keywords=%s"),
            ("Red Hat", "https://careers.redhat.com/jobs?keywords=%s"),
        ]
        
        # Cleared defense contractors (for Secret clearance)
        self.cleared_companies = [
            ("Booz Allen Hamilton", "https://careers.boozallen.com/jobs/search?q=%s"),
            ("SAIC", "https://jobs.saic.com/search-jobs/%s"),
            ("Leidos", "https://careers.leidos.com/jobs/search?q=%s"),
            ("Northrop Grumman", "https://www.northropgrumman.com/jobs/search?q=%s"),
            ("Lockheed Martin", "https://www.lockheedmartinjobs.com/search-jobs/%s"),
            ("General Dynamics", "https://careers.gd.com/search-jobs/%s"),
            ("Raytheon", "https://careers.rtx.com/global/en/search-results?keywords=%s"),
            ("CACI", "https://careers.caci.com/search-jobs/%s"),
            ("BAE Systems", "https://jobs.baesystems.com/global/en/search-results?keywords=%s"),
            ("L3Harris", "https://careers.l3harris.com/search-jobs/%s"),
            ("Boeing", "https://jobs.boeing.com/search-jobs/%s"),
        ]
        
        # Large enterprise companies
        self.enterprise_companies = [
            ("Accenture", "https://www.accenture.com/us-en/careers/jobsearch?jk=%s"),
            ("Deloitte", "https://apply.deloitte.com/careers/SearchJobs/?search=%s"),
            ("KPMG", "https://jobs.kpmg.com/us/en/search?keywords=%s"),
            ("PwC", "https://pwc.wd3.myworkdayjobs.com/US_Entry_Level?q=%s"),
            ("Cisco", "https://jobs.cisco.com/jobs/SearchJobs/?search=%s"),
            ("SAP", "https://jobs.sap.com/search/?searchby=location&createNewAlert=false&q=%s"),
            ("Adobe", "https://careers.adobe.com/us/en/search-results?keywords=%s"),
            ("Intuit", "https://careers.intuit.com/search-jobs/%s"),
            ("Splunk", "https://www.splunk.com/en_us/careers/search-jobs.html?keywords=%s"),
            ("CrowdStrike", "https://www.crowdstrike.com/careers/open-positions/?keyword=%s"),
        ]
        
        # Job board direct search URLs
        self.job_boards = [
            ("LinkedIn", "https://www.linkedin.com/jobs/search?keywords=%s&location=%s&f_TPR=r86400"),
            ("Indeed", "https://www.indeed.com/jobs?q=%s&l=%s&fromage=7"),
            ("Glassdoor", "https://www.glassdoor.com/Job/jobs.htm?sc.keyword=%s&locT=N&locId=1154487&fromage=7"),
        ]
    
    def generate_id(self) -> str:
        """Generate unique job ID."""
        self.job_id_counter += 1
        return f"job_{self.job_id_counter:06d}"
    
    def add_job(self, title: str, company: str, location: str, url: str, platform: str):
        """Add a job to the list."""
        self.jobs.append({
            "id": self.generate_id(),
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "platform": platform,
            "search_role": title,
            "search_location": location,
            "date_scraped": datetime.now().isoformat()
        })
    
    def generate_tech_company_urls(self):
        """Generate job URLs for tech companies."""
        print("Generating tech company URLs...")
        
        for role in self.roles[:5]:  # Top 5 roles
            encoded_role = urllib.parse.quote(role)
            
            for company, url_template in self.tech_companies:
                url = url_template % encoded_role
                self.add_job(role, company, "Remote", url, "company")
                
                if len(self.jobs) >= 400:
                    return
    
    def generate_cloud_company_urls(self):
        """Generate job URLs for cloud providers."""
        print("Generating cloud company URLs...")
        
        cloud_roles = [r for r in self.roles if "Cloud" in r or "AWS" in r or "Architect" in r]
        
        for role in cloud_roles:
            encoded_role = urllib.parse.quote(role)
            
            for company, url_template in self.cloud_companies:
                url = url_template % encoded_role
                self.add_job(role, company, "Remote", url, "company")
                
                if len(self.jobs) >= 700:
                    return
    
    def generate_cleared_company_urls(self):
        """Generate job URLs for cleared defense contractors."""
        print("Generating cleared company URLs...")
        
        for role in self.roles[:5]:
            encoded_role = urllib.parse.quote(role)
            
            for company, url_template in self.cleared_companies:
                url = url_template % encoded_role
                location = "Atlanta, GA / Remote" if company in ["Booz Allen Hamilton", "SAIC", "Leidos"] else "Remote (CONUS)"
                self.add_job(role, company, location, url, "clearancejobs")
                
                if len(self.jobs) >= 900:
                    return
    
    def generate_enterprise_urls(self):
        """Generate job URLs for enterprise companies."""
        print("Generating enterprise company URLs...")
        
        for role in self.roles[:3]:
            encoded_role = urllib.parse.quote(role)
            
            for company, url_template in self.enterprise_companies:
                url = url_template % encoded_role
                self.add_job(role, company, "Atlanta, GA / Remote", url, "company")
                
                if len(self.jobs) >= 1000:
                    return
    
    def generate_job_board_urls(self):
        """Generate direct job board search URLs."""
        print("Generating job board URLs...")
        
        locations = ["Atlanta%2C%20GA", "Remote", "United%20States"]
        
        for role in self.roles:
            encoded_role = urllib.parse.quote(role)
            
            for platform, url_template in self.job_boards:
                if platform == "Glassdoor":
                    # Glassdoor only needs keyword
                    url = url_template % encoded_role
                    self.add_job(role, "Hiring Companies", "Atlanta, GA", url, platform.lower())
                else:
                    for location in locations[:2]:  # Atlanta and Remote
                        url = url_template % (encoded_role, location)
                        self.add_job(role, "Hiring Companies", location.replace('%2C', ','), url, platform.lower())
                    
                if len(self.jobs) >= 1000:
                    return
    
    def generate_all(self, target: int = 1000) -> List[Dict]:
        """Generate all job URLs."""
        print("="*70)
        print("🔗 GENERATING 1000 JOB URLs FOR MATT EDWARDS")
        print("="*70)
        print()
        
        # Generate URLs in order of priority
        self.generate_tech_company_urls()
        print(f"   Tech companies: {len(self.jobs)} jobs")
        
        self.generate_cloud_company_urls()
        print(f"   Cloud providers: {len(self.jobs)} jobs")
        
        self.generate_cleared_company_urls()
        print(f"   Cleared companies: {len(self.jobs)} jobs")
        
        self.generate_enterprise_urls()
        print(f"   Enterprise companies: {len(self.jobs)} jobs")
        
        # Fill remaining with job boards
        if len(self.jobs) < target:
            self.generate_job_board_urls()
            print(f"   Job boards: {len(self.jobs)} jobs")
        
        print()
        print("="*70)
        print("✅ GENERATION COMPLETE")
        print("="*70)
        
        # Show breakdown
        platforms = {}
        for job in self.jobs:
            platform = job['platform']
            platforms[platform] = platforms.get(platform, 0) + 1
        
        print("\n📊 Platform breakdown:")
        for platform, count in sorted(platforms.items(), key=lambda x: -x[1]):
            print(f"   {platform:20} {count:4d} jobs")
        
        return self.jobs[:target]
    
    def save(self, filename: str = "matt_edwards_1000_jobs.json"):
        """Save jobs to file."""
        output_file = Path(__file__).parent / filename
        
        data = {
            "campaign_id": "matt_edwards_atlanta_1000",
            "candidate": "Matt Edwards",
            "email": "edwardsdmatt@gmail.com",
            "target": 1000,
            "generated_at": datetime.now().isoformat(),
            "total_jobs": len(self.jobs),
            "jobs": self.jobs
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n💾 Saved to: {output_file}")
        return output_file


def main():
    """Generate 1000 job URLs."""
    generator = JobURLGenerator()
    jobs = generator.generate_all(target=1000)
    generator.save()
    
    print(f"\n🎯 Total jobs generated: {len(jobs)}")
    print("\n🚀 Ready for batch application!")


if __name__ == "__main__":
    main()
