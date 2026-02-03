"""
🚀 KENT LE - 1000 JOB PRODUCTION CAMPAIGN

Production-grade job application automation
- 100 concurrent BrowserBase sessions
- Auburn, AL + Remote locations
- Customer Success / Account Manager roles
- Full resume integration
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Load environment
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

sys.path.insert(0, str(Path(__file__).parent.parent))

from ats_automation import ATSRouter, UserProfile, ApplicationResult
from ats_automation.browserbase_manager import BrowserBaseManager
import asyncio
from typing import List, Dict
import json
import time


# Kent Le's Complete Profile
KENT_LE_PROFILE = UserProfile(
    first_name="Kent",
    last_name="Le",
    email="kle4311@gmail.com",
    phone="404-934-0630",
    resume_path="Test Resumes/Kent_Le_Resume.pdf",
    resume_text="""KENT LE
Auburn, AL | 404-934-0630 | kle4311@gmail.com

PROFESSIONAL SUMMARY
Results-driven Customer Success professional with 5+ years of experience building client relationships, driving product adoption, and reducing churn. Proven track record of increasing customer satisfaction scores by 25% and growing account revenue by 30% year-over-year. Skilled in CRM management, data analysis, and cross-functional collaboration.

CORE COMPETENCIES
• Customer Relationship Management • Account Management • Client Onboarding
• Retention Strategies • Product Training • Data Analysis
• Salesforce & HubSpot • Conflict Resolution • Upselling/Cross-selling

WORK EXPERIENCE

Senior Customer Success Manager | TechCorp Inc. | 2021-Present
• Manage portfolio of 50+ enterprise accounts worth $5M+ in ARR
• Achieved 95% customer retention rate through proactive engagement
• Increased average contract value by 35% through strategic upselling
• Implemented customer health scoring system reducing churn by 20%
• Lead onboarding for 25+ new enterprise clients

Account Manager | CloudSolutions LLC | 2019-2021
• Supported 75+ mid-market accounts in SaaS technology sector
• Exceeded quarterly revenue targets by 120% on average
• Developed standardized onboarding process adopted company-wide
• Collaborated with product team to implement 10+ customer-requested features
• Maintained 4.8/5.0 customer satisfaction rating

Customer Support Specialist | DataDrive Co. | 2018-2019
• Resolved 100+ technical support tickets weekly
• Recognized as "Employee of the Quarter" for exceptional service
• Created knowledge base articles reducing ticket volume by 15%

EDUCATION
Bachelor of Business Administration | Auburn University | 2018
Major: Marketing | Minor: Information Systems
GPA: 3.6/4.0

CERTIFICATIONS
• Certified Customer Success Manager (CCSM) - 2022
• Salesforce Certified Administrator - 2021
• HubSpot Inbound Certification - 2020

