#!/usr/bin/env python3
"""
Kent Le - 10 Real Applications Campaign
Location: Auburn, AL (open to remote/hybrid/in-person)
Salary: $75k+
Target: Client Success, Account Management, Sales roles
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters import (
    JobSpyAdapter, JobSpySearchBuilder,
    SearchConfig, UserProfile, Resume,
    ApplicationStatus
)
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
        "salary_expectation": "$75,000 - $95,000",
        "relocation": "Open to remote and hybrid positions nationwide",
        "start_date": "2 weeks notice",
        "languages": "English, Vietnamese (fluent)",
    }
)

# Kent's Resume Path
RESUME_PATH = "/Users/tech4/Downloads/botworkieslocsl/botworgies/Test Resumes/Kent_Le_Resume.pdf"


class Kent10ApplicationCampaign:
    """Real campaign to apply to 10 jobs for Kent Le."""
    
    def __init__(self):
        self.browser_manager = StealthBrowserManager()
        self.output_dir = Path(__file__).parent / "output" / "kent_le_10_real"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {
            "campaign_id": f"kent_10_real_{datetime.now().strftime('%Y%m%d_%H%M')}",
            "target": 10,
            "completed": 0,
            "successful": 0,
            "failed": 0,
            "applications": [],
            "start_time": datetime.now().isoformat(),
        }
        
    async def find_jobs(self) -> list:
        """Find suitable jobs for Kent."""
        print("\n" + "="*70)
        print("🔍 PHASE 1: FINDING JOBS FOR KENT LE")
        print("="*70)
        print(f"\n📍 Location: Auburn, AL (Remote/Hybrid/In-person)")
        print(f"💰 Salary Target: $75k+")
        print(f"🎯 Roles: Customer Success, Account Management, Sales")
        print()
        
        # Use JobSpy to find jobs
        adapter = JobSpyAdapter(sites=["indeed", "linkedin", "zip_recruiter"])
        
        # Search for each role type
        all_jobs = []
        search_terms = [
            "Customer Success Manager",
            "Account Manager", 
            "Client Success Manager",
            "Sales Representative",
            "Business Development Representative"
        ]
        
        for term in search_terms:
            print(f"Searching: {term}...")
            criteria = SearchConfig(
                roles=[term],
                locations=["Auburn, AL", "Atlanta, GA", "Birmingham, AL", "Remote"],
                posted_within_days=7,
                easy_apply_only=False,  # Include external applications too
                salary_min=75000,
            )
            
            try:
                jobs = await adapter.search_jobs(criteria)
                print(f"  Found {len(jobs)} jobs")
                
                # Filter for salary if provided
                for job in jobs:
                    # Check if salary meets requirement
                    if self._meets_salary_requirement(job):
                        all_jobs.append(job)
                        
            except Exception as e:
                print(f"  Error: {e}")
                continue
        
        # Deduplicate by URL
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                unique_jobs.append(job)
        
        print(f"\n✅ Total unique jobs found: {len(unique_jobs)}")
        return unique_jobs[:20]  # Take top 20 for selection
    
    def _meets_salary_requirement(self, job) -> bool:
        """Check if job meets $75k salary requirement."""
        if not job.salary_range:
            return True  # Include jobs without salary info
        
        salary_str = job.salary_range.lower()
        
        # Extract numbers from salary string
        import re
        numbers = re.findall(r'\d+', salary_str.replace(',', ''))
        
        if not numbers:
            return True
        
        # Check if any number is >= 75000
        for num in numbers:
            if int(num) >= 75000:
                return True
            # Check for hourly rates (assume 2080 hours/year)
            if int(num) >= 36:  # $36/hr ≈ $75k/year
                return True
        
        return False
    
    async def apply_to_jobs(self, jobs: list):
        """Apply to top 10 jobs."""
        print("\n" + "="*70)
        print("📝 PHASE 2: APPLYING TO TOP 10 JOBS")
        print("="*70)
        print()
        
        # Load resume
        resume = await self._load_resume()
        if not resume:
            print("❌ Failed to load resume")
            return
        
        # Select top 10 jobs prioritizing:
        # 1. Easy Apply
        # 2. Auburn/Atlanta/Remote locations
        # 3. Recent postings
        prioritized_jobs = self._prioritize_jobs(jobs)
        top_10 = prioritized_jobs[:10]
        
        print(f"Selected {len(top_10)} jobs to apply:\n")
        for i, job in enumerate(top_10, 1):
            print(f"{i}. {job.title}")
            print(f"   Company: {job.company}")
            print(f"   Location: {job.location}")
            print(f"   Easy Apply: {job.easy_apply}")
            print(f"   URL: {job.url[:60]}...")
            print()
        
        # Apply to each job
        for i, job in enumerate(top_10, 1):
            print(f"\n{'='*70}")
            print(f"📨 Application {i}/10: {job.title} @ {job.company}")
            print(f"{'='*70}")
            
            try:
                result = await self._apply_to_job(job, resume)
                
                # Record result
                app_record = {
                    "id": i,
                    "job_title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "url": job.url,
                    "easy_apply": job.easy_apply,
                    "status": result.status.value,
                    "message": result.message,
                    "submitted_at": datetime.now().isoformat(),
                    "confirmation_id": result.confirmation_id,
                    "screenshot": result.screenshot_path,
                }
                
                self.results["applications"].append(app_record)
                
                if result.status == ApplicationStatus.SUBMITTED:
                    self.results["successful"] += 1
                    print(f"✅ SUCCESS: {result.message}")
                    if result.confirmation_id:
                        print(f"   Confirmation ID: {result.confirmation_id}")
                elif result.status == ApplicationStatus.PENDING_REVIEW:
                    print(f"⏸️  PENDING REVIEW: {result.message}")
                    print(f"   Screenshot: {result.screenshot_path}")
                elif result.status == ApplicationStatus.EXTERNAL_APPLICATION:
                    print(f"🔗 EXTERNAL: {result.message}")
                    print(f"   Apply at: {result.external_url}")
                else:
                    self.results["failed"] += 1
                    print(f"❌ FAILED: {result.message}")
                    if result.error:
                        print(f"   Error: {result.error}")
                
                self.results["completed"] += 1
                
                # Delay between applications
                if i < len(top_10):
                    print(f"\n⏳ Waiting 5 seconds before next application...")
                    await asyncio.sleep(5)
                    
            except Exception as e:
                print(f"❌ EXCEPTION: {e}")
                self.results["failed"] += 1
                self.results["applications"].append({
                    "id": i,
                    "job_title": job.title,
                    "company": job.company,
                    "status": "error",
                    "error": str(e),
                })
    
    async def _load_resume(self) -> Resume:
        """Load Kent's resume."""
        # For now, create a simple resume object
        # In production, you'd parse the PDF
        return Resume(
            file_path=RESUME_PATH,
            raw_text="",  # Would be extracted from PDF
            parsed_data={
                "name": "Kent Le",
                "email": "kle4311@gmail.com",
                "phone": "(404) 934-0630",
                "location": "Auburn, AL",
                "summary": "Customer Success professional with supply chain background",
                "skills": ["CRM", "Salesforce", "Data Analysis", "Vietnamese"],
            }
        )
    
    def _prioritize_jobs(self, jobs: list) -> list:
        """Prioritize jobs for application."""
        scored_jobs = []
        
        for job in jobs:
            score = 0
            
            # Easy Apply bonus
            if job.easy_apply:
                score += 10
            
            # Location preference
            location_lower = job.location.lower()
            if "auburn" in location_lower:
                score += 5
            if "atlanta" in location_lower:
                score += 4
            if "birmingham" in location_lower:
                score += 3
            if "remote" in location_lower or job.remote:
                score += 5
            
            # Recent posting bonus
            if job.posted_date:
                days_ago = (datetime.now() - job.posted_date).days
                if days_ago <= 1:
                    score += 3
                elif days_ago <= 3:
                    score += 2
                elif days_ago <= 7:
                    score += 1
            
            scored_jobs.append((job, score))
        
        # Sort by score descending
        scored_jobs.sort(key=lambda x: x[1], reverse=True)
        return [job for job, _ in scored_jobs]
    
    async def _apply_to_job(self, job, resume: Resume):
        """Apply to a single job."""
        from adapters import get_adapter
        
        # Detect platform and get adapter
        try:
            adapter = get_adapter(job.url, self.browser_manager)
        except ValueError:
            # Unknown platform - return external application
            from adapters.base import ApplicationResult
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message="Platform not supported for auto-apply",
                external_url=job.url
            )
        
        # Apply
        return await adapter.apply_to_job(
            job=job,
            resume=resume,
            profile=KENT_PROFILE,
            cover_letter=None,  # Could generate one with AI
            auto_submit=False   # Manual review for safety
        )
    
    def save_results(self):
        """Save campaign results."""
        self.results["end_time"] = datetime.now().isoformat()
        
        # Calculate duration
        start = datetime.fromisoformat(self.results["start_time"])
        end = datetime.fromisoformat(self.results["end_time"])
        duration = (end - start).total_seconds()
        self.results["duration_seconds"] = duration
        
        # Save JSON
        output_file = self.output_dir / f"{self.results['campaign_id']}_results.json"
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_file}")
        
        # Print summary
        print("\n" + "="*70)
        print("📊 CAMPAIGN SUMMARY")
        print("="*70)
        print(f"Target: {self.results['target']} applications")
        print(f"Completed: {self.results['completed']}")
        print(f"Successful: {self.results['successful']} ✅")
        print(f"Failed: {self.results['failed']} ❌")
        print(f"Duration: {duration/60:.1f} minutes")
        print(f"Success Rate: {self.results['successful']/max(self.results['completed'],1)*100:.1f}%")
        print("="*70)
    
    async def run(self):
        """Run the complete campaign."""
        print("\n" + "🚀"*35)
        print("   KENT LE - 10 REAL APPLICATIONS CAMPAIGN")
        print("   " + "🚀"*35)
        
        try:
            # Phase 1: Find jobs
            jobs = await self.find_jobs()
            
            if len(jobs) < 10:
                print(f"\n⚠️  Warning: Only found {len(jobs)} jobs, need 10")
            
            # Phase 2: Apply
            await self.apply_to_jobs(jobs)
            
        except Exception as e:
            print(f"\n❌ Campaign error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            await self.browser_manager.close_all()
            
            # Save results
            self.save_results()


async def main():
    """Run the campaign."""
    campaign = Kent10ApplicationCampaign()
    await campaign.run()


if __name__ == "__main__":
    asyncio.run(main())
