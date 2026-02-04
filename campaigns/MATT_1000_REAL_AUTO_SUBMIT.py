#!/usr/bin/env python3
"""
MATT EDWARDS - 1000 REAL JOB APPLICATIONS (AUTO-SUBMIT ENABLED)

⚠️  WARNING: This will ACTUALLY submit job applications!
     - Auto-submit is ENABLED
     - BrowserBase is CONNECTED  
     - Real forms will be filled and submitted
     - You WILL receive confirmation emails
"""

import sys
import os
from pathlib import Path

# Load environment
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value  # Set directly, don't use setdefault
                
print(f"Env check: BROWSERBASE_API_KEY={'Set' if os.environ.get('BROWSERBASE_API_KEY') else 'NOT SET'}")

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
from datetime import datetime
from typing import List, Dict

try:
    from ats_automation import ATSRouter, UserProfile, ApplicationResult
    from ats_automation.browserbase_manager import BrowserBaseManager
    ATS_AVAILABLE = True
except ImportError as e:
    print(f"❌ ATS Automation not available: {e}")
    ATS_AVAILABLE = False


# Matt Edwards Profile
MATT_PROFILE = UserProfile(
    first_name="Matt",
    last_name="Edwards",
    email="edwardsdmatt@gmail.com",
    phone="404-680-8472",
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
    salary_expectation="$110,000 - $140,000",
    years_experience=5,
    skills=[
        "Customer Success", "Account Management", "Cloud Computing",
        "AWS", "Azure", "GCP", "FedRAMP", "GovCloud",
        "Retention", "Expansion Revenue", "QBRs", "Health Scores",
        "Cost Optimization", "SaaS", "Enterprise Onboarding",
        "Security Clearance", "Multi-Cloud", "Portfolio Management"
    ],
    custom_answers={
        "salary_expectations": "$110,000 - $140,000",
        "willing_to_relocate": "No - Remote only",
        "authorized_to_work": "Yes - US Citizen with Secret Clearance",
        "start_date": "2 weeks notice",
        "clearance": "Secret Security Clearance (Active)"
    }
)


class MattProductionRunner:
    """PRODUCTION RUNNER - ACTUALLY SUBMITS APPLICATIONS"""
    
    def __init__(self, profile: UserProfile):
        self.profile = profile
        self.results = []
        
    async def run_real_campaign(
        self,
        job_urls: List[str],
        concurrent: int = 20,
        auto_submit: bool = True
    ) -> Dict:
        """Run REAL production campaign"""
        
        print("\n" + "="*70)
        print("🚀 MATT EDWARDS - 1000 REAL JOB APPLICATIONS")
        print("="*70)
        print(f"⚠️  MODE: {'REAL APPLICATIONS (AUTO-SUBMIT)' if auto_submit else 'TEST MODE'}")
        print(f"📧 Email: {self.profile.email}")
        print(f"📍 Location: Atlanta, GA / Remote")
        print(f"🔐 Clearance: Secret (Active)")
        print(f"📋 Jobs: {len(job_urls)}")
        print(f"⚡ Concurrent: {concurrent}")
        print(f"⏰ Started: {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)
        
        if auto_submit:
            print("\n⚠️  ⚠️  ⚠️  WARNING  ⚠️  ⚠️  ⚠️")
            print("AUTO-SUBMIT IS ENABLED!")
            print("This will ACTUALLY submit job applications!")
            print("You WILL receive confirmation emails from job sites.")
            print("⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️\n")
            await asyncio.sleep(5)
        
        if not ATS_AVAILABLE:
            print("❌ ATS Automation module not available")
            return {"error": "ATS not available"}
        
        # BrowserBase is initialized by ATSRouter
        print("Initializing ATS Router...")
        print("✅ Ready")
        
        # Process with concurrency
        semaphore = asyncio.Semaphore(concurrent)
        completed = 0
        successful = 0
        
        async def process_job(url: str, index: int):
            nonlocal completed, successful
            
            async with semaphore:
                print(f"[{index+1:4d}/{len(job_urls)}] {url[:60]}...")
                
                try:
                    router = ATSRouter(self.profile)
                    
                    # Apply to job (router handles submission)
                    result = await router.apply(url)
                    
                    self.results.append(result)
                    completed += 1
                    
                    if result.success:
                        successful += 1
                        status = "✅ SUBMITTED" if auto_submit else "✅ TEST PASSED"
                    else:
                        status = f"❌ FAILED: {result.error_message[:40]}"
                    
                    print(f"   {status}")
                    
                    # Progress every 50
                    if completed % 50 == 0:
                        print(f"\n📊 Progress: {completed}/{len(job_urls)} | "
                              f"Success: {successful} | {datetime.now().strftime('%H:%M:%S')}\n")
                    
                    return result
                    
                except Exception as e:
                    print(f"   ❌ ERROR: {str(e)[:50]}")
                    completed += 1
                    return None
                finally:
                    if 'router' in locals():
                        await router.cleanup()
        
        # Run all jobs
        start_time = datetime.now()
        tasks = [process_job(url, i) for i, url in enumerate(job_urls)]
        await asyncio.gather(*tasks, return_exceptions=True)
        end_time = datetime.now()
        
        # No browser cleanup needed - handled by ATSRouter
        
        # Report
        duration_mins = (end_time - start_time).total_seconds() / 60
        
        report = {
            "campaign_id": f"matt_edwards_real_{start_time.strftime('%Y%m%d_%H%M')}",
            "mode": "REAL_APPLICATIONS" if auto_submit else "TEST",
            "total_jobs": len(job_urls),
            "completed": completed,
            "successful": successful,
            "failed": completed - successful,
            "success_rate": (successful / completed * 100) if completed > 0 else 0,
            "duration_minutes": duration_mins,
            "auto_submit": auto_submit,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        # Save report
        output_dir = Path("campaigns/output/matt_edwards_real")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"real_campaign_{start_time.strftime('%Y%m%d_%H%M')}.json"
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print("\n" + "="*70)
        print("✅ CAMPAIGN COMPLETE")
        print("="*70)
        print(f"Mode: {'🚀 REAL APPLICATIONS' if auto_submit else '✅ TEST MODE'}")
        print(f"Total: {completed}")
        print(f"Successful: {successful}")
        print(f"Failed: {completed - successful}")
        print(f"Success Rate: {report['success_rate']:.1f}%")
        print(f"Duration: {duration_mins:.1f} minutes")
        print(f"Report: {report_path}")
        
        if auto_submit:
            print("\n📧 You should receive confirmation emails from job sites")
            print("   within the next 24 hours.")
        
        print("="*70)
        
        return report


async def main():
    """Main entry point"""
    
    # Load job URLs
    job_file = Path("ats_automation/testing/job_urls_1000.txt")
    if job_file.exists():
        with open(job_file) as f:
            urls = [line.strip() for line in f if line.strip()][:1000]
    else:
        print("❌ Job URLs file not found")
        return
    
    print(f"📋 Loaded {len(urls)} job URLs")
    
    # Create runner
    runner = MattProductionRunner(MATT_PROFILE)
    
    # ⚠️ AUTO_SUBMIT IS SET TO TRUE - WILL ACTUALLY SUBMIT
    AUTO_SUBMIT = True
    
    report = await runner.run_real_campaign(
        job_urls=urls,
        concurrent=20,  # 20 concurrent sessions
        auto_submit=AUTO_SUBMIT
    )
    
    return report


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelled by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
