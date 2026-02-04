#!/usr/bin/env python3
"""
Matt Edwards 1000 Applications - UNIFIED CAMPAIGN

Uses the ATS Router architecture:
1. Direct Apply (Greenhouse, Lever, Ashby) - Priority 1, 75% success
2. Native Flow (Indeed, LinkedIn) - Priority 2, 40% success  
3. Complex Forms (Workday, Taleo) - Priority 3, 20% success

Usage:
    python MATT_1000_UNIFIED.py --confirm --auto-submit --limit 1000
"""

import asyncio
import argparse
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('campaigns/output/matt_1000_unified.log')
    ]
)
logger = logging.getLogger(__name__)

# Import our new architecture
from adapters.ats_router import ATSRouter, PlatformCategory
from adapters.base import UserProfile, Resume, JobPosting, SearchConfig

# Import scrapers
from adapters.job_boards.greenhouse_api import GreenhouseAPIScraper
from adapters.job_boards.lever_api import LeverAPIScraper
from adapters.native_flow import NativeFlowHandler


@dataclass
class CampaignConfig:
    """Campaign configuration."""
    target_applications: int = 1000
    max_concurrent: int = 5
    auto_submit: bool = False
    
    # Platform priorities
    enable_direct_apply: bool = True      # Greenhouse, Lever, Ashby
    enable_native_flow: bool = True       # Indeed, LinkedIn
    enable_complex_forms: bool = False    # Workday, Taleo (disabled by default)
    
    # Limits per category
    max_direct_apply: int = 600
    max_native_flow: int = 300
    max_complex_forms: int = 100


@dataclass
class CampaignStats:
    """Campaign statistics."""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # By category
    direct_apply_attempted: int = 0
    direct_apply_success: int = 0
    native_flow_attempted: int = 0
    native_flow_success: int = 0
    complex_forms_attempted: int = 0
    complex_forms_success: int = 0
    
    total_jobs: int = 0
    
    def overall_success_rate(self) -> float:
        total = self.direct_apply_attempted + self.native_flow_attempted + self.complex_forms_attempted
        success = self.direct_apply_success + self.native_flow_success + self.complex_forms_success
        return success / max(total, 1)


