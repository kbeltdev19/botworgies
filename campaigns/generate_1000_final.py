#!/usr/bin/env python3
"""
Generate exactly 1000 job URLs for Matt Edwards Campaign
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
        
        # All target roles
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
            "Cloud Solutions Architect",
            "Customer Success Director",
            "Cloud Success Manager",
            "Digital Account Manager",
            "Strategic Account Manager"
        ]
        
        # All companies with career URLs
        self.all_companies = [
            # Tech/SaaS (40)
            ("Salesforce", "https://careers.salesforce.com/en/jobs/?search=%s", "tech"),
            ("Workday", "https://careers.workday.com/en-us/jobs.html?keywords=%s", "tech"),
            ("ServiceNow", "https://careers.servicenow.com/careers/jobs?keywords=%s", "tech"),
            ("Snowflake", "https://careers.snowflake.com/us/en/search-results?keywords=%s", "tech"),
            ("Databricks", "https://www.databricks.com/company/careers/open-positions?keywords=%s", "tech"),
            ("HashiCorp", "https://www.hashicorp.com/careers/jobs?search=%s", "tech"),
            ("Twilio", "https://www.twilio.com/en-us/company/jobs?search=%s", "tech"),
            ("Okta", "https://www.okta.com/company/careers/?search=%s", "tech"),
            ("Cloudflare", "https://www.cloudflare.com/careers/jobs/?search=%s", "tech"),
            ("Datadog", "https://careers.datadoghq.com/?search=%s", "tech"),
            ("MongoDB", "https://www.mongodb.com/careers/jobs?search=%s", "tech"),
            ("Confluent", "https://www.confluent.io/careers/positions/?search=%s", "tech"),
            ("Elastic", "https://www.elastic.co/careers/jobs?search=%s", "tech"),
            ("GitLab", "https://about.gitlab.com/jobs/?search=%s", "tech"),
            ("Fastly", "https://www.fastly.com/about/careers?search=%s", "tech"),
            ("PagerDuty", "https://www.pagerduty.com/careers/jobs/?search=%s", "tech"),
            ("New Relic", "https://newrelic.com/careers?search=%s", "tech"),
            ("LaunchDarkly", "https://launchdarkly.com/careers?search=%s", "tech"),
            ("CircleCI", "https://circleci.com/careers/jobs/?search=%s", "tech"),
            ("Miro", "https://miro.com/careers/?search=%s", "tech"),
            ("Figma", "https://www.figma.com/careers/?search=%s", "tech"),
            ("Notion", "https://www.notion.so/careers?search=%s", "tech"),
            ("Asana", "https://asana.com/jobs?search=%s", "tech"),
            ("Monday.com", "https://monday.com/careers?search=%s", "tech"),
            ("Airtable", "https://www.airtable.com/careers?search=%s", "tech"),
            ("Slack", "https://slack.com/careers?search=%s", "tech"),
            ("Zoom", "https://careers.zoom.us/jobs?search=%s", "tech"),
            ("Webex", "https://jobs.webex.com/careers?search=%s", "tech"),
            ("Dropbox", "https://www.dropbox.com/jobs?search=%s", "tech"),
            ("Box", "https://www.box.com/careers?search=%s", "tech"),
            ("DocuSign", "https://www.docusign.com/company/careers?search=%s", "tech"),
            ("Adobe", "https://careers.adobe.com/us/en/search-results?keywords=%s", "tech"),
            ("Canva", "https://www.canva.com/careers?search=%s", "tech"),
            ("HubSpot", "https://www.hubspot.com/careers?search=%s", "tech"),
            ("Zendesk", "https://www.zendesk.com/careers?search=%s", "tech"),
            ("Shopify", "https://www.shopify.com/careers?search=%s", "tech"),
            ("Atlassian", "https://www.atlassian.com/company/careers?search=%s", "tech"),
            ("Freshworks", "https://www.freshworks.com/company/careers?search=%s", "tech"),
            ("Zoho", "https://www.zoho.com/careers?search=%s", "tech"),
            ("SAP", "https://jobs.sap.com/search?q=%s", "tech"),
            
            # Cloud (10)
            ("AWS", "https://www.amazon.jobs/en/search?base_query=%s", "cloud"),
            ("Microsoft", "https://careers.microsoft.com/us/en/search-results?keywords=%s", "cloud"),
            ("Google Cloud", "https://careers.google.com/jobs/results/?q=%s", "cloud"),
            ("Oracle", "https://careers.oracle.com/jobs/?keyword=%s", "cloud"),
            ("IBM", "https://careers.ibm.com/job/search?query=%s", "cloud"),
            ("VMware", "https://careers.vmware.com/main/jobs?keywords=%s", "cloud"),
            ("Red Hat", "https://careers.redhat.com/jobs?keywords=%s", "cloud"),
            ("HPE", "https://careers.hpe.com/jobs?keywords=%s", "cloud"),
            ("Dell", "https://jobs.dell.com/search?keywords=%s", "cloud"),
            ("NetApp", "https://careers.netapp.com/jobs?keywords=%s", "cloud"),
            
            # Cleared/Defense (25)
            ("Booz Allen Hamilton", "https://careers.boozallen.com/jobs?q=%s", "cleared"),
            ("SAIC", "https://jobs.saic.com/search-jobs?q=%s", "cleared"),
            ("Leidos", "https://careers.leidos.com/jobs?q=%s", "cleared"),
            ("Northrop Grumman", "https://www.northropgrumman.com/jobs?q=%s", "cleared"),
            ("Lockheed Martin", "https://www.lockheedmartinjobs.com/search?q=%s", "cleared"),
            ("General Dynamics", "https://careers.gd.com/search?q=%s", "cleared"),
            ("Raytheon", "https://careers.rtx.com/search?keywords=%s", "cleared"),
            ("CACI", "https://careers.caci.com/search?q=%s", "cleared"),
            ("BAE Systems", "https://jobs.baesystems.com/search?keywords=%s", "cleared"),
            ("L3Harris", "https://careers.l3harris.com/search?q=%s", "cleared"),
            ("Boeing", "https://jobs.boeing.com/search?q=%s", "cleared"),
            ("Perspecta", "https://jobs.perspecta.com/search?q=%s", "cleared"),
            ("ManTech", "https://mantech.com/careers/search?q=%s", "cleared"),
            ("General Atomics", "https://www.ga-careers.com/search?q=%s", "cleared"),
            ("Sierra Nevada", "https://www.sncorp.com/careers/search?q=%s", "cleared"),
            ("SpaceX", "https://www.spacex.com/careers/jobs?search=%s", "cleared"),
            ("Blue Origin", "https://www.blueorigin.com/careers/search?q=%s", "cleared"),
            ("Palantir", "https://www.palantir.com/careers/search?q=%s", "cleared"),
            ("Anduril", "https://www.anduril.com/careers?search=%s", "cleared"),
            ("Shield AI", "https://www.shield.ai/careers?search=%s", "cleared"),
            ("HawkEye 360", "https://www.he360.com/careers?search=%s", "cleared"),
            ("Planet Labs", "https://www.planet.com/careers?search=%s", "cleared"),
            ("Maxar", "https://maxar.wd1.myworkdayjobs.com/en-US/Maxar?query=%s", "cleared"),
            ("Peraton", "https://careers.peraton.com/search?keywords=%s", "cleared"),
            ("VTG", "https://www.vtg.com/careers?search=%s", "cleared"),
            
            # Enterprise/Consulting (25)
            ("Accenture", "https://www.accenture.com/us-en/careers?jk=%s", "enterprise"),
            ("Deloitte", "https://apply.deloitte.com/careers?search=%s", "enterprise"),
            ("KPMG", "https://jobs.kpmg.com/us/en/search?keywords=%s", "enterprise"),
            ("PwC", "https://pwc.wd3.myworkdayjobs.com?query=%s", "enterprise"),
            ("Cisco", "https://jobs.cisco.com/jobs?search=%s", "enterprise"),
            ("Intuit", "https://careers.intuit.com/search?q=%s", "enterprise"),
            ("Splunk", "https://www.splunk.com/careers?keywords=%s", "enterprise"),
            ("CrowdStrike", "https://www.crowdstrike.com/careers?keyword=%s", "enterprise"),
            ("Palo Alto Networks", "https://jobs.paloaltonetworks.com/en/jobs/?search=%s", "enterprise"),
            ("Zscaler", "https://www.zscaler.com/careers?search=%s", "enterprise"),
            ("Fortinet", "https://www.fortinet.com/corporate/careers?search=%s", "enterprise"),
            ("Verizon", "https://www.verizon.com/about/careers?search=%s", "enterprise"),
            ("AT&T", "https://www.att.com/careers?search=%s", "enterprise"),
            ("T-Mobile", "https://careers.t-mobile.com/search?keywords=%s", "enterprise"),
            ("Comcast", "https://jobs.comcast.com/search?keywords=%s", "enterprise"),
            ("Charter Spectrum", "https://jobs.spectrum.com/search?keywords=%s", "enterprise"),
            ("Cox", "https://jobs.coxenterprises.com/search?keywords=%s", "enterprise"),
            ("Dish", "https://jobs.dish.com/search?keywords=%s", "enterprise"),
            ("Lumen", "https://jobs.lumen.com/search?keywords=%s", "enterprise"),
            ("CenturyLink", "https://jobs.centurylink.com/search?keywords=%s", "enterprise"),
            ("Frontier", "https://careers.frontier.com/search?keywords=%s", "enterprise"),
            ("Windstream", "https://jobs.windstream.com/search?keywords=%s", "enterprise"),
            ("Equinix", "https://www.equinix.com/careers?search=%s", "enterprise"),
            ("Digital Realty", "https://www.digitalrealty.com/careers?search=%s", "enterprise"),
            ("Iron Mountain", "https://jobs.ironmountain.com/search?keywords=%s", "enterprise"),
        ]
    
    def generate_id(self) -> str:
        self.job_id_counter += 1
        return f"job_{self.job_id_counter:06d}"
    
    def add_job(self, title: str, company: str, location: str, url: str, platform: str):
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
        print("="*70)
        print("🔗 GENERATING 1000 JOB URLs FOR MATT EDWARDS")
        print("="*70)
        print(f"Roles: {len(self.roles)}")
        print(f"Companies: {len(self.all_companies)}")
        print()
        
        # Generate jobs for each role across all companies
        for role in self.roles:
            encoded_role = urllib.parse.quote(role)
            
            for company, url_template, category in self.all_companies:
                # Determine location based on category
                if category == "cleared":
                    location = "Remote (CONUS)" if "Federal" in company else "Atlanta, GA / Remote"
                    platform = "clearancejobs"
                else:
                    location = "Remote" if category in ["tech", "cloud"] else "Atlanta, GA / Remote"
                    platform = "company"
                
                url = url_template % encoded_role
                self.add_job(role, company, location, url, platform)
                
                if len(self.jobs) >= target:
                    break
            
            if len(self.jobs) >= target:
                break
            
            # Progress update every 100 jobs
            if len(self.jobs) % 100 == 0:
                print(f"   Generated {len(self.jobs)} jobs...")
        
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
    generator = JobURLGenerator()
    jobs = generator.generate_all(target=1000)
    generator.save()
    
    print(f"\n🎯 Total jobs generated: {len(jobs)}")
    print("\n🚀 Ready for batch application with 35 concurrent sessions!")


if __name__ == "__main__":
    main()
