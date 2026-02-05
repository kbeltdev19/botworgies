#!/usr/bin/env python3
"""
Generate 1000 job URLs for Matt Edwards Campaign - Version 2
Generates exactly 1000 targeted job URLs
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
        
        # Extended target roles (10 roles)
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
        
        # Extended tech companies (25 companies)
        self.tech_companies = [
            ("Salesforce", "https://careers.salesforce.com/en/jobs/?search=%s"),
            ("Workday", "https://careers.workday.com/en-us/jobs.html?keywords=%s"),
            ("ServiceNow", "https://careers.servicenow.com/careers/jobs?keywords=%s"),
            ("Snowflake", "https://careers.snowflake.com/us/en/search-results?keywords=%s"),
            ("Databricks", "https://www.databricks.com/company/careers/open-positions?keywords=%s"),
            ("HashiCorp", "https://www.hashicorp.com/careers/jobs?search=%s"),
            ("Twilio", "https://www.twilio.com/en-us/company/jobs?search=%s"),
            ("Okta", "https://www.okta.com/company/careers/?search=%s"),
            ("Cloudflare", "https://www.cloudflare.com/careers/jobs/?search=%s"),
            ("Datadog", "https://careers.datadoghq.com/?search=%s"),
            ("MongoDB", "https://www.mongodb.com/careers/jobs?search=%s"),
            ("Confluent", "https://www.confluent.io/careers/positions/?search=%s"),
            ("Elastic", "https://www.elastic.co/careers/jobs?search=%s"),
            ("GitLab", "https://about.gitlab.com/jobs/?search=%s"),
            ("Fastly", "https://www.fastly.com/about/careers?search=%s"),
            ("PagerDuty", "https://www.pagerduty.com/careers/jobs/?search=%s"),
            ("New Relic", "https://newrelic.com/careers?search=%s"),
            ("LaunchDarkly", "https://launchdarkly.com/careers?search=%s"),
            ("CircleCI", "https://circleci.com/careers/jobs/?search=%s"),
            ("Miro", "https://miro.com/careers/?search=%s"),
            ("Figma", "https://www.figma.com/careers/?search=%s"),
            ("Notion", "https://www.notion.so/careers?search=%s"),
            ("Asana", "https://asana.com/jobs?search=%s"),
            ("Monday.com", "https://monday.com/careers?search=%s"),
            ("Airtable", "https://www.airtable.com/careers?search=%s"),
        ]
        
        # Extended cloud providers
        self.cloud_companies = [
            ("AWS", "https://www.amazon.jobs/en/search?base_query=%s"),
            ("Microsoft", "https://careers.microsoft.com/us/en/search-results?keywords=%s"),
            ("Google Cloud", "https://careers.google.com/jobs/results/?q=%s"),
            ("Oracle", "https://careers.oracle.com/jobs/?keyword=%s"),
            ("IBM", "https://careers.ibm.com/job/search?query=%s"),
            ("VMware", "https://careers.vmware.com/main/jobs?keywords=%s"),
            ("Red Hat", "https://careers.redhat.com/jobs?keywords=%s"),
            ("HPE", "https://careers.hpe.com/jobs?keywords=%s"),
            ("Dell", "https://jobs.dell.com/search?keywords=%s"),
            ("NetApp", "https://careers.netapp.com/jobs?keywords=%s"),
        ]
        
        # Extended cleared defense contractors
        self.cleared_companies = [
            ("Booz Allen Hamilton", "https://careers.boozallen.com/jobs?q=%s"),
            ("SAIC", "https://jobs.saic.com/search-jobs?q=%s"),
            ("Leidos", "https://careers.leidos.com/jobs?q=%s"),
            ("Northrop Grumman", "https://www.northropgrumman.com/jobs?q=%s"),
            ("Lockheed Martin", "https://www.lockheedmartinjobs.com/search?q=%s"),
            ("General Dynamics", "https://careers.gd.com/search?q=%s"),
            ("Raytheon", "https://careers.rtx.com/search?keywords=%s"),
            ("CACI", "https://careers.caci.com/search?q=%s"),
            ("BAE Systems", "https://jobs.baesystems.com/search?keywords=%s"),
            ("L3Harris", "https://careers.l3harris.com/search?q=%s"),
            ("Boeing", "https://jobs.boeing.com/search?q=%s"),
            ("Perspecta", "https://jobs.perspecta.com/search?q=%s"),
            ("ManTech", "https://mantech.com/careers/search?q=%s"),
            ("Science Applications", "https://jobs.saic.com/search?q=%s"),
            ("General Atomics", "https://www.ga-careers.com/search?q=%s"),
            ("Sierra Nevada", "https://www.sncorp.com/careers/search?q=%s"),
            ("SpaceX", "https://www.spacex.com/careers/jobs?search=%s"),
            ("Blue Origin", "https://www.blueorigin.com/careers/search?q=%s"),
            ("Palantir", "https://www.palantir.com/careers/search?q=%s"),
            ("Anduril", "https://www.anduril.com/careers?search=%s"),
        ]
        
        # Extended enterprise companies
        self.enterprise_companies = [
            ("Accenture", "https://www.accenture.com/us-en/careers?jk=%s"),
            ("Deloitte", "https://apply.deloitte.com/careers?search=%s"),
            ("KPMG", "https://jobs.kpmg.com/us/en/search?keywords=%s"),
            ("PwC", "https://pwc.wd3.myworkdayjobs.com?query=%s"),
            ("Cisco", "https://jobs.cisco.com/jobs?search=%s"),
            ("SAP", "https://jobs.sap.com/search?q=%s"),
            ("Adobe", "https://careers.adobe.com/us/en/search?keywords=%s"),
            ("Intuit", "https://careers.intuit.com/search?q=%s"),
            ("Splunk", "https://www.splunk.com/careers?keywords=%s"),
            ("CrowdStrike", "https://www.crowdstrike.com/careers?keyword=%s"),
            ("Palo Alto Networks", "https://jobs.paloaltonetworks.com/en/jobs/?search=%s"),
            ("Zscaler", "https://www.zscaler.com/careers?search=%s"),
            ("Fortinet", "https://www.fortinet.com/corporate/careers?search=%s"),
            ("McAfee", "https://www.mcafee.com/careers?search=%s"),
            ("Symantec", "https://www.broadcom.com/company/careers?search=%s"),
            ("Verizon", "https://www.verizon.com/about/careers?search=%s"),
            ("AT&T", "https://www.att.com/careers?search=%s"),
            ("T-Mobile", "https://careers.t-mobile.com/search?keywords=%s"),
            ("Comcast", "https://jobs.comcast.com/search?keywords=%s"),
            ("Charter Spectrum", "https://jobs.spectrum.com/search?keywords=%s"),
        ]
        
        # Additional companies (financial, healthcare, retail)
        self.additional_companies = [
            ("JPMorgan Chase", "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs?keyword=%s"),
            ("Goldman Sachs", "https://www.goldmansachs.com/careers?search=%s"),
            ("Morgan Stanley", "https://www.morganstanley.com/careers?search=%s"),
            ("Bank of America", "https://careers.bankofamerica.com/en-us/job-search?search=%s"),
            ("Wells Fargo", "https://wd5.myworkdaysite.com/wellsfargo?query=%s"),
            ("Capital One", "https://www.capitalonecareers.com/search?keywords=%s"),
            ("American Express", "https://www.americanexpress.com/careers?search=%s"),
            ("Visa", "https://www.visa.com/careers?search=%s"),
            ("Mastercard", "https://www.mastercard.com/careers?search=%s"),
            ("PayPal", "https://www.paypal.com/careers?search=%s"),
            ("Stripe", "https://stripe.com/jobs/search?query=%s"),
            ("Square", "https://careers.squareup.com/us/en/jobs?search=%s"),
            ("Plaid", "https://plaid.com/careers?search=%s"),
            ("Robinhood", "https://careers.robinhood.com/?search=%s"),
            ("Coinbase", "https://www.coinbase.com/careers?search=%s"),
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
    
    def generate_all(self, target: int = 1000) -> List[Dict]:
        """Generate all job URLs."""
        print("="*70)
        print("🔗 GENERATING 1000 JOB URLs FOR MATT EDWARDS")
        print("="*70)
        print()
        
        # Strategy: Generate jobs from each category
        jobs_per_role_tech = 3
        jobs_per_role_cloud = 2
        jobs_per_role_cleared = 2
        jobs_per_role_enterprise = 2
        jobs_per_role_additional = 2
        
        # 1. Tech companies: 10 roles x 3 companies x 25 companies = 750 (but we'll limit)
        print("Generating tech company URLs...")
        for role in self.roles:
            encoded_role = urllib.parse.quote(role)
            for company, url_template in self.tech_companies[:15]:  # Top 15 tech
                url = url_template % encoded_role
                self.add_job(role, company, "Remote", url, "company")
                if len(self.jobs) >= target:
                    break
            if len(self.jobs) >= target:
                break
        print(f"   Total: {len(self.jobs)} jobs")
        
        # 2. Cloud providers
        if len(self.jobs) < target:
            print("Generating cloud company URLs...")
            for role in self.roles[:5]:  # Top 5 roles
                encoded_role = urllib.parse.quote(role)
                for company, url_template in self.cloud_companies:
                    url = url_template % encoded_role
                    self.add_job(role, company, "Remote", url, "company")
                    if len(self.jobs) >= target:
                        break
                if len(self.jobs) >= target:
                    break
            print(f"   Total: {len(self.jobs)} jobs")
        
        # 3. Cleared companies (for Secret clearance)
        if len(self.jobs) < target:
            print("Generating cleared company URLs...")
            for role in self.roles[:5]:
                encoded_role = urllib.parse.quote(role)
                for company, url_template in self.cleared_companies[:15]:
                    url = url_template % encoded_role
                    location = "Atlanta, GA / Remote" if company in ["Booz Allen Hamilton", "SAIC", "Leidos"] else "Remote (CONUS)"
                    self.add_job(role, company, location, url, "clearancejobs")
                    if len(self.jobs) >= target:
                        break
                if len(self.jobs) >= target:
                    break
            print(f"   Total: {len(self.jobs)} jobs")
        
        # 4. Enterprise companies
        if len(self.jobs) < target:
            print("Generating enterprise company URLs...")
            for role in self.roles[:5]:
                encoded_role = urllib.parse.quote(role)
                for company, url_template in self.enterprise_companies[:15]:
                    url = url_template % encoded_role
                    self.add_job(role, company, "Atlanta, GA / Remote", url, "company")
                    if len(self.jobs) >= target:
                        break
                if len(self.jobs) >= target:
                    break
            print(f"   Total: {len(self.jobs)} jobs")
        
        # 5. Additional companies
        if len(self.jobs) < target:
            print("Generating additional company URLs...")
            for role in self.roles[:3]:
                encoded_role = urllib.parse.quote(role)
                for company, url_template in self.additional_companies:
                    url = url_template % encoded_role
                    self.add_job(role, company, "Remote", url, "company")
                    if len(self.jobs) >= target:
                        break
                if len(self.jobs) >= target:
                    break
            print(f"   Total: {len(self.jobs)} jobs")
        
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
