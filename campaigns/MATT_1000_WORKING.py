#!/usr/bin/env python3
"""
MATT EDWARDS - 1000 REAL JOB APPLICATIONS (WORKING VERSION)
Auto-submit enabled with external handling
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Matt's Profile
MATT_PROFILE = {
    "first_name": "Matt",
    "last_name": "Edwards",
    "email": "edwardsdmatt@gmail.com",
    "phone": "404-680-8472",
    "location": "Atlanta, GA",
    "linkedin": "https://linkedin.com/in/matt-edwards-",
    "resume_path": "Test Resumes/Matt_Edwards_Resume.pdf",
    "min_salary": 110000,
    "target_roles": [
        "Customer Success Manager",
        "Cloud Delivery Manager", 
        "Technical Account Manager",
        "Solutions Architect",
        "Enterprise Account Manager"
    ],
    "clearance": "Secret",
    "custom_answers": {
        "salary_expectations": "$110,000 - $140,000",
        "willing_to_relocate": "No - Remote only",
        "authorized_to_work": "Yes - US Citizen with Secret Clearance",
        "start_date": "2 weeks notice",
        "clearance": "Secret Security Clearance (Active)"
    }
}


class MattApplicationSubmitter:
    """Submits REAL job applications for Matt"""
    
    def __init__(self, profile):
        self.profile = profile
        self.submitted = 0
        self.failed = 0
        self.results = []
        
    async def submit_application(self, job_url: str) -> dict:
        """Submit a REAL job application"""
        try:
            from ats_automation import ATSRouter
            
            # Initialize router
            router = ATSRouter(self.profile)
            
            # Apply to job (auto-submit happens internally)
            result = await router.apply(job_url)
            
            self.results.append({
                "url": job_url,
                "success": result.success,
                "platform": result.platform.value if result.platform else None,
                "error": result.error_message
            })
            
            if result.success:
                self.submitted += 1
                return {"success": True}
            else:
                self.failed += 1
                return {"success": False, "error": result.error_message}
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:50]}")
            self.failed += 1
            return {"success": False, "error": str(e)}
        finally:
            if 'router' in locals():
                await router.cleanup()
    
    async def run_campaign(self, job_urls: list, concurrent: int = 5):  # Reduced for rate limits
        """Run the campaign"""
        total = len(job_urls)
        semaphore = asyncio.Semaphore(concurrent)
        self.last_request_time = 0  # For rate limiting
        start_time = datetime.now()
        
        print("\n" + "="*70)
        print("🚀 MATT EDWARDS - 1000 REAL JOB APPLICATIONS")
        print("="*70)
        print(f"Candidate: {self.profile['first_name']} {self.profile['last_name']}")
        print(f"Email: {self.profile['email']}")
        print(f"Clearance: {self.profile['clearance']}")
        print(f"Total jobs: {total}")
        print(f"Concurrent: {concurrent}")
        print(f"Started: {start_time.strftime('%H:%M:%S')}")
        print("="*70 + "\n")
        
        async def process_job(url, index):
            async with semaphore:
                # Rate limiting: max 1 request per 2 seconds per session
                import time
                now = time.time()
                time_since_last = now - self.last_request_time
                if time_since_last < 2:
                    await asyncio.sleep(2 - time_since_last)
                
                print(f"[{index+1:4d}/{total}] {url[:60]}...")
                result = await self.submit_application(url)
                self.last_request_time = time.time()
                
                status = "✅ SUBMITTED" if result["success"] else "❌ FAILED"
                print(f"   {status}")
                
                # Progress every 50
                if (index + 1) % 50 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    print(f"\n📊 Progress: {index+1}/{total} | "
                          f"Success: {self.submitted} | {datetime.now().strftime('%H:%M:%S')}\n")
        
        # Process all jobs
        tasks = [process_job(url, i) for i, url in enumerate(job_urls)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60
        
        # Report
        report = {
            "campaign_id": f"matt_working_{start_time.strftime('%Y%m%d_%H%M')}",
            "total": total,
            "submitted": self.submitted,
            "failed": self.failed,
            "success_rate": (self.submitted / total * 100) if total > 0 else 0,
            "duration_minutes": duration,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "results": self.results
        }
        
        # Save report
        output_dir = Path("campaigns/output/matt_edwards_real")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_file = output_dir / f"working_campaign_{start_time.strftime('%H%M')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print("\n" + "="*70)
        print("✅ CAMPAIGN COMPLETE")
        print("="*70)
        print(f"Total: {total}")
        print(f"Submitted: {self.submitted}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {report['success_rate']:.1f}%")
        print(f"Duration: {duration:.1f} minutes")
        print(f"Report: {report_file}")
        print("="*70)
        
        return report


async def main():
    print("🧹 Cleaning up existing BrowserBase sessions...")
    # Wait for existing sessions to expire
    await asyncio.sleep(10)
    
    # Load job URLs
    job_file = Path("ats_automation/testing/job_urls_1000.txt")
    if job_file.exists():
        with open(job_file) as f:
            urls = [line.strip() for line in f if line.strip()][:1000]
    else:
        print("❌ Job URLs file not found")
        return
    
    print(f"📋 Loaded {len(urls)} job URLs")
    
    # Create submitter
    submitter = MattApplicationSubmitter(MATT_PROFILE)
    
    # Run campaign
    report = await submitter.run_campaign(urls, concurrent=20)
    
    return report


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelled")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
