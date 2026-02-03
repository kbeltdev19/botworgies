#!/usr/bin/env python3
"""
KENT LE - REAL PRODUCTION APPLICATIONS

⚠️  WARNING: This will ACTUALLY submit job applications!
     - Auto-submit is ENABLED
     - BrowserBase is CONNECTED  
     - Real forms will be filled
     - You WILL receive confirmation emails

Requirements:
1. BrowserBase API connected
2. CAPTCHA solving service (optional but recommended)
3. Valid LinkedIn session cookie
4. Resume uploaded and parsed
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
                os.environ.setdefault(key, value)

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


# Kent Le Profile
KENT_PROFILE = UserProfile(
    first_name="Kent",
    last_name="Le",
    email="kle4311@gmail.com",
    phone="404-934-0630",
    resume_path="Test Resumes/Kent_Le_Resume.pdf",
    resume_text="""KENT LE
Auburn, Alabama | 404-934-0630 | kle4311@gmail.com

PROFESSIONAL SUMMARY
Results-driven Customer Success professional with 5+ years of experience.

WORK EXPERIENCE
Senior Customer Success Manager | TechCorp Inc. | 2021-Present
Account Manager | CloudSolutions LLC | 2019-2021

EDUCATION
Bachelor of Business Administration | Auburn University | 2018
""",
    linkedin_url="https://linkedin.com/in/kentle",
    salary_expectation="$75,000 - $95,000",
    years_experience=5,
    skills=["Customer Success", "Account Management", "Salesforce", "HubSpot"],
    custom_answers={
        "salary_expectations": "$75,000 - $95,000",
        "willing_to_relocate": "No - prefer remote or Auburn, AL area",
        "authorized_to_work": "Yes - US Citizen"
    }
)


class RealProductionRunner:
    """
    PRODUCTION RUNNER - ACTUALLY SUBMITS APPLICATIONS
    
    WARNING: This will submit real job applications!
    """
    
    def __init__(self, profile: UserProfile):
        self.profile = profile
        self.results = []
        self.browser = None
        
    async def run_real_campaign(
        self,
        job_urls: List[str],
        concurrent: int = 10,  # Lower for real submissions
        auto_submit: bool = True  # ⚠️ THIS ACTUALLY SUBMITS!
    ) -> Dict:
        """
        Run REAL production campaign
        
        ⚠️  WARNING: auto_submit=True will actually submit applications!
        """
        
        print("\n" + "="*70)
        print("🚀 KENT LE - REAL PRODUCTION CAMPAIGN")
        print("="*70)
        print(f"⚠️  MODE: {'REAL APPLICATIONS' if auto_submit else 'SAFE MODE (test)'}")
        print(f"📧 Email: {self.profile.email}")
        print(f"📍 Location: Auburn, AL / Remote")
        print(f"📋 Jobs: {len(job_urls)}")
        print(f"⚡ Concurrent: {concurrent}")
        print(f"⏰ Started: {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)
        
        if auto_submit:
            print("\n⚠️  ⚠️  ⚠️  WARNING  ⚠️  ⚠️  ⚠️")
            print("This will ACTUALLY submit job applications!")
            print("You WILL receive confirmation emails from job sites.")
            print("Press Ctrl+C within 5 seconds to cancel...")
            print("⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️\n")
            await asyncio.sleep(5)
        
        if not ATS_AVAILABLE:
            print("❌ ATS Automation module not available")
            return {"error": "ATS not available"}
        
        # Initialize BrowserBase
        print("Connecting to BrowserBase...")
        self.browser = BrowserBaseManager()
        await self.browser.initialize()
        print("✅ BrowserBase connected")
        
        # Process with lower concurrency for safety
        semaphore = asyncio.Semaphore(concurrent)
        completed = 0
        successful = 0
        
        async def process_job(url: str, index: int):
            nonlocal completed, successful
            
            async with semaphore:
                print(f"[{index+1:4d}/{len(job_urls)}] Processing: {url[:60]}...")
                
                try:
                    # Create router with browser
                    router = ATSRouter(self.profile, browser=self.browser)
                    
                    # ⚠️ THIS ACTUALLY SUBMITS IF auto_submit=True
                    result = await router.apply(url, auto_submit=auto_submit)
                    
                    self.results.append(result)
                    completed += 1
                    
                    if result.success:
                        successful += 1
                        status = "✅ SUBMITTED" if auto_submit else "✅ TEST PASSED"
                    else:
                        status = f"❌ FAILED: {result.error_message[:40]}"
                    
                    print(f"   {status}")
                    
                    # Progress every 10
                    if completed % 10 == 0:
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
        
        # Cleanup
        if self.browser:
            await self.browser.close()
        
        # Report
        duration_mins = (end_time - start_time).total_seconds() / 60
        
        report = {
            "campaign_id": f"kent_real_{start_time.strftime('%Y%m%d_%H%M')}",
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
        report_path = f"campaigns/output/kent_real_{start_time.strftime('%Y%m%d_%H%M')}_report.json"
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
    runner = RealProductionRunner(KENT_PROFILE)
    
    # ⚠️ SET auto_submit=True FOR REAL APPLICATIONS
    # ⚠️ SET auto_submit=False FOR TESTING
    
    AUTO_SUBMIT = False  # <-- CHANGE TO True FOR REAL APPLICATIONS
    
    report = await runner.run_real_campaign(
        job_urls=urls,
        concurrent=10,  # Lower for real applications
        auto_submit=AUTO_SUBMIT
    )
    
    return report


if __name__ == "__main__":
    asyncio.run(main())
