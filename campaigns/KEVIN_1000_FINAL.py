#!/usr/bin/env python3
"""
KEVIN BELTRAN - 1000 SUCCESSFUL APPLICATIONS (FINAL)
With validation, prescraping, and confirmation tracking
"""

import os
import sys
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load credentials
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

# KEVIN'S PROFILE
KEVIN = {
    "first_name": "Kevin",
    "last_name": "Beltran",
    "email": "beltranrkevin@gmail.com",
    "phone": "770-378-2545",
    "location": "Atlanta, GA",
    "resume_path": "Test Resumes/Kevin_Beltran_Resume.pdf",
    "linkedin": "",
    "salary": "$85,000 - $120,000"
}

print("=" * 80)
print("🚀 KEVIN BELTRAN - 1000 SUCCESSFUL APPLICATIONS (VALIDATED)")
print("=" * 80)
print(f"👤 {KEVIN['first_name']} {KEVIN['last_name']} | {KEVIN['location']}")
print(f"📧 {KEVIN['email']}")
print()


class JobPrescraper:
    """Prescrape jobs from multiple sources to get real listings."""
    
    def __init__(self):
        self.all_jobs: List[Dict] = []
        self.seen_urls = set()
    
    def add_job(self, job: Dict) -> bool:
        """Add job if unique and valid."""
        url = job.get('url', '')
        if not url or url in self.seen_urls:
            return False
        if not url.startswith('http'):
            return False
        self.seen_urls.add(url)
        self.all_jobs.append(job)
        return True
    
    def scrape_all_sources(self, target: int = 1000) -> List[Dict]:
        """Scrape from multiple job boards."""
        print("📋 PRESCRAPING JOBS FROM MULTIPLE SOURCES")
        print("=" * 80)
        
        # Source 1: JobSpy (LinkedIn, Indeed, ZipRecruiter)
        self._scrape_jobspy()
        
        # Source 2: Load any previously collected real jobs
        self._load_cached_jobs()
        
        print(f"\n✅ Total unique jobs collected: {len(self.all_jobs)}")
        return self.all_jobs[:target]
    
    def _scrape_jobspy(self):
        """Scrape using JobSpy."""
        print("\n🕷️  Source 1: JobSpy (LinkedIn, Indeed, ZipRecruiter)")
        
        try:
            from jobspy import scrape_jobs
            
            search_terms = [
                "ServiceNow Business Analyst",
                "ServiceNow Consultant",
                "ITSM Analyst",
                "ServiceNow Administrator",
                "IT Business Analyst"
            ]
            
            locations = ["Remote", "Atlanta, GA", "Washington, DC"]
            
            for term in search_terms[:3]:  # Limit terms
                for location in locations[:2]:  # Limit locations
                    if len(self.all_jobs) >= 1000:
                        break
                    
                    try:
                        df = scrape_jobs(
                            site_name=["linkedin", "indeed"],
                            search_term=term,
                            location=location,
                            results_wanted=50,
                            hours_old=168,
                            is_remote=(location == "Remote")
                        )
                        
                        if len(df) > 0:
                            for _, row in df.iterrows():
                                job = {
                                    "id": f"js_{len(self.all_jobs):05d}",
                                    "title": str(row.get('title', '')),
                                    "company": str(row.get('company', '')),
                                    "location": str(row.get('location', '')),
                                    "url": str(row.get('job_url', '')),
                                    "platform": str(row.get('site', 'unknown')),
                                    "description": str(row.get('description', ''))[:300],
                                    "is_remote": bool(row.get('is_remote', False)),
                                    "source": "jobspy"
                                }
                                self.add_job(job)
                            
                            print(f"   ✅ '{term}' in '{location or 'Any'}': {len(df)} jobs")
                            
                    except Exception as e:
                        print(f"   ⚠️  Error: {e}")
                        continue
                    
        except ImportError:
            print("   ⚠️  JobSpy not available")
    
    def _load_cached_jobs(self):
        """Load previously scraped jobs."""
        cache_files = [
            "output/kevin_1000_real_fast/jobs_1000.json",
            "output/kevin_1000_all_real/all_real_jobs.json",
            "ats_automation/testing/collected_jobs_500.json"
        ]
        
        for cache_file in cache_files:
            path = Path(cache_file)
            if path.exists():
                try:
                    with open(path) as f:
                        jobs = json.load(f)
                        added = 0
                        for job in jobs:
                            if self.add_job(job):
                                added += 1
                        print(f"\n📁 Loaded {added} jobs from {cache_file}")
                except:
                    pass


