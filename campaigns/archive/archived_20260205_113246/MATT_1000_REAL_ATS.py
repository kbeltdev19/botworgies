#!/usr/bin/env python3
"""
🚀 MATT EDWARDS - 1000 REAL JOB APPLICATIONS (ATS AUTOMATION)
20 Concurrent Sessions - Indeed + LinkedIn
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
Customer Success Manager with 5+ years driving cloud adoption, retention, and expansion within AWS partner ecosystems. Proven track record managing $5.5M ACV portfolio with 98% gross retention and $1M+ expansion revenue. Expert in enterprise onboarding, multi-cloud cost optimization, and FedRAMP compliance. Active Secret Security Clearance.

CORE COMPETENCIES
Customer Success: Account Management, Retention, Expansion Revenue, Onboarding, QBRs, Health Scores, NRR/GRR, Churn Reduction
Cloud & Technical: AWS, Azure, GCP, Multi-Cloud, FedRAMP, GovCloud, Cost Optimization, Well-Architected Reviews, SaaS, Implementation
Metrics & Business: $5.5M Portfolio Management, 98% Retention, $1M+ Expansion, ACV/ARR Management, Business Outcomes, ROI Optimization
Security: Secret Clearance (Active), FedRAMP, CompTIA Security+

PROFESSIONAL EXPERIENCE

Cloud Delivery Manager, 2bCloud (AWS Premier Consulting Partner) | Remote | Feb 2026 - Present
- Lead end-to-end customer onboarding and cloud implementation across AWS, Azure, and GCP
- Drive integration setup including IAM/SSO, networking, monitoring/logging, and API integrations
- Manage cloud funding programs (AWS MAP, Azure Migrate & Modernize, GCP funding)
- Coordinate cross-functional delivery teams for successful launch and adoption
- Maintain FedRAMP compliance for government cloud deployments

Customer Success Manager, 2bCloud (AWS Premier Consulting Partner) | Remote | Aug 2022 - Feb 2026
- Managed $5.5M ACV enterprise portfolio achieving 98% gross retention rate (GRR)
- Drove $1M+ expansion revenue through upsell and cross-sell initiatives
- Conducted Quarterly Business Reviews (QBRs) with C-level stakeholders
- Implemented health scoring system reducing churn by 25%
- Managed 25+ enterprise accounts across government (FedRAMP) and commercial sectors

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
        "Security Clearance", "Multi-Cloud", "Portfolio Management",
        "Secret Clearance", "CompTIA Security+", "FedRAMP Compliance"
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
            "degree": "Bachelor of Science in Information Technology",
            "school": "Georgia State University",
            "year": "2018"
        }
    ],
    custom_answers={
        "clearance": "I hold an active Secret Security Clearance",
        "salary": "My salary expectation is $110,000 - $140,000 depending on the total compensation package",
        "remote": "I am seeking fully remote positions",
        "relocation": "I am not willing to relocate but open to remote work"
    }
)


class MattEdwardsRealCampaign:
    """Production campaign runner for Matt Edwards with real job applications"""
    
    def __init__(self, profile: UserProfile):
        self.profile = profile
        self.results: List[ApplicationResult] = []
        self.start_time: datetime = None
        self.end_time: datetime = None
        self.router: ATSRouter = None
        
    async def initialize(self):
        """Initialize ATS router and browser infrastructure"""
        print("\n🌐 Initializing ATS automation infrastructure...")
        self.router = ATSRouter(self.profile)
        
        # Test browser connection
        print("   Testing BrowserBase connection...")
        try:
            await self.router.browser.initialize()
            session = await self.router.browser.create_session("test")
            print(f"   ✅ BrowserBase session created: {session.session_id[:20]}...")
            await self.router.browser.close_session(session.session_id)
            print("   ✅ Infrastructure ready")
        except Exception as e:
            print(f"   ⚠️  Warning: {e}")
            
    async def run_campaign(
        self,
        job_urls: List[str],
        concurrent: int = 20,
        location: str = "Remote (US)"
    ) -> Dict:
        """Run full production campaign"""
        
        await self.initialize()
        
        self.start_time = datetime.now()
        total_jobs = len(job_urls)
        
        print("\n" + "="*80)
        print("🚀 MATT EDWARDS - 1000 REAL JOB APPLICATIONS (ATS AUTOMATION)")
        print("="*80)
        print(f"Candidate: {self.profile.first_name} {self.profile.last_name}")
        print(f"Email: {self.profile.email}")
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
                print(f"[{index+1:4d}/{total_jobs}] ", end="", flush=True)
                
                try:
                    # Apply using ATS router
                    result = await self.router.apply(url)
                    self.results.append(result)
                    
                    # Print result
                    status_icon = "✅" if result.success else "⚠️" if result.redirect_url else "❌"
                    company = result.company_name or "Unknown"
                    print(f"{status_icon} {company[:30]:30} | {result.platform.value:12} | ", end="")
                    
                    if result.success:
                        print("APPLIED")
                    elif result.redirect_url:
                        print(f"REDIRECT → {result.redirect_url[:30]}...")
                    elif result.error_message:
                        print(f"ERROR: {result.error_message[:40]}")
                    else:
                        print("FAILED")
                        
                except Exception as e:
                    print(f"💥 EXCEPTION: {str(e)[:50]}")
                    # Create error result
                    error_result = ApplicationResult(
                        success=False,
                        platform=self.router.detect_platform(url),
                        job_url=url,
                        error_message=str(e),
                        manual_required=True
                    )
                    self.results.append(error_result)
                
                completed += 1
                
                # Progress update every 50 jobs
                if completed % 50 == 0:
                    elapsed = (datetime.now() - self.start_time).total_seconds() / 60
                    progress = (completed / total_jobs) * 100
                    rate = completed / elapsed if elapsed > 0 else 0
                    remaining = (total_jobs - completed) / rate if rate > 0 else 0
                    
                    print(f"\n{'='*80}")
                    print(f"📊 PROGRESS: {completed}/{total_jobs} ({progress:.1f}%) | Elapsed: {elapsed:.1f}min | ETA: {remaining:.1f}min")
                    print(f"{'='*80}\n")
                    
                    # Save intermediate results
                    self._save_progress()
        
        # Create tasks for all jobs
        tasks = [process_job(url, i) for i, url in enumerate(job_urls)]
        
        # Process all jobs
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.end_time = datetime.now()
        
        # Cleanup
        await self.router.browser.cleanup()
        
        return self._generate_report(total_jobs, location)
    
    def _save_progress(self):
        """Save intermediate progress"""
        output_dir = Path(__file__).parent / "output" / "matt_edwards_ats_real"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        progress_file = output_dir / f"progress_{datetime.now().strftime('%H%M%S')}.json"
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "completed": len(self.results),
            "successful": sum(1 for r in self.results if r.success),
            "failed": sum(1 for r in self.results if not r.success and not r.manual_required),
            "manual_required": sum(1 for r in self.results if r.manual_required),
            "results": [
                {
                    "success": r.success,
                    "platform": r.platform.value if r.platform else None,
                    "company": r.company_name,
                    "job_title": r.job_title,
                    "url": r.job_url,
                    "error": r.error_message,
                    "manual_required": r.manual_required,
                    "redirect_url": r.redirect_url
                }
                for r in self.results
            ]
        }
        
        with open(progress_file, 'w') as f:
            json.dump(data, f, indent=2)
            
    def _generate_report(self, total_jobs: int, location: str) -> Dict:
        """Generate final campaign report"""
        
        duration = (self.end_time - self.start_time).total_seconds()
        
        # Calculate stats
        successful = sum(1 for r in self.results if r.success)
        redirects = sum(1 for r in self.results if r.redirect_url and not r.success)
        manual_required = sum(1 for r in self.results if r.manual_required and not r.success)
        failed = total_jobs - successful - redirects - manual_required
        
        # Platform breakdown
        platform_stats = {}
        for result in self.results:
            platform = result.platform.value if result.platform else "unknown"
            if platform not in platform_stats:
                platform_stats[platform] = {"success": 0, "failed": 0, "redirect": 0, "manual": 0}
            
            if result.success:
                platform_stats[platform]["success"] += 1
            elif result.redirect_url:
                platform_stats[platform]["redirect"] += 1
            elif result.manual_required:
                platform_stats[platform]["manual"] += 1
            else:
                platform_stats[platform]["failed"] += 1
        
        report = {
            "campaign_id": "matt_edwards_1000_real_ats",
            "candidate": {
                "name": f"{self.profile.first_name} {self.profile.last_name}",
                "email": self.profile.email,
                "clearance": self.profile.clearance_level
            },
            "timestamp": datetime.now().isoformat(),
            "started": self.start_time.isoformat(),
            "completed": self.end_time.isoformat(),
            "duration_seconds": duration,
            "duration_minutes": duration / 60,
            "total_jobs": total_jobs,
            "successful": successful,
            "redirects": redirects,
            "manual_required": manual_required,
            "failed": failed,
            "success_rate": ((successful + redirects) / total_jobs * 100) if total_jobs > 0 else 0,
            "avg_time_per_job_seconds": duration / total_jobs if total_jobs > 0 else 0,
            "platform_breakdown": platform_stats,
            "all_results": [
                {
                    "success": r.success,
                    "platform": r.platform.value if r.platform else None,
                    "company": r.company_name,
                    "job_title": r.job_title,
                    "job_url": r.job_url,
                    "application_url": r.application_url,
                    "redirect_url": r.redirect_url,
                    "confirmation_number": r.confirmation_number,
                    "error_message": r.error_message,
                    "manual_required": r.manual_required,
                    "fields_filled": r.fields_filled,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None
                }
                for r in self.results
            ]
        }
        
        # Save report
        output_dir = Path(__file__).parent / "output" / "matt_edwards_ats_real"
        output_dir.mkdir(parents=True, exist_ok=True)
        report_file = output_dir / "MATT_1000_FINAL_REPORT.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print("\n" + "="*80)
        print("✅ CAMPAIGN COMPLETE - FINAL REPORT")
        print("="*80)
        print(f"\n📊 RESULTS:")
        print(f"   Total Jobs: {total_jobs}")
        print(f"   ✅ Successful: {successful}")
        print(f"   ↪️  Redirects: {redirects}")
        print(f"   ⚠️  Manual Required: {manual_required}")
        print(f"   ❌ Failed: {failed}")
        print(f"   Success Rate: {report['success_rate']:.1f}%")
        print(f"\n⏱️ TIMING:")
        print(f"   Duration: {report['duration_minutes']:.1f} minutes")
        print(f"   Avg Time/Job: {report['avg_time_per_job_seconds']:.1f} seconds")
        print(f"\n🏢 BY PLATFORM:")
        for platform, stats in platform_stats.items():
            total = sum(stats.values())
            if total > 0:
                sr = (stats['success'] + stats['redirect']) / total * 100
                print(f"   {platform:15} {stats['success']:3d}✓ {stats['redirect']:3d}↪  {stats['manual']:3d}⚠  {stats['failed']:3d}✗ ({sr:.1f}%)")
        print(f"\n💾 Report saved: {report_file}")
        print("="*80)
        
        return report


async def main():
    """Main entry point"""
    
    # Load job URLs
    job_urls_file = Path(__file__).parent.parent / "ats_automation" / "testing" / "job_urls_1000.txt"
    with open(job_urls_file) as f:
        job_urls = [line.strip() for line in f if line.strip()]
    
    print(f"\n{'⚠️'*40}")
    print("⚠️  REAL JOB APPLICATIONS WILL BE SUBMITTED  ⚠️")
    print(f"{'⚠️'*40}")
    print(f"\nCandidate: {MATT_EDWARDS_PROFILE.first_name} {MATT_EDWARDS_PROFILE.last_name}")
    print(f"Email: {MATT_EDWARDS_PROFILE.email}")
    print(f"Resume: {MATT_EDWARDS_PROFILE.resume_path}")
    print(f"\nTarget: {len(job_urls)} real job postings")
    print(f"Platforms: Indeed ({sum(1 for u in job_urls if 'indeed.com' in u)}), LinkedIn ({sum(1 for u in job_urls if 'linkedin.com' in u)})")
    print(f"\nStarting in 10 seconds... (Ctrl+C to cancel)")
    
    try:
        for i in range(10, 0, -1):
            print(f"   {i}...", end="\r")
            await asyncio.sleep(1)
        print("   Go!     ")
        
        # Run campaign
        runner = MattEdwardsRealCampaign(MATT_EDWARDS_PROFILE)
        report = await runner.run_campaign(
            job_urls=job_urls[:1000],
            concurrent=20,
            location="Remote (US)"
        )
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelled by user")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
