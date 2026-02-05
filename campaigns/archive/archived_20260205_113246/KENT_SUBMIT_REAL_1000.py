#!/usr/bin/env python3
"""
KENT LE - SUBMIT 1000 REAL JOB APPLICATIONS

⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️
⚠️                                                                    ⚠️
⚠️   THIS SCRIPT ACTUALLY SUBMITS REAL JOB APPLICATIONS!              ⚠️
⚠️                                                                    ⚠️
⚠️   - You WILL receive confirmation emails                           ⚠️
⚠️   - Employers WILL see your application                            ⚠️
⚠️   - This CANNOT be undone                                          ⚠️
⚠️                                                                    ⚠️
⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️
"""

import sys
import os
import signal
import asyncio
import json
from pathlib import Path
from datetime import datetime
import time

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
                os.environ.setdefault(key, value)


class ZombieProcessKiller:
    """Handles zombie/stuck processes"""
    
    @staticmethod
    def kill_all():
        """Kill all zombie Python and browser processes"""
        try:
            import psutil
            killed = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'cpu_times']):
                try:
                    pinfo = proc.info
                    cmdline = ' '.join(pinfo.get('cmdline') or [])
                    
                    # Kill zombie Python processes related to campaigns
                    if pinfo.get('name') in ['python3', 'Python', 'python']:
                        if any(x in cmdline for x in ['campaign', 'production', 'kent', 'matt', 'kevin', 'apply']):
                            try:
                                # Check if zombie or stuck
                                if pinfo.get('status') == psutil.STATUS_ZOMBIE:
                                    os.kill(pinfo['pid'], signal.SIGKILL)
                                    killed += 1
                                    print(f"   💀 Killed zombie Python PID {pinfo['pid']}")
                                elif pinfo.get('cpu_times') and pinfo['cpu_times'].user > 300:
                                    os.kill(pinfo['pid'], signal.SIGKILL)
                                    killed += 1
                                    print(f"   ⏱️  Killed stuck Python PID {pinfo['pid']}")
                            except:
                                pass
                    
                    # Kill stuck Playwright/browser processes
                    if 'playwright' in cmdline or 'browserbase' in cmdline or 'chromium' in cmdline:
                        try:
                            if pinfo.get('cpu_times') and pinfo['cpu_times'].user > 600:
                                os.kill(pinfo['pid'], signal.SIGKILL)
                                killed += 1
                                print(f"   🌐 Killed stuck browser PID {pinfo['pid']}")
                        except:
                            pass
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if killed > 0:
                print(f"✅ Cleaned up {killed} zombie/stuck processes")
            return killed
        except ImportError:
            print("⚠️  psutil not available, using basic cleanup")
            os.system("pkill -9 -f 'python.*campaign\|playwright' 2>/dev/null")
            return 0


# Kill zombies before starting
print("🧹 Pre-flight cleanup...")
ZombieProcessKiller.kill_all()

# Kent's Profile
KENT_PROFILE = {
    "first_name": "Kent",
    "last_name": "Le",
    "email": "kle4311@gmail.com",
    "phone": "404-934-0630",
    "location": "Auburn, AL",
    "linkedin": "",
    "resume_path": "Test Resumes/Kent_Le_Resume.pdf",
    "min_salary": 75000,
    "target_roles": [
        "Customer Success Manager",
        "Account Manager",
        "Client Success Manager",
        "Business Development Representative",
        "Account Executive",
        "Sales Development Representative"
    ],
    "clearance": None,
    "custom_answers": {
        "salary_expectations": "$75,000 - $95,000",
        "willing_to_relocate": "No - prefer remote or Auburn, AL area",
        "authorized_to_work": "Yes - US Citizen",
        "start_date": "2 weeks notice"
    }
}


