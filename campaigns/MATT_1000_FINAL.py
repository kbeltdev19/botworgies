#!/usr/bin/env python3
"""
MATT EDWARDS - 1000 REAL APPLICATIONS (FINAL)
Auto-submit ENABLED | Local Browser Fallback | Verification
"""

import sys
import os
import asyncio
import json
import time
from pathlib import Path
from datetime import datetime

# Load environment FIRST
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

sys.path.insert(0, str(Path(__file__).parent.parent))

from browser.stealth_manager import StealthBrowserManager


# Matt's Profile
MATT_PROFILE = {
    "first_name": "Matt",
    "last_name": "Edwards",
    "email": "edwardsdmatt@gmail.com",
    "phone": "404-680-8472",
    "location": "Atlanta, GA",
    "resume_path": "Test Resumes/Matt_Edwards_Resume.pdf",
    "resume_text": """MATT EDWARDS
edwardsdmatt@gmail.com | linkedin.com/in/matt-edwards- | Secret Clearance | Remote

Customer Success Manager with 5+ years driving cloud adoption, retention, and expansion within AWS partner ecosystems. Proven track record managing $5.5M ACV portfolio with 98% gross retention and $1M+ expansion revenue.

CORE COMPETENCIES
Customer Success: Account Management, Retention, Expansion Revenue, Onboarding, QBRs, Health Scores
Cloud & Technical: AWS, Azure, GCP, Multi-Cloud, FedRAMP, GovCloud, Cost Optimization
Security: Secret Clearance (Active), CompTIA Security+, FedRAMP Foundation

PROFESSIONAL EXPERIENCE
Cloud Delivery Manager, 2bCloud (AWS Premier Partner) | Remote | 2026-Present
Customer Success Manager, 2bCloud (AWS Premier Partner) | Remote | 2022-2026

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
    "clearance": "Secret",
    "custom_answers": {
        "salary_expectations": "$110,000 - $140,000",
        "willing_to_relocate": "No - Remote only",
        "authorized_to_work": "Yes - US Citizen with Secret Clearance",
        "start_date": "2 weeks notice"
    }
}


class MattFinalCampaign:
    """Final production campaign with local browser fallback"""
    
    def __init__(self):
        self.results = []
        self.stats = {"success": 0, "failed": 0, "external": 0}
        self.browser_manager = None
        self.output_dir = Path("campaigns/output/matt_edwards_final")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    async def initialize(self):
        """Initialize browser with local fallback"""
        print("🌐 Initializing browser manager...")
        self.browser_manager = StealthBrowserManager(prefer_local=False)
        await self.browser_manager.initialize()
        
        # Test session creation
        try:
            test_session = await self.browser_manager.create_stealth_session(
                platform="test",
                use_proxy=True,
                force_local=False
            )
            print(f"✅ BrowserBase session: {test_session.session_id[:20]}...")
            await self.browser_manager.close_session(test_session.session_id)
        except Exception as e:
            print(f"⚠️  BrowserBase failed ({e}), will use local fallback")
        
        print("✅ Browser ready")
    
    async def apply_to_job(self, job: dict) -> dict:
        """Apply to a single job"""
        url = job.get("url", "")
        platform = job.get("platform", "unknown")
        
        session = None
        try:
            # Create session (BrowserBase or local fallback)
            session = await self.browser_manager.create_stealth_session(
                platform=platform,
                use_proxy=True,
                force_local=False  # Will auto-fallback if BrowserBase fails
            )
            
            page = session.page
            
            # Navigate to job
            await page.goto(url, timeout=30000)
            await asyncio.sleep(2)
            
            # Get page info
            current_url = page.url
            content = await page.content()
            content_lower = content.lower()
            
            # Check for apply buttons
            apply_selectors = [
                'button:has-text("Apply")',
                'a:has-text("Apply")',
                '[data-testid="apply-button"]',
                '.apply-button',
                'button:has-text("Apply now")'
            ]
            
            apply_found = False
            for selector in apply_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(timeout=5000)
                        apply_found = True
                        await asyncio.sleep(2)
                        break
                except:
                    continue
            
            if not apply_found:
                # Check if external redirect
                if "greenhouse" in current_url or "lever" in current_url:
                    return {"status": "external", "url": current_url}
                return {"status": "failed", "error": "No apply button found"}
            
            # Fill basic form fields
            try:
                # First name
                await page.fill('input[name="firstName"], input[name="first_name"], input[placeholder*="First"]', 
                               MATT_PROFILE["first_name"], timeout=3000)
            except:
                pass
            
            try:
                # Last name
                await page.fill('input[name="lastName"], input[name="last_name"], input[placeholder*="Last"]',
                               MATT_PROFILE["last_name"], timeout=3000)
            except:
                pass
            
            try:
                # Email
                await page.fill('input[name="email"], input[type="email"]',
                               MATT_PROFILE["email"], timeout=3000)
            except:
                pass
            
            try:
                # Phone
                await page.fill('input[name="phone"], input[type="tel"]',
                               MATT_PROFILE["phone"], timeout=3000)
            except:
                pass
            
            await asyncio.sleep(1)
            
            # Try to submit
            submit_selectors = [
                'button:has-text("Submit")',
                'button:has-text("Submit application")',
                'button[type="submit"]',
                'input[type="submit"]'
            ]
            
            submitted = False
            for selector in submit_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(timeout=5000)
                        submitted = True
                        await asyncio.sleep(3)
                        break
                except:
                    continue
            
            if submitted:
                # Validate submission
                final_content = await page.content()
                success_indicators = [
                    "thank you", "submitted", "success", "received",
                    "application complete", "confirmation"
                ]
                found_success = any(s in final_content.lower() for s in success_indicators)
                
                if found_success:
                    return {"status": "success"}
                else:
                    return {"status": "submitted", "note": "Form submitted, validation unclear"}
            else:
                return {"status": "filled", "note": "Form filled but submit not clicked"}
                
        except Exception as e:
            return {"status": "error", "error": str(e)[:100]}
        finally:
            if session:
                try:
                    await self.browser_manager.close_session(session.session_id)
                except:
                    pass
    
    async def run_campaign(self, jobs: list, concurrent: int = 5):
        """Run the full campaign"""
        await self.initialize()
        
        total = len(jobs)
        semaphore = asyncio.Semaphore(concurrent)
        start_time = datetime.now()
        
        print("\n" + "="*80)
        print("🚀 MATT EDWARDS - 1000 REAL APPLICATIONS (FINAL)")
        print("="*80)
        print(f"Candidate: {MATT_PROFILE['first_name']} {MATT_PROFILE['last_name']}")
        print(f"Email: {MATT_PROFILE['email']}")
        print(f"Clearance: {MATT_PROFILE['clearance']}")
        print(f"Total Jobs: {total}")
        print(f"Concurrent: {concurrent}")
        print(f"Started: {start_time.strftime('%H:%M:%S')}")
        print("="*80 + "\n")
        
        async def process_job(job, index):
            async with semaphore:
                # Rate limiting
                await asyncio.sleep(3)  # 3 second delay between jobs
                
                company = job.get("company", "Unknown")[:25]
                title = job.get("title", "Unknown")[:35]
                
                print(f"[{index+1:4d}/{total}] {title:35} @ {company:25} ... ", end="", flush=True)
                
                result = await self.apply_to_job(job)
                
                self.results.append({
                    "job_id": job.get("id"),
                    "company": job.get("company"),
                    "title": job.get("title"),
                    "url": job.get("url"),
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                })
                
                if result["status"] == "success":
                    self.stats["success"] += 1
                    print("✅ SUCCESS")
                elif result["status"] == "external":
                    self.stats["external"] += 1
                    print("↪️  EXTERNAL")
                else:
                    self.stats["failed"] += 1
                    error = result.get("error", "Unknown")[:30]
                    print(f"❌ {error}")
                
                # Progress every 50
                if (index + 1) % 50 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    success_rate = self.stats["success"] / (index + 1) * 100
                    print(f"\n{'='*80}")
                    print(f"📊 Progress: {index+1}/{total} | Success: {self.stats['success']} | "
                          f"Rate: {success_rate:.1f}% | Time: {elapsed:.1f}min")
                    print(f"{'='*80}\n")
                    self._save_progress()
        
        # Process all jobs
        tasks = [process_job(job, i) for i, job in enumerate(jobs)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60
        
        # Cleanup
        await self.browser_manager.close_all()
        
        # Final report
        report = {
            "campaign_id": f"matt_final_{start_time.strftime('%Y%m%d_%H%M')}",
            "candidate": MATT_PROFILE,
            "total_jobs": total,
            "successful": self.stats["success"],
            "external": self.stats["external"],
            "failed": self.stats["failed"],
            "success_rate": (self.stats["success"] / total * 100) if total > 0 else 0,
            "duration_minutes": duration,
            "results": self.results,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        # Save final report
        report_file = self.output_dir / f"FINAL_REPORT_{start_time.strftime('%H%M')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Print summary
        print("\n" + "="*80)
        print("✅ CAMPAIGN COMPLETE")
        print("="*80)
        print(f"Total Jobs: {total}")
        print(f"✅ Successful: {self.stats['success']}")
        print(f"↪️  External: {self.stats['external']}")
        print(f"❌ Failed: {self.stats['failed']}")
        print(f"Success Rate: {report['success_rate']:.1f}%")
        print(f"Duration: {duration:.1f} minutes")
        print(f"Report: {report_file}")
        print("="*80)
        
        return report
    
    def _save_progress(self):
        """Save intermediate progress"""
        progress_file = self.output_dir / f"progress_{datetime.now().strftime('%H%M%S')}.json"
        with open(progress_file, 'w') as f:
            json.dump({
                "stats": self.stats,
                "results": self.results[-100:]  # Last 100
            }, f, indent=2)


async def main():
    # Load jobs from the 1000 jobs file
    jobs_file = Path("campaigns/matt_edwards_1000_jobs.json")
    if jobs_file.exists():
        with open(jobs_file) as f:
            data = json.load(f)
            jobs = data.get("jobs", [])
    else:
        print("❌ Jobs file not found")
        return
    
    print(f"📋 Loaded {len(jobs)} jobs")
    
    # Show warning
    print("\n" + "⚠️ "*40)
    print("⚠️  THIS WILL SUBMIT REAL JOB APPLICATIONS!")
    print("⚠️  Auto-submit is ENABLED")
    print("⚠️  Matt WILL receive confirmation emails")
    print("⚠️ "*40)
    print("\nStarting in 10 seconds... (Ctrl+C to cancel)")
    
    for i in range(10, 0, -1):
        print(f"   {i}...", end="\r")
        await asyncio.sleep(1)
    print("   Go!     ")
    
    # Run campaign
    campaign = MattFinalCampaign()
    report = await campaign.run_campaign(jobs[:1000], concurrent=5)
    
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
