#!/usr/bin/env python3
"""
KEVIN BELTRAN - 1000 APPLICATIONS (UNIFIED FRAMEWORK)
Uses the new job board pipeline with real scraping

Features:
- Multi-source scraping (Dice, Indeed RSS, Greenhouse, Lever)
- Intelligent deduplication across boards
- ATS-specific field mapping
- Validation with confirmation tracking
- Session pooling for efficiency
"""

import asyncio
import argparse
import json
import logging
import sys
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import traceback

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import unified framework
from adapters.job_boards import (
    SearchCriteria, UnifiedJobPipeline,
    DiceScraper, IndeedRssScraper, 
    GreenhouseAPIScraper, LeverAPIScraper
)
from adapters.job_boards.field_mappings import FieldMappings, CustomFieldHandlers
from adapters.validation import SubmissionValidator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class CampaignConfig:
    """Kevin Beltran's campaign configuration."""
    # Candidate Info
    first_name: str = "Kevin"
    last_name: str = "Beltran"
    email: str = "beltranrkevin@gmail.com"
    phone: str = "770-378-2545"
    linkedin: str = ""
    location: str = "Atlanta, GA"
    
    # Resume
    resume_path: str = "Test Resumes/Kevin_Beltran_Resume.pdf"
    
    # Search Criteria
    queries: List[str] = None
    locations: List[str] = None
    remote_only: bool = True
    
    # Campaign Settings
    target_jobs: int = 1000
    max_concurrent: int = 5
    rate_limit_delay: int = 30
    enable_validation: bool = True
    auto_submit: bool = True
    
    def __post_init__(self):
        if self.queries is None:
            self.queries = [
                "ServiceNow Business Analyst",
                "ServiceNow Consultant",
                "ITSM Analyst",
                "ServiceNow Administrator",
                "Federal ServiceNow Analyst"
            ]
        if self.locations is None:
            self.locations = ["Remote", "Atlanta, GA", "Washington, DC"]


