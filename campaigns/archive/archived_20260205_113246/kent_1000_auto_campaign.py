#!/usr/bin/env python3
"""
Kent Le - 1000 Automated Applications Campaign
Location: Auburn, AL (Remote/Hybrid/In-person)
Salary: $75k+
Target: Customer Success, Account Management, Sales, Business Development

This campaign automates job discovery and application across multiple platforms.
"""

import os
import sys
import asyncio
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters import (
    JobSpyAdapter, SearchConfig, UserProfile, Resume,
    ApplicationStatus, JobPosting, ApplicationResult,
    get_adapter, get_all_adapters_for_search
)
from browser.stealth_manager import StealthBrowserManager
from ai.kimi_service import KimiResumeOptimizer


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


@dataclass
class CampaignStats:
    """Track campaign progress."""
    target: int = 1000
    attempted: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    external_only: int = 0  # Jobs that require manual application
    by_platform: Dict[str, Dict] = field(default_factory=dict)
    errors: List[Dict] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    
    @property
    def success_rate(self) -> float:
        if self.attempted == 0:
            return 0.0
        return (self.successful / self.attempted) * 100
    
    @property
    def elapsed_minutes(self) -> float:
        return (datetime.now() - self.start_time).total_seconds() / 60


class Kent1000Campaign:
    """Automated 1000-application campaign for Kent Le."""
    
    def __init__(self, target: int = 1000):
        self.target = target
        self.stats = CampaignStats(target=target)
        self.browser_manager = StealthBrowserManager()
        self.ai_service = KimiResumeOptimizer()
        
        self.output_dir = Path(__file__).parent / "output" / f"kent_1000_{datetime.now().strftime('%Y%m%d_%H%M')}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Job queue
        self.jobs_queue: List[JobPosting] = []
        self.processed_urls: set = set()
        
        # Rate limiting
        self.min_delay = 3  # seconds between applications
        self.max_delay = 8
        
    async def discover_jobs(self) -> List[JobPosting]:
        """Discover 2000+ jobs to ensure we can apply to 1000."""
        print("\n" + "="*80)
        print("🔍 PHASE 1: MASS JOB DISCOVERY")
        print("="*80)
        print(f"\nTarget: Find 2000+ jobs to select 1000 best matches")
        print("Searching across: Indeed, LinkedIn, ZipRecruiter\n")
        
        all_jobs = []
        
        # Search configurations
        search_configs = [
            # Primary roles - high volume
            {"roles": ["Customer Success Manager"], "locations": ["Remote", "Atlanta, GA", "Birmingham, AL"]},
            {"roles": ["Account Manager"], "locations": ["Remote", "Atlanta, GA", "Columbus, GA"]},
            {"roles": ["Sales Representative"], "locations": ["Remote", "Atlanta, GA", "Auburn, AL"]},
            {"roles": ["Business Development Representative"], "locations": ["Remote", "Atlanta, GA"]},
            
            # Secondary roles - medium volume
            {"roles": ["Client Success Manager"], "locations": ["Remote", "Atlanta, GA"]},
            {"roles": ["Account Executive"], "locations": ["Remote", "Atlanta, GA", "Birmingham, AL"]},
            {"roles": ["Sales Development Representative"], "locations": ["Remote", "Atlanta, GA"]},
            {"roles": ["Customer Success Specialist"], "locations": ["Remote", "Atlanta, GA"]},
            
            # Tertiary roles - specific industries
            {"roles": ["Insurance Account Manager"], "locations": ["Remote", "Atlanta, GA"]},
            {"roles": ["Sales Consultant"], "locations": ["Remote", "Atlanta, GA"]},
            {"roles": ["Relationship Manager"], "locations": ["Remote", "Atlanta, GA"]},
        ]
        
        # Use JobSpy for bulk scraping
        sites = ["indeed", "linkedin", "zip_recruiter"]
        
        for config in search_configs:
            print(f"Searching: {config['roles'][0]}...", end=" ", flush=True)
            
            try:
                adapter = JobSpyAdapter(sites=sites)
                search_criteria = SearchConfig(
                    roles=config["roles"],
                    locations=config["locations"],
                    posted_within_days=14,  # Last 2 weeks
                    easy_apply_only=False,
                )
                
                jobs = await adapter.search_jobs(search_criteria)
                
                # Filter for salary if possible
                filtered_jobs = self._filter_jobs(jobs)
                
                print(f"Found {len(filtered_jobs)} jobs (filtered from {len(jobs)})")
                all_jobs.extend(filtered_jobs)
                
                # Early stop if we have enough
                if len(all_jobs) >= 2500:
                    print(f"\n✅ Reached target job count: {len(all_jobs)}")
                    break
                    
                await asyncio.sleep(2)  # Rate limiting
                
            except Exception as e:
                print(f"Error: {e}")
                continue
        
        # Deduplicate
        unique_jobs = self._deduplicate_jobs(all_jobs)
        
        print(f"\n{'='*80}")
        print(f"✅ DISCOVERY COMPLETE: {len(unique_jobs)} unique jobs found")
        print(f"{'='*80}")
        
        # Save discovered jobs
        self._save_discovered_jobs(unique_jobs)
        
        return unique_jobs
    
    def _filter_jobs(self, jobs: List[JobPosting]) -> List[JobPosting]:
        """Filter jobs based on criteria."""
        filtered = []
        
        for job in jobs:
            # Skip if already processed
            if job.url in self.processed_urls:
                continue
            
            # Check salary if available
            if job.salary_range:
                if not self._meets_salary_requirement(job.salary_range):
                    continue
            
            # Prefer remote/hybrid
            is_remote = job.remote or "remote" in job.location.lower()
            
            # Prioritize better companies/positions
            filtered.append(job)
            self.processed_urls.add(job.url)
        
        return filtered
    
    def _meets_salary_requirement(self, salary_range: str) -> bool:
        """Check if salary meets $75k minimum."""
        import re
        
        if not salary_range:
            return True
        
        # Extract numbers
        numbers = re.findall(r'\d{2,3},?\d{3}', salary_range)
        if not numbers:
            return True
        
        for num_str in numbers:
            num = int(num_str.replace(',', ''))
            # Check yearly salary
            if num >= 70000:  # Allow slightly below 75k
                return True
            # Check hourly (assume 2080 hours/year)
            if 30 <= num <= 100 and num * 2080 >= 70000:
                return True
        
        return False
    
    def _deduplicate_jobs(self, jobs: List[JobPosting]) -> List[JobPosting]:
        """Remove duplicate jobs by URL."""
        seen = set()
        unique = []
        
        for job in jobs:
            if job.url not in seen:
                seen.add(job.url)
                unique.append(job)
        
        return unique
    
    def _save_discovered_jobs(self, jobs: List[JobPosting]):
        """Save discovered jobs to file."""
        jobs_data = []
        for job in jobs:
            jobs_data.append({
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "salary": job.salary_range,
                "remote": job.remote,
                "easy_apply": job.easy_apply,
                "description": job.description[:500] if job.description else "",
            })
        
        output_file = self.output_dir / "discovered_jobs.json"
        with open(output_file, 'w') as f:
            json.dump(jobs_data, f, indent=2)
        
        print(f"💾 Saved {len(jobs)} jobs to {output_file}")
    
    async def apply_to_jobs(self, jobs: List[JobPosting]):
        """Apply to jobs until we reach 1000 successful applications."""
        print("\n" + "="*80)
        print("📝 PHASE 2: AUTOMATED APPLICATIONS")
        print("="*80)
        print(f"\nTarget: {self.target} successful applications")
        print(f"Available jobs: {len(jobs)}")
        print(f"Expected success rate: 60-75%")
        print(f"Estimated time: 8-12 hours\n")
        
        # Load resume
        resume = await self._load_resume()
        
        # Sort jobs by priority
        prioritized_jobs = self._prioritize_jobs(jobs)
        
        # Apply to jobs
        for i, job in enumerate(prioritized_jobs):
            if self.stats.successful >= self.target:
                print(f"\n🎉 TARGET REACHED: {self.stats.successful} successful applications!")
                break
            
            # Progress update every 10 jobs
            if i % 10 == 0:
                self._print_progress()
            
            # Apply to job
            await self._apply_single_job(job, resume, i + 1, len(prioritized_jobs))
            
            # Rate limiting
            delay = random.uniform(self.min_delay, self.max_delay)
            await asyncio.sleep(delay)
            
            # Save progress every 50 jobs
            if i % 50 == 0 and i > 0:
                self._save_progress()
        
        # Final save
        self._save_progress()
    
    def _prioritize_jobs(self, jobs: List[JobPosting]) -> List[JobPosting]:
        """Prioritize jobs for application order."""
        scored_jobs = []
        
        for job in jobs:
            score = 0
            
            # Easy Apply gets highest priority
            if job.easy_apply:
                score += 100
            
            # Remote positions
            if job.remote or "remote" in job.location.lower():
                score += 50
            
            # High salary
            if job.salary_range:
                if "80000" in job.salary_range or "90000" in job.salary_range:
                    score += 30
                elif "75000" in job.salary_range or "70000" in job.salary_range:
                    score += 20
            
            # Location preference
            location_lower = job.location.lower()
            if "auburn" in location_lower:
                score += 40
            elif "atlanta" in location_lower:
                score += 35
            elif "columbus" in location_lower:
                score += 30
            elif "birmingham" in location_lower:
                score += 25
            
            # Relevant title keywords
            title_lower = job.title.lower()
            if "customer success" in title_lower:
                score += 20
            elif "account manager" in title_lower:
                score += 15
            elif "sales" in title_lower:
                score += 10
            
            scored_jobs.append((job, score))
        
        # Sort by score descending
        scored_jobs.sort(key=lambda x: x[1], reverse=True)
        return [job for job, _ in scored_jobs]
    
    async def _load_resume(self) -> Resume:
        """Load Kent's resume."""
        # Parse resume with AI
        resume_text = self._extract_resume_text()
        
        return Resume(
            file_path=RESUME_PATH,
            raw_text=resume_text,
            parsed_data={
                "name": "Kent Le",
                "email": "kle4311@gmail.com",
                "phone": "(404) 934-0630",
                "location": "Auburn, AL",
                "summary": "Customer Success professional with supply chain background",
                "skills": ["CRM", "Salesforce", "Data Analysis", "Vietnamese", "Account Management"],
            }
        )
    
    def _extract_resume_text(self) -> str:
        """Extract text from PDF resume."""
        try:
            import PyPDF2
            with open(RESUME_PATH, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                return text
        except Exception as e:
            print(f"Warning: Could not extract resume text: {e}")
            return ""
    
    async def _apply_single_job(self, job: JobPosting, resume: Resume, current: int, total: int):
        """Apply to a single job."""
        self.stats.attempted += 1
        
        try:
            # Get platform adapter
            adapter = get_adapter(job.url, self.browser_manager)
            platform = adapter.platform.value
            
            # Update platform stats
            if platform not in self.stats.by_platform:
                self.stats.by_platform[platform] = {"attempted": 0, "successful": 0, "failed": 0}
            self.stats.by_platform[platform]["attempted"] += 1
            
            # Apply
            result = await adapter.apply_to_job(
                job=job,
                resume=resume,
                profile=KENT_PROFILE,
                cover_letter=None,
                auto_submit=False  # Manual review for safety
            )
            
            # Process result
            if result.status == ApplicationStatus.SUBMITTED:
                self.stats.successful += 1
                self.stats.by_platform[platform]["successful"] += 1
                
            elif result.status == ApplicationStatus.PENDING_REVIEW:
                # Count as successful if pending review
                self.stats.successful += 1
                self.stats.by_platform[platform]["successful"] += 1
                
            elif result.status == ApplicationStatus.EXTERNAL_APPLICATION:
                self.stats.external_only += 1
                self.stats.by_platform[platform]["external"] = self.stats.by_platform[platform].get("external", 0) + 1
                
            else:
                self.stats.failed += 1
                self.stats.by_platform[platform]["failed"] += 1
                
        except Exception as e:
            self.stats.failed += 1
            self.stats.errors.append({
                "job_id": job.id,
                "job_url": job.url,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    def _print_progress(self):
        """Print campaign progress."""
        elapsed = self.stats.elapsed_minutes
        rate = self.stats.successful / (elapsed / 60) if elapsed > 0 else 0
        
        print(f"\n{'='*80}")
        print(f"📊 PROGRESS UPDATE ({datetime.now().strftime('%H:%M:%S')})")
        print(f"{'='*80}")
        print(f"Target: {self.target} | Successful: {self.stats.successful} | Failed: {self.stats.failed}")
        print(f"Success Rate: {self.stats.success_rate:.1f}% | External Only: {self.stats.external_only}")
        print(f"Elapsed: {elapsed:.1f} min | Rate: {rate:.1f} apps/hour")
        print(f"ETA: {(self.target - self.stats.successful) / max(rate, 1):.1f} hours")
        print(f"{'='*80}\n")
    
    def _save_progress(self):
        """Save campaign progress to file."""
        progress_file = self.output_dir / "campaign_progress.json"
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "stats": {
                "target": self.stats.target,
                "attempted": self.stats.attempted,
                "successful": self.stats.successful,
                "failed": self.stats.failed,
                "external_only": self.stats.external_only,
                "success_rate": self.stats.success_rate,
                "by_platform": self.stats.by_platform,
            },
            "elapsed_minutes": self.stats.elapsed_minutes,
            "errors": self.stats.errors[-20:],  # Last 20 errors
        }
        
        with open(progress_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    async def run(self):
        """Run the complete 1000-application campaign."""
        print("\n" + "🚀"*40)
        print("   KENT LE - 1000 AUTOMATED APPLICATIONS CAMPAIGN")
        print("   " + "🚀"*40)
        print(f"\n   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Target: {self.target} successful applications")
        print(f"   Location: Auburn, AL (Remote/Hybrid/In-person)")
        print(f"   Salary: $75k+")
        print()
        
        try:
            # Phase 1: Discover jobs
            jobs = await self.discover_jobs()
            
            if len(jobs) < self.target:
                print(f"\n⚠️  Warning: Only found {len(jobs)} jobs, need {self.target}")
                print("Continuing with available jobs...")
            
            # Phase 2: Apply to jobs
            await self.apply_to_jobs(jobs)
            
        except Exception as e:
            print(f"\n❌ Campaign error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            await self.browser_manager.close_all()
            
            # Final report
            self._print_final_report()
    
    def _print_final_report(self):
        """Print final campaign report."""
        elapsed = self.stats.elapsed_minutes
        
        print("\n" + "="*80)
        print("📊 FINAL CAMPAIGN REPORT")
        print("="*80)
        print(f"\nCampaign ID: {self.output_dir.name}")
        print(f"Started: {self.stats.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {elapsed:.1f} minutes ({elapsed/60:.1f} hours)")
        print()
        print("RESULTS:")
        print(f"  Target: {self.stats.target}")
        print(f"  Attempted: {self.stats.attempted}")
        print(f"  Successful: {self.stats.successful} ✅")
        print(f"  Failed: {self.stats.failed} ❌")
        print(f"  External Only: {self.stats.external_only} 🔗")
        print(f"  Success Rate: {self.stats.success_rate:.1f}%")
        print()
        print("BY PLATFORM:")
        for platform, stats in self.stats.by_platform.items():
            success_rate = (stats.get("successful", 0) / max(stats["attempted"], 1)) * 100
            print(f"  {platform}: {stats['attempted']} attempted, {stats.get('successful', 0)} successful ({success_rate:.0f}%)")
        print()
        print(f"Output Directory: {self.output_dir}")
        print("="*80)


async def main():
    """Run the campaign."""
    # Allow target override from command line
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    
    campaign = Kent1000Campaign(target=target)
    await campaign.run()


if __name__ == "__main__":
    asyncio.run(main())
