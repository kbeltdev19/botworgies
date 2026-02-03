#!/usr/bin/env python3
"""
Kent Le - Automated Application Runner
Apply to jobs from a JSON list using browser automation.

Usage:
    python kent_apply_to_jobs.py jobs_file.json
"""

import sys
import asyncio
import json
import random
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters import get_adapter, UserProfile, Resume, ApplicationStatus
from browser.stealth_manager import StealthBrowserManager


# Kent's Profile
KENT_PROFILE = UserProfile(
    first_name="Kent",
    last_name="Le",
    email="kle4311@gmail.com",
    phone="(404) 934-0630",
    location="Auburn, AL",
    linkedin_url="https://linkedin.com/in/kent-le",
    work_authorization="Yes",
    sponsorship_required="No",
    years_experience=3,
    custom_answers={
        "salary_expectation": "75000",
        "relocation": "Open to remote and hybrid positions nationwide",
        "start_date": "2 weeks notice",
        "languages": "English, Vietnamese (fluent)",
    }
)

RESUME_PATH = "/Users/tech4/Downloads/botworkieslocsl/botworgies/Test Resumes/Kent_Le_Resume.pdf"


class ApplicationRunner:
    """Run automated applications to a list of jobs."""
    
    def __init__(self, jobs_file: str):
        self.jobs_file = Path(jobs_file)
        self.output_dir = self.jobs_file.parent
        
        # Load jobs
        with open(jobs_file) as f:
            self.jobs = json.load(f)
        
        self.browser_manager = StealthBrowserManager()
        
        # Stats
        self.stats = {
            "total": len(self.jobs),
            "attempted": 0,
            "successful": 0,
            "failed": 0,
            "external": 0,
            "by_platform": {},
            "start_time": datetime.now().isoformat(),
        }
        
        # Results
        self.results = []
        
    async def run(self):
        """Run applications to all jobs."""
        print("\n" + "="*80)
        print("📝 AUTOMATED APPLICATION RUNNER")
        print("="*80)
        print(f"\nCandidate: Kent Le")
        print(f"Target: {self.stats['total']} jobs")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Load resume
        resume = self._load_resume()
        
        # Apply to each job
        for i, job in enumerate(self.jobs, 1):
            print(f"\n{'='*80}")
            print(f"📨 Job {i}/{self.stats['total']}: {job['title']}")
            print(f"{'='*80}")
            print(f"Company: {job['company']}")
            print(f"Location: {job['location']}")
            print(f"URL: {job['url']}")
            
            result = await self._apply_to_job(job, resume)
            
            # Record result
            self.results.append({
                "job_id": job['id'],
                "title": job['title'],
                "company": job['company'],
                "url": job['url'],
                "status": result['status'],
                "message": result['message'],
                "timestamp": datetime.now().isoformat(),
            })
            
            # Update stats
            self.stats['attempted'] += 1
            if result['status'] == 'submitted':
                self.stats['successful'] += 1
                print(f"\n✅ SUCCESS: {result['message']}")
            elif result['status'] == 'external':
                self.stats['external'] += 1
                print(f"\n🔗 EXTERNAL: {result['message']}")
            else:
                self.stats['failed'] += 1
                print(f"\n❌ FAILED: {result['message']}")
            
            # Progress update
            if i % 10 == 0:
                self._print_progress()
            
            # Delay between applications
            if i < len(self.jobs):
                delay = random.uniform(3, 6)
                print(f"\n⏳ Waiting {delay:.1f}s...")
                await asyncio.sleep(delay)
        
        # Cleanup
        await self.browser_manager.close_all()
        
        # Save results
        self._save_results()
        self._print_final_report()
    
    def _load_resume(self) -> Resume:
        """Load resume."""
        return Resume(
            file_path=RESUME_PATH,
            raw_text="",
            parsed_data={
                "name": "Kent Le",
                "email": "kle4311@gmail.com",
                "phone": "(404) 934-0630",
                "location": "Auburn, AL",
            }
        )
    
    async def _apply_to_job(self, job: dict, resume: Resume) -> dict:
        """Apply to a single job."""
        try:
            # Get adapter
            adapter = get_adapter(job['url'], self.browser_manager)
            platform = adapter.platform.value
            
            # Update platform stats
            if platform not in self.stats['by_platform']:
                self.stats['by_platform'][platform] = {'attempted': 0, 'successful': 0}
            self.stats['by_platform'][platform]['attempted'] += 1
            
            # Create JobPosting object
            from adapters import JobPosting, PlatformType
            job_posting = JobPosting(
                id=str(job['id']),
                platform=PlatformType(platform) if hasattr(PlatformType, platform.upper()) else PlatformType.EXTERNAL,
                title=job['title'],
                company=job['company'],
                location=job['location'],
                url=job['url'],
                easy_apply=job.get('easy_apply', False),
                remote=job.get('remote', False),
            )
            
            # Apply
            result = await adapter.apply_to_job(
                job=job_posting,
                resume=resume,
                profile=KENT_PROFILE,
                cover_letter=None,
                auto_submit=False,  # Safe mode - manual review
            )
            
            # Update platform success
            if result.status == ApplicationStatus.SUBMITTED:
                self.stats['by_platform'][platform]['successful'] += 1
                return {'status': 'submitted', 'message': result.message}
            elif result.status == ApplicationStatus.EXTERNAL_APPLICATION:
                return {'status': 'external', 'message': f"Apply at: {result.external_url}"}
            else:
                return {'status': 'failed', 'message': result.message or result.error or 'Unknown error'}
                
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _print_progress(self):
        """Print progress update."""
        attempted = self.stats['attempted']
        successful = self.stats['successful']
        rate = (successful / max(attempted, 1)) * 100
        
        print(f"\n{'='*80}")
        print(f"📊 PROGRESS: {attempted}/{self.stats['total']} | Success: {successful} ({rate:.1f}%)")
        print(f"{'='*80}")
    
    def _save_results(self):
        """Save application results."""
        results_file = self.output_dir / "application_results.json"
        
        data = {
            "stats": self.stats,
            "results": self.results,
            "end_time": datetime.now().isoformat(),
        }
        
        with open(results_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n💾 Results saved to: {results_file}")
    
    def _print_final_report(self):
        """Print final report."""
        print("\n" + "="*80)
        print("📊 FINAL REPORT")
        print("="*80)
        print(f"\nTotal Attempted: {self.stats['attempted']}")
        print(f"Successful: {self.stats['successful']} ✅")
        print(f"External (Manual): {self.stats['external']} 🔗")
        print(f"Failed: {self.stats['failed']} ❌")
        
        if self.stats['attempted'] > 0:
            rate = (self.stats['successful'] / self.stats['attempted']) * 100
            print(f"\nSuccess Rate: {rate:.1f}%")
        
        print("\nBy Platform:")
        for platform, stats in self.stats['by_platform'].items():
            print(f"  {platform}: {stats['successful']}/{stats['attempted']}")
        
        print(f"\nOutput: {self.output_dir}")
        print("="*80)


async def main():
    """Main entry."""
    if len(sys.argv) < 2:
        print("Usage: python kent_apply_to_jobs.py <jobs_file.json>")
        print("\nExample:")
        print("  python kent_apply_to_jobs.py output/kent_batch_100_20260203_1615/jobs_to_apply.json")
        sys.exit(1)
    
    jobs_file = sys.argv[1]
    runner = ApplicationRunner(jobs_file)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