class ValidatedApplicationCampaign:
    """Campaign with validation to ensure real submissions."""
    
    def __init__(self, jobs: List[Dict]):
        self.jobs = jobs
        self.stats = {
            "started": datetime.now().isoformat(),
            "attempted": 0,
            "validated_successful": 0,
            "failed": 0,
            "confirmation_ids": [],
            "screenshots": []
        }
        self.output_dir = Path("output/kevin_1000_validated")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def apply_with_validation(self, job: Dict) -> Dict:
        """Apply and validate the submission."""
        from browser.stealth_manager import StealthBrowserManager
        from adapters.validation import SubmissionValidator
        
        result = {
            "job_id": job['id'],
            "company": job['company'],
            "title": job['title'],
            "url": job['url'],
            "status": "attempted",
            "validated": False,
            "confirmation_id": None,
            "screenshot": None,
            "error": None
        }
        
        try:
            manager = StealthBrowserManager()
            await manager.initialize()
            
            # Create session
            session = await manager.create_stealth_session(
                platform=job.get('platform', 'generic'),
                use_proxy=True
            )
            
            page = session.page
            
            # Navigate to job
            try:
                await page.goto(job['url'], timeout=20000, wait_until="domcontentloaded")
                await asyncio.sleep(3)
            except Exception as e:
                result["error"] = f"Navigation failed: {str(e)[:50]}"
                await manager.close_session(session.session_id)
                await manager.close_all()
                return result
            
            # Look for apply button and click
            apply_clicked = False
            for selector in [
                'button:has-text("Apply")',
                'a:has-text("Apply")',
                'button:has-text("Easy Apply")',
                '.apply-button'
            ]:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        apply_clicked = True
                        await asyncio.sleep(3)
                        break
                except:
                    continue
            
            if not apply_clicked:
                result["error"] = "No apply button found"
                await manager.close_session(session.session_id)
                await manager.close_all()
                return result
            
            # Fill form fields
            fields_filled = []
            field_mappings = [
                ('input[name*="first"]', KEVIN['first_name']),
                ('input[name*="last"]', KEVIN['last_name']),
                ('input[type="email"]', KEVIN['email']),
                ('input[type="tel"]', KEVIN['phone']),
            ]
            
            for selector, value in field_mappings:
                try:
                    field = page.locator(selector).first
                    if await field.count() > 0 and await field.is_visible():
                        await field.fill(value)
                        fields_filled.append(selector)
                except:
                    continue
            
            # Upload resume
            try:
                resume_path = Path(KEVIN['resume_path']).resolve()
                if resume_path.exists():
                    file_input = page.locator('input[type="file"]').first
                    if await file_input.count() > 0:
                        await file_input.set_input_files(str(resume_path))
                        await asyncio.sleep(2)
            except:
                pass
            
            # Click submit
            submit_clicked = False
            for selector in ['button[type="submit"]', 'button:has-text("Submit")']:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        submit_clicked = True
                        await asyncio.sleep(5)  # Wait for submission
                        break
                except:
                    continue
            
            if not submit_clicked:
                result["error"] = "Submit button not found or not clickable"
                await manager.close_session(session.session_id)
                await manager.close_all()
                return result
            
            # VALIDATE SUBMISSION
            validation = await SubmissionValidator.validate(
                page=page,
                job_id=job['id'],
                platform=job.get('platform', 'generic'),
                screenshot_dir=str(self.output_dir / "screenshots")
            )
            
            result["validated"] = validation['success']
            result["confirmation_id"] = validation.get('confirmation_id')
            result["screenshot"] = validation.get('screenshot_path')
            result["validation_message"] = validation.get('message', '')
            
            await manager.close_session(session.session_id)
            await manager.close_all()
            
        except Exception as e:
            result["error"] = str(e)[:100]
        
        return result
    
    async def run(self):
        """Run the validated campaign."""
        print("\n" + "=" * 80)
        print("🚀 STARTING VALIDATED APPLICATIONS")
        print("=" * 80)
        print(f"Total jobs: {len(self.jobs)}")
        print(f"Estimated time: {len(self.jobs) * 2 / 60:.1f} hours")
        print()
        
        start_time = time.time()
        
        for i, job in enumerate(self.jobs):
            print(f"[{i+1:4d}/{len(self.jobs)}] {job['company'][:25]:25s} | ", end="", flush=True)
            
            result = await self.apply_with_validation(job)
            
            self.stats["attempted"] += 1
            
            if result and result.get("validated"):
                self.stats["validated_successful"] += 1
                print(f"✅ VALIDATED", end="")
                if result.get("confirmation_id"):
                    print(f" | ID: {result['confirmation_id'][:15]}", end="")
                    self.stats["confirmation_ids"].append(result["confirmation_id"])
            else:
                self.stats["failed"] += 1
                if result and result.get('error'):
                    error_msg = result.get('error')
                elif result:
                    error_msg = 'Failed'
                else:
                    error_msg = 'No result'
                print(f"❌ {error_msg[:30]}", end="")
            
            print()
            
            # Save progress every 25
            if self.stats["attempted"] % 25 == 0:
                self._save_progress()
                self._print_stats()
            
            # Brief pause
            await asyncio.sleep(1)
        
        # Final report
        elapsed = time.time() - start_time
        self._save_progress()
        self._print_final_report(elapsed)
    
    def _save_progress(self):
        """Save progress to file."""
        with open(self.output_dir / "progress.json", 'w') as f:
            json.dump(self.stats, f, indent=2, default=str)
    
    def _print_stats(self):
        """Print current stats."""
        rate = (self.stats["validated_successful"] / self.stats["attempted"] * 100) if self.stats["attempted"] > 0 else 0
        print(f"\n📊 Stats: {self.stats['attempted']} attempted | {self.stats['validated_successful']} validated ({rate:.1f}%) | {len(self.stats['confirmation_ids'])} confirmations\n")
    
    def _print_final_report(self, elapsed: float):
        """Print final report."""
        print("\n" + "=" * 80)
        print("📊 FINAL REPORT - VALIDATED CAMPAIGN")
        print("=" * 80)
        print(f"Total Attempted: {self.stats['attempted']}")
        print(f"Validated Successful: {self.stats['validated_successful']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Success Rate: {(self.stats['validated_successful'] / self.stats['attempted'] * 100):.2f}%")
        print(f"Confirmation IDs: {len(self.stats['confirmation_ids'])}")
        print(f"Duration: {elapsed/3600:.2f} hours")
        print()
        print(f"Screenshots saved: {self.output_dir}/screenshots/")
        print(f"Progress file: {self.output_dir}/progress.json")


async def main():
    # Prescrape jobs
    scraper = JobPrescraper()
    jobs = scraper.scrape_all_sources(target=1000)
    
    if len(jobs) == 0:
        print("❌ No jobs found!")
        return
    
    print(f"\n🎯 Ready to process {len(jobs)} jobs")
    print("\n⏳ Starting in 3 seconds...")
    import time
    time.sleep(3)
    
    # Run campaign
    campaign = ValidatedApplicationCampaign(jobs)
    await campaign.run()


if __name__ == "__main__":
    asyncio.run(main())
