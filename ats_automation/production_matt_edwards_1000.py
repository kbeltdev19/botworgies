"""
🚀 MATT EDWARDS - 1000 JOB PRODUCTION CAMPAIGN (IMPROVED)

Profile: Customer Success Manager with AWS/Cloud expertise
Location: Remote (US)
Clearance: Secret
Target: Customer Success, Account Manager, Cloud Delivery roles
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


# Matt Edwards' Complete Profile
MATT_EDWARDS_PROFILE = UserProfile(
    first_name="Matt",
    last_name="Edwards",
    email="edwardsdmatt@gmail.com",
    phone="770-875-2298",
    resume_path="Test Resumes/Matt_Edwards_Resume.pdf",
    resume_text="""MATT EDWARDS
edwardsdmatt@gmail.com | linkedin.com/in/matt-edwards- | Secret Clearance | Remote

PROFESSIONAL SUMMARY
Customer Success Manager with 5+ years driving cloud adoption, retention, and expansion within AWS partner ecosystems. Proven track record managing $5.5M ACV portfolio with 98% gross retention and $1M+ expansion revenue. Expert in enterprise onboarding, multi-cloud cost optimization, and FedRAMP compliance.

CORE COMPETENCIES
Customer Success: Account Management, Retention, Expansion Revenue, Onboarding, QBRs, Health Scores, NRR/GRR, Churn Reduction
Cloud & Technical: AWS, Azure, GCP, Multi-Cloud, FedRAMP, GovCloud, Cost Optimization, Well-Architected Reviews, SaaS, Implementation
Metrics & Business: $5.5M Portfolio Management, 98% Retention, $1M+ Expansion, ACV/ARR Management, Business Outcomes, ROI Optimization

PROFESSIONAL EXPERIENCE

Cloud Delivery Manager, 2bCloud (AWS Premier Consulting Partner) | Remote | Feb 2026 - Present
- Lead end-to-end customer onboarding and cloud implementation across AWS, Azure, and GCP
- Drive integration setup including IAM/SSO, networking, monitoring/logging, and API integrations
- Manage cloud funding programs (AWS MAP, Azure Migrate & Modernize, GCP funding)
- Coordinate cross-functional delivery teams for successful launch and adoption

Customer Success Manager, 2bCloud (AWS Premier Consulting Partner) | Remote | Aug 2022 - Feb 2026
- Managed $5.5M ACV enterprise portfolio achieving 98% gross retention rate (GRR)
- Drove $1M+ expansion revenue through upsell and cross-sell initiatives
- Conducted Quarterly Business Reviews (QBRs) with C-level stakeholders
- Implemented health scoring system reducing churn by 25%
- Managed 25+ enterprise accounts across government and commercial sectors

EDUCATION
Bachelor of Science in Information Technology | Georgia State University | 2018

CERTIFICATIONS
- AWS Certified Solutions Architect – Associate
- AWS Certified Cloud Practitioner
- CompTIA Security+
- FedRAMP Foundation

CLEARANCE
Secret Security Clearance (Active)
""",
    linkedin_url="https://linkedin.com/in/matt-edwards-",
    portfolio_url=None,
    github_url=None,
    salary_expectation="$110,000 - $140,000",
    years_experience=5,
    skills=[
        "Customer Success", "Account Management", "Cloud Computing",
        "AWS", "Azure", "GCP", "FedRAMP", "GovCloud",
        "Retention", "Expansion Revenue", "QBRs", "Health Scores",
        "Cost Optimization", "SaaS", "Enterprise Onboarding",
        "Security Clearance", "Multi-Cloud", "Portfolio Management"
    ],
    work_history=[
        {
            "company": "2bCloud (AWS Premier Partner)",
            "title": "Cloud Delivery Manager",
            "duration": "2026-Present",
            "location": "Remote"
        },
        {
            "company": "2bCloud (AWS Premier Partner)",
            "title": "Customer Success Manager",
            "duration": "2022-2026",
            "location": "Remote"
        }
    ],
    education=[
        {
            "institution": "Georgia State University",
            "degree": "Bachelor of Science in Information Technology",
            "field": "Information Technology",
            "graduation_year": "2018"
        }
    ],
    custom_answers={
        "salary_expectations": "$110,000 - $140,000",
        "willing_to_relocate": "No - Remote only",
        "authorized_to_work": "Yes - US Citizen with Secret Clearance",
        "start_date": "2 weeks notice",
        "clearance": "Secret Security Clearance (Active)",
        "why_interested": "Passionate about cloud technology and helping enterprises achieve their digital transformation goals through customer success."
    }
)


class MattEdwardsCampaignRunner:
    """Production campaign runner for Matt Edwards"""
    
    def __init__(self, profile: UserProfile):
        self.profile = profile
        self.results: List[ApplicationResult] = []
        self.start_time: datetime = None
        self.end_time: datetime = None
        
    async def run_campaign(
        self,
        job_urls: List[str],
        concurrent: int = 30,  # Reduced for stability
        location: str = "Remote (US)"
    ) -> Dict:
        """Run full production campaign"""
        
        self.start_time = datetime.now()
        total_jobs = len(job_urls)
        
        print("\n" + "="*80)
        print("🚀 MATT EDWARDS - 1000 JOB PRODUCTION CAMPAIGN")
        print("="*80)
        print(f"Candidate: {self.profile.first_name} {self.profile.last_name}")
        print(f"Location: {location}")
        print(f"Clearance: Secret (Active)")
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
                    
                    router = ATSRouter(self.profile)
                    result = await router.apply(url)
                    
                    self.results.append(result)
                    completed += 1
                    
                    # Progress update every 50 jobs
                    if completed % 50 == 0:
                        progress = (completed / total_jobs) * 100
                        elapsed = (datetime.now() - self.start_time).total_seconds() / 60
                        eta = (elapsed / progress) * (100 - progress) if progress > 0 else 0
                        print(f"\n📊 PROGRESS: {completed}/{total_jobs} ({progress:.1f}%) | Elapsed: {elapsed:.1f}min | ETA: {eta:.1f}min\n")
                    
                    return result
                except Exception as e:
                    print(f"❌ Error: {e}")
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
                finally:
                    if 'router' in locals():
                        await router.cleanup()
        
        # Create and run tasks
        tasks = [process_job(url, i) for i, url in enumerate(job_urls)]
        await asyncio.gather(*tasks)
        
        self.end_time = datetime.now()
        
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
                platform_stats[platform] = {"attempts": 0, "successful": 0, "failed": 0}
            platform_stats[platform]["attempts"] += 1
            if result.success or result.status in ['redirect', 'external_redirect']:
                platform_stats[platform]["successful"] += 1
            else:
                platform_stats[platform]["failed"] += 1
        
        report = {
            "campaign_id": f"matt_edwards_1000_{self.start_time.strftime('%Y%m%d_%H%M')}",
            "candidate": f"{self.profile.first_name} {self.profile.last_name}",
            "location": location,
            "clearance": "Secret (Active)",
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
    
    with open(job_urls_file) as f:
        job_urls = [line.strip() for line in f if line.strip()]
    
    print(f"Loaded {len(job_urls)} job URLs")
    
    # Run campaign
    runner = MattEdwardsCampaignRunner(MATT_EDWARDS_PROFILE)
    report = await runner.run_campaign(
        job_urls=job_urls[:1000],
        concurrent=30,  # 30 concurrent for stability
        location="Remote (US)"
    )
    
    return report


if __name__ == "__main__":
    report = asyncio.run(main())