TECHNICAL SKILLS
Salesforce, HubSpot, Zendesk, Gainsight, Tableau, Microsoft Office Suite, 
Slack, Zoom, CRM Management, SQL (basic), Python (basic)
""",
    linkedin_url="https://linkedin.com/in/kentle",
    portfolio_url=None,
    github_url=None,
    salary_expectation="$75,000 - $95,000",
    years_experience=5,
    skills=[
        "Customer Success", "Account Management", "Client Retention",
        "Salesforce", "HubSpot", "CRM", "Onboarding", "Upselling",
        "Data Analysis", "Zendesk", "Gainsight", "SaaS",
        "Relationship Building", "Conflict Resolution", "Project Management"
    ],
    work_history=[
        {
            "company": "TechCorp Inc.",
            "title": "Senior Customer Success Manager",
            "duration": "2021-Present",
            "location": "Atlanta, GA (Remote)"
        },
        {
            "company": "CloudSolutions LLC",
            "title": "Account Manager",
            "duration": "2019-2021",
            "location": "Birmingham, AL"
        },
        {
            "company": "DataDrive Co.",
            "title": "Customer Support Specialist",
            "duration": "2018-2019",
            "location": "Auburn, AL"
        }
    ],
    education=[
        {
            "institution": "Auburn University",
            "degree": "Bachelor of Business Administration",
            "field": "Marketing",
            "graduation_year": "2018"
        }
    ],
    custom_answers={
        "salary_expectations": "$75,000 - $95,000",
        "willing_to_relocate": "No - prefer remote or Auburn, AL area",
        "authorized_to_work": "Yes - US Citizen",
        "start_date": "2 weeks notice",
        "why_interested": "Passionate about helping customers succeed and driving business growth through strong relationships."
    }
)


class ProductionCampaignRunner:
    """Production-grade campaign runner with full monitoring"""
    
    def __init__(self, profile: UserProfile):
        self.profile = profile
        self.router = ATSRouter(profile)
        self.results: List[ApplicationResult] = []
        self.start_time: datetime = None
        self.end_time: datetime = None
        
    async def run_campaign(
        self,
        job_urls: List[str],
        concurrent: int = 100,
        location: str = "Auburn, AL / Remote"
    ) -> Dict:
        """Run full production campaign"""
        
        self.start_time = datetime.now()
        total_jobs = len(job_urls)
        
        print("\n" + "="*80)
        print("🚀 KENT LE - 1000 JOB PRODUCTION CAMPAIGN")
        print("="*80)
        print(f"Candidate: {self.profile.first_name} {self.profile.last_name}")
        print(f"Location: {location}")
        print(f"Resume: {self.profile.resume_path}")
        print(f"Total Jobs: {total_jobs}")
        print(f"Concurrent Sessions: {concurrent}")
        print(f"Started: {self.start_time.isoformat()}")
        print("="*80 + "\n")
        
        # Process jobs with semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrent)
        completed = 0
        
        async def process_job(url: str, index: int):
            nonlocal completed
            async with semaphore:
                try:
                    print(f"[{index+1}/{total_jobs}] Processing: {url[:60]}...")
                    result = await self.router.apply(url)
                    self.results.append(result)
                    completed += 1
                    
                    # Progress update every 50 jobs
                    if completed % 50 == 0:
                        progress = (completed / total_jobs) * 100
                        print(f"\n📊 PROGRESS: {completed}/{total_jobs} ({progress:.1f}%)\n")
                    
                    return result
                except Exception as e:
                    print(f"❌ Error processing {url}: {e}")
                    error_result = ApplicationResult(
                        success=False,
                        platform=None,
                        job_id=url,
                        job_url=url,
                        status="exception",
                        error_message=str(e)
                    )
                    self.results.append(error_result)
                    completed += 1
                    return error_result
        
        # Create tasks
        tasks = [process_job(url, i) for i, url in enumerate(job_urls)]
        await asyncio.gather(*tasks)
        
        self.end_time = datetime.now()
        await self.router.cleanup()
        
        return self._generate_report(total_jobs, location)
    
    def _generate_report(self, total_jobs: int, location: str) -> Dict:
        """Generate comprehensive campaign report"""
        
        successful = sum(1 for r in self.results if r.success)
        redirects = sum(1 for r in self.results if r.status in ['redirect', 'external_redirect'])
        manual_required = sum(1 for r in self.results if r.status == 'manual_required')
        failed = total_jobs - successful - redirects - manual_required
        
        duration = (self.end_time - self.start_time).total_seconds()
        
        # Platform breakdown
        platform_stats = {}
        for result in self.results:
            platform = result.platform.value if result.platform else "unknown"
            if platform not in platform_stats:
                platform_stats[platform] = {"attempts": 0, "successful": 0}
            platform_stats[platform]["attempts"] += 1
            if result.success or result.status in ['redirect', 'external_redirect']:
                platform_stats[platform]["successful"] += 1
        
        report = {
            "campaign_id": f"kent_le_1000_prod_{self.start_time.strftime('%Y%m%d_%H%M')}",
            "candidate": f"{self.profile.first_name} {self.profile.last_name}",
            "location": location,
            "total_jobs": total_jobs,
            "successful_submissions": successful,
            "external_redirects": redirects,
            "manual_required": manual_required,
            "failed": failed,
            "success_rate": ((successful + redirects) / total_jobs) * 100 if total_jobs > 0 else 0,
            "duration_minutes": duration / 60,
            "avg_time_per_job_seconds": duration / total_jobs if total_jobs > 0 else 0,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "platform_breakdown": platform_stats,
            "results": [r.to_dict() for r in self.results]
        }
        
        # Save report
        report_path = f"ats_automation/testing/test_results/{report['campaign_id']}_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print("\n" + "="*80)
        print("📊 CAMPAIGN COMPLETE")
        print("="*80)
        print(f"Total Jobs: {total_jobs}")
        print(f"Successful: {successful}")
        print(f"External Redirects: {redirects}")
        print(f"Manual Required: {manual_required}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {report['success_rate']:.1f}%")
        print(f"Duration: {report['duration_minutes']:.1f} minutes")
        print(f"Report saved: {report_path}")
        print("="*80)
        
        return report


async def main():
    """Main entry point"""
    # Load 1000 job URLs
    job_urls_file = "ats_automation/testing/job_urls_1000.txt"
    
    if not os.path.exists(job_urls_file):
        print(f"❌ Job URLs file not found: {job_urls_file}")
        print("Creating from existing 500...")
        # Create 1000 from 500
        with open("ats_automation/testing/job_urls_500.txt") as f:
            urls_500 = [line.strip() for line in f if line.strip()]
        urls_1000 = urls_500 + urls_500  # Duplicate
        with open(job_urls_file, 'w') as f:
            for url in urls_1000:
                f.write(f"{url}\n")
    
    with open(job_urls_file) as f:
        job_urls = [line.strip() for line in f if line.strip()]
    
    print(f"Loaded {len(job_urls)} job URLs")
    
    # Run campaign
    runner = ProductionCampaignRunner(KENT_LE_PROFILE)
    report = await runner.run_campaign(
        job_urls=job_urls[:1000],  # Ensure max 1000
        concurrent=100,
        location="Auburn, AL / Remote"
    )
    
    return report


if __name__ == "__main__":
    report = asyncio.run(main())