class KevinUnifiedCampaign:
    """Kevin's 1000-application campaign using unified framework."""
    
    def __init__(self, config: CampaignConfig):
        self.config = config
        self.output_dir = Path("campaigns/output/kevin_1000_unified")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Stats
        self.stats = {
            "scraped": 0,
            "attempted": 0,
            "validated_successful": 0,
            "failed": 0,
            "confirmation_ids": [],
            "errors": [],
            "by_ats": {},
            "by_source": {}
        }
        
        self.results: List[Dict] = []
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown gracefully."""
        logger.info("\n⚠️  Shutdown signal received, finishing current job...")
        self.running = False
    
    async def scrape_jobs(self) -> List[Dict]:
        """Scrape jobs from multiple sources using unified pipeline."""
        logger.info("="*70)
        logger.info("📋 PRESCRAPING JOBS FROM MULTIPLE SOURCES")
        logger.info("="*70)
        
        # Create pipeline with scrapers
        pipeline = UnifiedJobPipeline()
        pipeline.add_scraper(DiceScraper())
        pipeline.add_scraper(IndeedRssScraper())
        pipeline.add_scraper(GreenhouseAPIScraper())
        pipeline.add_scraper(LeverAPIScraper())
        
        all_jobs = []
        
        # Search for each query/location combination
        for query in self.config.queries:
            for location in self.config.locations:
                if not self.running:
                    break
                    
                criteria = SearchCriteria(
                    query=query,
                    location=location,
                    remote_only=self.config.remote_only,
                    max_results=200  # Per search
                )
                
                try:
                    logger.info(f"\n🔍 Searching: '{query}' in '{location}'")
                    jobs = await pipeline.search_all(criteria)
                    
                    # Convert to dict format
                    for job in jobs:
                        all_jobs.append({
                            "id": job.id,
                            "title": job.title,
                            "company": job.company,
                            "location": job.location,
                            "url": job.url,
                            "apply_url": job.apply_url or job.url,
                            "source": job.source,
                            "ats_type": pipeline.router.detect_ats(job.url),
                            "is_direct_apply": pipeline.router.is_direct_application_url(job.url),
                            "remote": job.remote,
                            "clearance_required": job.clearance_required,
                            "posted_date": job.posted_date.isoformat() if job.posted_date else None
                        })
                    
                    logger.info(f"   ✅ Found {len(jobs)} jobs")
                    
                except Exception as e:
                    logger.error(f"   ❌ Search failed: {e}")
                    continue
                
                # Brief delay between searches
                await asyncio.sleep(2)
        
        # Get stats
        stats = pipeline.get_stats()
        self.stats["by_source"] = stats.get('by_source', {})
        self.stats["by_ats"] = stats.get('by_ats', {})
        
        logger.info(f"\n📊 Scraping Complete:")
        logger.info(f"   Total unique jobs: {len(all_jobs)}")
        logger.info(f"   By source: {self.stats['by_source']}")
        logger.info(f"   By ATS: {self.stats['by_ats']}")
        
        return all_jobs[:self.config.target_jobs]
    
    async def apply_to_job(self, job: Dict) -> Dict:
        """Apply to a single job with validation."""
        from browser.stealth_manager import StealthBrowserManager
        
        result = {
            "job_id": job['id'],
            "company": job['company'],
            "title": job['title'],
            "url": job['url'],
            "ats_type": job.get('ats_type', 'unknown'),
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
                platform=job.get('source', 'generic'),
                use_proxy=True
            )
            
            page = session.page
            apply_url = job.get('apply_url') or job['url']
            
            # Navigate
            try:
                await page.goto(apply_url, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(3)
            except Exception as e:
                result["error"] = f"Navigation failed: {str(e)[:50]}"
                await manager.close_session(session.session_id)
                await manager.close_all()
                return result
            
            # Use field mappings for the ATS type
            ats_type = job.get('ats_type', 'generic')
            field_map = FieldMappings.get_mappings(ats_type)
            
            # Fill fields using mappings
            filled_count = 0
            for field_key, selector in field_map.items():
                try:
                    value = self._get_field_value(field_key)
                    if not value:
                        continue
                    
                    field = page.locator(selector).first
                    if await field.count() > 0 and await field.is_visible():
                        await field.fill(value)
                        filled_count += 1
                except:
                    continue
            
            result["fields_filled"] = filled_count
            
            # Upload resume
            try:
                resume_path = Path(self.config.resume_path).resolve()
                if resume_path.exists():
                    file_input = page.locator('input[type="file"]').first
                    if await file_input.count() > 0:
                        await file_input.set_input_files(str(resume_path))
                        await asyncio.sleep(2)
            except:
                pass
            
            # Submit if auto-submit enabled
            if self.config.auto_submit:
                submit_selectors = FieldMappings.get_submit_selectors(ats_type)
                for selector in submit_selectors:
                    try:
                        btn = page.locator(selector).first
                        if await btn.count() > 0 and await btn.is_visible():
                            await btn.click()
                            await asyncio.sleep(5)
                            break
                    except:
                        continue
            
            # Validate submission
            if self.config.enable_validation:
                validation = await SubmissionValidator.validate(
                    page=page,
                    job_id=job['id'],
                    platform=ats_type,
                    screenshot_dir=str(self.output_dir / "screenshots")
                )
                
                result["validated"] = validation.get('success', False)
                result["confirmation_id"] = validation.get('confirmation_id')
                result["screenshot"] = validation.get('screenshot_path')
                result["validation_message"] = validation.get('message', '')
            
            await manager.close_session(session.session_id)
            await manager.close_all()
            
        except Exception as e:
            result["error"] = str(e)[:100]
            logger.error(f"Error applying to {job['company']}: {e}")
        
        return result
    
    def _get_field_value(self, field_key: str) -> Optional[str]:
        """Get value for a field key."""
        mapping = {
            'first_name': self.config.first_name,
            'last_name': self.config.last_name,
            'email': self.config.email,
            'phone': self.config.phone,
            'location': self.config.location,
            'linkedin': self.config.linkedin
        }
        return mapping.get(field_key)
    
    async def run_campaign(self, jobs: List[Dict]):
        """Run the application campaign."""
        logger.info("\n" + "="*70)
        logger.info("🚀 STARTING VALIDATED APPLICATIONS")
        logger.info("="*70)
        logger.info(f"Total jobs: {len(jobs)}")
        logger.info(f"Auto-submit: {self.config.auto_submit}")
        logger.info(f"Validation: {self.config.enable_validation}")
        logger.info(f"Rate limit: {self.config.rate_limit_delay}s between jobs")
        logger.info("="*70 + "\n")
        
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def process_job(job: Dict, index: int):
            async with semaphore:
                if not self.running:
                    return
                
                logger.info(f"[{index+1:4d}/{len(jobs)}] {job['company'][:30]:30s} | ", end="")
                
                result = await self.apply_to_job(job)
                self.results.append(result)
                
                self.stats["attempted"] += 1
                
                if result.get("validated"):
                    self.stats["validated_successful"] += 1
                    logger.info(f"✅ VALIDATED", end="")
                    if result.get("confirmation_id"):
                        logger.info(f" | ID: {result['confirmation_id'][:15]}", end="")
                        self.stats["confirmation_ids"].append(result["confirmation_id"])
                else:
                    self.stats["failed"] += 1
                    error = result.get('error') or 'Failed'
                    logger.info(f"❌ {error[:30]}", end="")
                
                logger.info("")
                
                # Save progress periodically
                if self.stats["attempted"] % 25 == 0:
                    self._save_progress()
                
                # Rate limiting
                await asyncio.sleep(self.config.rate_limit_delay)
        
        # Process all jobs
        tasks = [process_job(job, i) for i, job in enumerate(jobs)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Final save
        self._save_progress()
    
    def _save_progress(self):
        """Save progress to file."""
        progress_file = self.output_dir / "progress.json"
        with open(progress_file, 'w') as f:
            json.dump({
                "stats": self.stats,
                "results": self.results[-100:],  # Last 100
                "timestamp": datetime.now().isoformat()
            }, f, indent=2, default=str)
        
        logger.info(f"\n📊 Progress: {self.stats['attempted']} attempted | "
                   f"{self.stats['validated_successful']} validated | "
                   f"{len(self.stats['confirmation_ids'])} confirmations\n")
    
    def print_final_report(self):
        """Print final campaign report."""
        logger.info("\n" + "="*70)
        logger.info("📊 FINAL REPORT - KEVIN BELTRAN (UNIFIED)")
        logger.info("="*70)
        logger.info(f"Total Attempted: {self.stats['attempted']}")
        logger.info(f"Validated Successful: {self.stats['validated_successful']}")
        logger.info(f"Failed: {self.stats['failed']}")
        
        if self.stats['attempted'] > 0:
            rate = (self.stats['validated_successful'] / self.stats['attempted'] * 100)
            logger.info(f"Success Rate: {rate:.2f}%")
        
        logger.info(f"Confirmation IDs: {len(self.stats['confirmation_ids'])}")
        
        logger.info(f"\n📡 By Source:")
        for source, count in sorted(self.stats['by_source'].items(), key=lambda x: -x[1]):
            logger.info(f"  {source}: {count}")
        
        logger.info(f"\n🎯 By ATS Type:")
        for ats, count in sorted(self.stats['by_ats'].items(), key=lambda x: -x[1]):
            logger.info(f"  {ats}: {count}")
        
        logger.info("="*70)


async def main():
    parser = argparse.ArgumentParser(description='Kevin Beltran 1000 Applications (Unified)')
    parser.add_argument('--test', action='store_true', help='Test mode (10 jobs only)')
    parser.add_argument('--limit', type=int, default=1000, help='Max jobs to process')
    parser.add_argument('--delay', type=int, default=30, help='Seconds between jobs')
    parser.add_argument('--no-submit', action='store_true', help='Disable auto-submit')
    parser.add_argument('--no-validation', action='store_true', help='Disable validation')
    args = parser.parse_args()
    
    # Create config
    config = CampaignConfig(
        target_jobs=10 if args.test else args.limit,
        rate_limit_delay=args.delay,
        auto_submit=not args.no_submit,
        enable_validation=not args.no_validation
    )
    
    # Create and run campaign
    campaign = KevinUnifiedCampaign(config)
    
    try:
        # Phase 1: Scrape jobs
        jobs = await campaign.scrape_jobs()
        
        if len(jobs) == 0:
            logger.error("❌ No jobs found!")
            return
        
        # Phase 2: Apply
        await campaign.run_campaign(jobs)
        
        # Phase 3: Report
        campaign.print_final_report()
        
    except Exception as e:
        logger.error(f"Campaign failed: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