class Matt1000UnifiedCampaign:
    """Unified campaign using ATS Router architecture."""
    
    def __init__(self, config: CampaignConfig):
        self.config = config
        self.stats = CampaignStats()
        self.router: Optional[ATSRouter] = None
        
        # Output
        self.output_dir = Path("campaigns/output/matt_1000_unified")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Candidate profile
        self.profile = UserProfile(
            first_name="Matt",
            last_name="Edwards",
            email="edwardsdmatt@gmail.com",
            phone="404-555-0123",
            linkedin="https://www.linkedin.com/in/matt-edwards-/",
            location="Atlanta, GA"
        )
        
        self.resume = Resume(
            file_path="data/matt_edwards_resume.pdf",
            text=""  # Would be parsed from PDF
        )
        
    async def initialize(self):
        """Initialize browser and router."""
        from browser.stealth_manager import StealthBrowserManager
        
        browser_manager = StealthBrowserManager()
        await browser_manager.initialize()
        
        self.router = ATSRouter(browser_manager)
        logger.info("✓ ATS Router initialized")
        
    async def run(self):
        """Run the complete campaign."""
        print("\n" + "="*70)
        print("🚀 MATT EDWARDS - 1000 APPLICATIONS (UNIFIED)")
        print("="*70)
        print(f"Target: {self.config.target_applications} applications")
        print(f"Direct Apply (Greenhouse/Lever): {self.config.max_direct_apply}")
        print(f"Native Flow (Indeed/LinkedIn): {self.config.max_native_flow}")
        print(f"Complex Forms (Workday/Taleo): {self.config.max_complex_forms}")
        print("="*70 + "\n")
        
        self.stats.started_at = datetime.now().isoformat()
        
        await self.initialize()
        
        # Phase 1: Direct Apply (highest success rate)
        if self.config.enable_direct_apply:
            await self._run_direct_apply()
        
        # Phase 2: Native Flow (medium success rate)
        if self.config.enable_native_flow:
            await self._run_native_flow()
        
        # Phase 3: Complex Forms (lowest success rate, queued last)
        if self.config.enable_complex_forms:
            await self._run_complex_forms()
        
        # Complete
        self.stats.completed_at = datetime.now().isoformat()
        self._save_final_report()
        self._print_summary()
        
    async def _run_direct_apply(self):
        """Run direct apply phase (Greenhouse, Lever, Ashby)."""
        logger.info("\n" + "="*70)
        logger.info("📦 PHASE 1: DIRECT APPLY (Greenhouse, Lever, Ashby)")
        logger.info("="*70)
        
        jobs = []
        
        # Scrape Greenhouse
        logger.info("\n🔍 Scraping Greenhouse...")
        async with GreenhouseAPIScraper() as scraper:
            gh_jobs = await scraper.search(SearchConfig(
                query="Customer Success Manager OR Cloud Delivery Manager OR Technical Account Manager",
                remote_only=True,
                max_results=self.config.max_direct_apply // 2
            ))
            for job in gh_jobs:
                jobs.append(JobPosting(
                    id=job.id,
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    url=job.url,
                    platform="greenhouse",
                    easy_apply=True
                ))
            logger.info(f"  Found {len(gh_jobs)} Greenhouse jobs")
        
        # Scrape Lever
        logger.info("\n🔍 Scraping Lever...")
        async with LeverAPIScraper() as scraper:
            lever_jobs = await scraper.search(SearchConfig(
                query="Customer Success OR Cloud OR Technical Account Manager",
                remote_only=True,
                max_results=self.config.max_direct_apply // 2
            ))
            for job in lever_jobs:
                jobs.append(JobPosting(
                    id=job.id,
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    url=job.url,
                    platform="lever",
                    easy_apply=True
                ))
            logger.info(f"  Found {len(lever_jobs)} Lever jobs")
        
        logger.info(f"\n📋 Total Direct Apply jobs: {len(jobs)}")
        
        # Apply to each job
        for i, job in enumerate(jobs[:self.config.max_direct_apply], 1):
            logger.info(f"\n[{i}/{min(len(jobs), self.config.max_direct_apply)}] {job.title} at {job.company}")
            
            try:
                result = await self.router.apply_to_job(
                    job=job,
                    resume=self.resume,
                    profile=self.profile,
                    auto_submit=self.config.auto_submit
                )
                
                self.stats.direct_apply_attempted += 1
                
                if result.status.value == "submitted":
                    self.stats.direct_apply_success += 1
                    logger.info(f"  ✓ Submitted - {result.confirmation_id}")
                elif result.status.value == "pending_review":
                    logger.info(f"  ⏸️  Pending review")
                else:
                    logger.info(f"  ✗ {result.message}")
                    
            except Exception as e:
                logger.error(f"  ✗ Error: {e}")
            
            # Rate limiting
            await asyncio.sleep(5)
        
        logger.info(f"\n📊 Direct Apply: {self.stats.direct_apply_success}/{self.stats.direct_apply_attempted} success")
        
    async def _run_native_flow(self):
        """Run native flow phase (Indeed, LinkedIn)."""
        logger.info("\n" + "="*70)
        logger.info("📦 PHASE 2: NATIVE FLOW (Indeed, LinkedIn)")
        logger.info("="*70)
        
        handler = NativeFlowHandler(self.router.browser_manager)
        
        # Indeed
        logger.info("\n🔍 Searching Indeed...")
        criteria = SearchConfig(
            roles=["Customer Success Manager", "Cloud Delivery Manager", "Technical Account Manager"],
            locations=["Remote"],
            posted_within_days=7
        )
        
        results = await handler.search_and_apply(
            platform='indeed',
            criteria=criteria,
            resume=self.resume,
            profile=self.profile,
            auto_submit=self.config.auto_submit,
            max_jobs=self.config.max_native_flow
        )
        
        for result in results:
            self.stats.native_flow_attempted += 1
            if result.status.value == "submitted":
                self.stats.native_flow_success += 1
        
        logger.info(f"\n📊 Indeed: {self.stats.native_flow_success}/{self.stats.native_flow_attempted} success")
        
    async def _run_complex_forms(self):
        """Run complex forms phase (Workday, Taleo) - queued last."""
        logger.info("\n" + "="*70)
        logger.info("📦 PHASE 3: COMPLEX FORMS (Workday, Taleo)")
        logger.info("="*70)
        logger.info("⚠️  These have lower success rates and take longer")
        
        # This would require finding Workday/Taleo jobs specifically
        # For now, skip or implement limited support
        logger.info("Skipping complex forms (implement later)")
        
    def _save_final_report(self):
        """Save final campaign report."""
        report = {
            'config': asdict(self.config),
            'stats': asdict(self.stats),
            'router_stats': self.router.get_stats() if self.router else {},
        }
        
        filepath = self.output_dir / 'final_report.json'
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"\n💾 Report saved to {filepath}")
        
    def _print_summary(self):
        """Print campaign summary."""
        print("\n" + "="*70)
        print("📋 CAMPAIGN SUMMARY")
        print("="*70)
        
        if self.stats.started_at and self.stats.completed_at:
            duration = (
                datetime.fromisoformat(self.stats.completed_at) -
                datetime.fromisoformat(self.stats.started_at)
            ).total_seconds() / 3600
            print(f"Duration: {duration:.1f} hours")
        
        print(f"\nDirect Apply (Greenhouse/Lever):")
        print(f"  Attempted: {self.stats.direct_apply_attempted}")
        print(f"  Success: {self.stats.direct_apply_success}")
        print(f"  Rate: {self.stats.direct_apply_success/max(self.stats.direct_apply_attempted,1):.1%}")
        
        print(f"\nNative Flow (Indeed/LinkedIn):")
        print(f"  Attempted: {self.stats.native_flow_attempted}")
        print(f"  Success: {self.stats.native_flow_success}")
        print(f"  Rate: {self.stats.native_flow_success/max(self.stats.native_flow_attempted,1):.1%}")
        
        print(f"\nOverall:")
        print(f"  Total Attempted: {self.stats.direct_apply_attempted + self.stats.native_flow_attempted}")
        print(f"  Total Success: {self.stats.direct_apply_success + self.stats.native_flow_success}")
        print(f"  Success Rate: {self.stats.overall_success_rate():.1%}")
        
        print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description='Matt Edwards 1000 Applications - Unified Campaign',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Unified campaign using ATS Router:
  Phase 1: Direct Apply (Greenhouse, Lever) - 75% success
  Phase 2: Native Flow (Indeed, LinkedIn) - 40% success
  Phase 3: Complex Forms (Workday, Taleo) - 20% success

Usage:
    python MATT_1000_UNIFIED.py --confirm --auto-submit --limit 1000
        """
    )
    
    parser.add_argument('--confirm', action='store_true', help='Confirm production run')
    parser.add_argument('--auto-submit', action='store_true', help='Enable auto-submit')
    parser.add_argument('--limit', type=int, default=1000, help='Maximum applications')
    parser.add_argument('--include-complex', action='store_true', help='Include Workday/Taleo')
    
    args = parser.parse_args()
    
    if args.auto_submit and not args.confirm:
        print("❌ --auto-submit requires --confirm")
        sys.exit(1)
    
    config = CampaignConfig(
        target_applications=args.limit,
        auto_submit=args.auto_submit,
        enable_complex_forms=args.include_complex
    )
    
    if args.auto_submit and not os.path.exists("data/matt_edwards_resume.pdf"):
        print("❌ Resume not found")
        sys.exit(1)
    
    campaign = Matt1000UnifiedCampaign(config)
    
    try:
        asyncio.run(campaign.run())
    except Exception as e:
        logger.error(f"Campaign failed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