class RealApplicationSubmitter:
    """Submits REAL job applications"""
    
    def __init__(self, profile):
        self.profile = profile
        self.submitted = 0
        self.failed = 0
        self.duplicates_skipped = 0
        self.zombie_killer = ZombieProcessKiller()
        
    async def submit_application(self, job_url: str, job_title: str, company: str) -> bool:
        """
        Submit a REAL job application
        
        ⚠️ This actually fills out and submits the form!
        """
        try:
            from ats_automation import ATSRouter
            from campaigns.duplicate_checker import DuplicateChecker
            
            # Check for duplicates
            checker = DuplicateChecker()
            if checker.is_already_applied("kle4311@gmail.com", job_url):
                self.duplicates_skipped += 1
                return False
            
            # Initialize router with browser
            router = ATSRouter(self.profile)
            
            # ⚠️ THIS ACTUALLY SUBMITS THE APPLICATION
            result = await router.apply(job_url, auto_submit=True)
            
            if result.success:
                self.submitted += 1
                checker.record_application("kle4311@gmail.com", job_url, "kent_real_1000")
                return True
            else:
                self.failed += 1
                return False
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:50]}")
            self.failed += 1
            return False
        finally:
            if 'router' in locals():
                await router.cleanup()
    
    async def run_real_campaign(self, jobs: list, concurrent: int = 10):
        """
        Run REAL campaign with zombie process monitoring
        """
        import asyncio
        
        total = len(jobs)
        semaphore = asyncio.Semaphore(concurrent)
        start_time = datetime.now()
        
        print("\n" + "="*70)
        print("🚀 SUBMITTING REAL APPLICATIONS")
        print("="*70)
        print(f"Total jobs: {total}")
        print(f"Concurrent: {concurrent}")
        print(f"Started: {start_time.strftime('%H:%M:%S')}")
        print("="*70 + "\n")
        
        async def process_job(job, index):
            async with semaphore:
                print(f"[{index+1:4d}/{total}] {job['title'][:30]} at {job['company'][:20]}...")
                
                success = await self.submit_application(
                    job['url'], 
                    job['title'], 
                    job['company']
                )
                
                status = "✅ SUBMITTED" if success else "❌ FAILED"
                print(f"   {status}")
                
                # Progress update every 50
                if (index + 1) % 50 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    rate = (index + 1) / elapsed if elapsed > 0 else 0
                    print(f"\n📊 Progress: {index+1}/{total} | Rate: {rate:.1f}/min | {datetime.now().strftime('%H:%M:%S')}\n")
                
                # Kill zombies periodically
                if (index + 1) % 100 == 0:
                    self.zombie_killer.kill_all()
                
                # Brief delay to be respectful
                await asyncio.sleep(2)
                
                return success
        
        # Process all jobs
        tasks = [process_job(job, i) for i, job in enumerate(jobs)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Final cleanup
        self.zombie_killer.kill_all()
        
        # Report
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60
        
        report = {
            "campaign_id": f"kent_real_1000_{start_time.strftime('%Y%m%d_%H%M')}",
            "total": total,
            "submitted": self.submitted,
            "failed": self.failed,
            "duplicates_skipped": self.duplicates_skipped,
            "success_rate": (self.submitted / total * 100) if total > 0 else 0,
            "duration_minutes": duration,
            "apps_per_minute": self.submitted / duration if duration > 0 else 0,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        # Save report
        report_file = Path(__file__).parent / f"kent_real_1000_report_{start_time.strftime('%Y%m%d_%H%M')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print("\n" + "="*70)
        print("✅ CAMPAIGN COMPLETE")
        print("="*70)
        print(f"Total: {total}")
        print(f"✅ Submitted: {self.submitted}")
        print(f"❌ Failed: {self.failed}")
        print(f"⏭️  Duplicates: {self.duplicates_skipped}")
        print(f"📈 Success Rate: {report['success_rate']:.1f}%")
        print(f"⏱️  Duration: {duration:.1f} minutes")
        print(f"🚀 Apps/Min: {report['apps_per_minute']:.1f}")
        print(f"💾 Report: {report_file}")
        print("="*70)
        print("\n📧 You should receive confirmation emails soon!")
        print("   Check your inbox (and spam folder) at kle4311@gmail.com")
        
        return report


async def main():
    """Main entry point"""
    
    # Show warning
    print("\n" + "⚠️ " * 35)
    print("\n   THIS WILL SUBMIT REAL JOB APPLICATIONS!\n")
    print("   You WILL receive confirmation emails.")
    print("   This CANNOT be undone.\n")
    print("⚠️ " * 35 + "\n")
    
    # Load jobs
    jobs_file = Path(__file__).parent / "kent_le_real_jobs_1000.json"
    
    if jobs_file.exists():
        with open(jobs_file) as f:
            data = json.load(f)
            jobs = data.get('jobs', [])
    else:
        print("❌ No jobs file found. Run KENT_REAL_1000_PRODUCTION.py first")
        return
    
    print(f"📋 Loaded {len(jobs)} jobs")
    
    # Confirm
    print("\n⚠️  Press Ctrl+C within 10 seconds to cancel...")
    try:
        for i in range(10, 0, -1):
            print(f"Starting in {i}...", end='\r')
            time.sleep(1)
        print("\n🚀 Starting REAL submissions!          ")
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled")
        return
    
    # Run campaign
    submitter = RealApplicationSubmitter(KENT_PROFILE)
    report = await submitter.run_real_campaign(jobs[:1000], concurrent=10)
    
    return report


if __name__ == "__main__":
    asyncio.run(main())
