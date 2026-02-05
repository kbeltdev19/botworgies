#!/usr/bin/env python3
"""
Simple Direct Campaign - Focus on actually submitting applications.

This campaign:
1. Discovers jobs with DIRECT ATS URLs only
2. Filters to simple forms (Greenhouse, Lever with quick-apply)
3. Uses VisualFormAgentV2 with verification
4. ONLY counts success if verified
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleDirectCampaign:
    """Simplified campaign focused on verified submissions."""
    
    # Platforms that work well with our automation
    SUPPORTED_PLATFORMS = ['greenhouse', 'lever']
    
    def __init__(self, profile_path: str, resume_path: str, target: int = 50):
        self.profile_path = profile_path
        self.resume_path = resume_path
        self.target = target
        
        # Load profile
        with open(profile_path) as f:
            self.profile = yaml.safe_load(f)
        
        self.discovered_jobs: List[Dict] = []
        self.results: List[Dict] = []
        self.stats = {
            'discovered': 0,
            'filtered': 0,
            'attempted': 0,
            'verified_success': 0,
            'failed': 0,
        }
        
        self.output_dir = Path('campaigns/output')
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def run(self):
        """Run the campaign."""
        logger.info("=" * 60)
        logger.info("Simple Direct Campaign - Verified Submissions Only")
        logger.info("=" * 60)
        logger.info(f"Target: {self.target} verified applications")
        logger.info(f"Profile: {self.profile.get('first_name')} {self.profile.get('last_name')}")
        logger.info(f"Resume: {self.resume_path}")
        logger.info("=" * 60)
        
        # Phase 1: Discover jobs
        await self._discover_jobs()
        
        # Phase 2: Filter to supported platforms
        await self._filter_jobs()
        
        # Phase 3: Apply with verification
        await self._apply_to_jobs()
        
        # Phase 4: Report
        await self._generate_report()
    
    async def _discover_jobs(self):
        """Discover jobs from JobSpy."""
        logger.info("\n[Phase 1] Discovering jobs...")
        
        from jobspy import scrape_jobs
        
        queries = ['ServiceNow', 'Software Engineer', 'IT Manager', 'DevOps']
        all_jobs = []
        
        for query in queries:
            try:
                df = scrape_jobs(
                    site_name=['indeed', 'zip_recruiter'],
                    search_term=query,
                    location='Remote',
                    results_wanted=50,
                    hours_old=72
                )
                
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        job = {
                            'id': str(abs(hash(row['job_url'])) % 10000000),
                            'title': row['title'],
                            'company': row['company'] if pd.notna(row['company']) else 'Unknown',
                            'location': row['location'] if pd.notna(row['location']) else 'Remote',
                            'url': row['job_url'],
                            'apply_url': row.get('job_url_direct') if pd.notna(row.get('job_url_direct')) else None,
                            'description': str(row.get('description', ''))[:500],
                        }
                        all_jobs.append(job)
                    
                    logger.info(f"  {query}: {len(df)} jobs")
            except Exception as e:
                logger.warning(f"  {query} failed: {e}")
        
        # Deduplicate
        seen = set()
        unique = []
        for job in all_jobs:
            if job['url'] not in seen:
                seen.add(job['url'])
                unique.append(job)
        
        self.discovered_jobs = unique
        self.stats['discovered'] = len(unique)
        logger.info(f"Total unique jobs: {len(unique)}")
    
    async def _filter_jobs(self):
        """Filter to supported platforms with direct URLs."""
        logger.info("\n[Phase 2] Filtering to supported platforms...")
        
        filtered = []
        
        for job in self.discovered_jobs:
            apply_url = job.get('apply_url')
            
            # Must have direct URL
            if not apply_url:
                continue
            
            # Skip Indeed-only URLs
            if 'indeed.com/job' in apply_url:
                continue
            
            # Check platform
            url_lower = apply_url.lower()
            platform = None
            
            if 'greenhouse' in url_lower or 'grnh.se' in url_lower:
                platform = 'greenhouse'
            elif 'lever' in url_lower:
                platform = 'lever'
            elif 'workday' in url_lower:
                platform = 'workday'
            else:
                platform = 'other'
            
            job['platform'] = platform
            
            # Prioritize supported platforms
            if platform in self.SUPPORTED_PLATFORMS:
                filtered.insert(0, job)  # Add to front
            else:
                filtered.append(job)
        
        self.discovered_jobs = filtered[:self.target * 2]  # Get 2x for buffer
        self.stats['filtered'] = len(self.discovered_jobs)
        
        # Show breakdown
        by_platform = {}
        for job in self.discovered_jobs:
            p = job['platform']
            by_platform[p] = by_platform.get(p, 0) + 1
        
        logger.info(f"Jobs with direct URLs: {len(filtered)}")
        logger.info("By platform:")
        for p, count in sorted(by_platform.items(), key=lambda x: -x[1]):
            logger.info(f"  - {p}: {count}")
    
    async def _apply_to_jobs(self):
        """Apply to jobs with verification."""
        logger.info("\n[Phase 3] Applying with verification...")
        
        from adapters.handlers.browser_manager import BrowserManager
        from ai.visual_form_agent_v2 import VisualFormAgentV2
        
        browser = BrowserManager(headless=False)  # Visible for debugging
        
        for i, job in enumerate(self.discovered_jobs, 1):
            if self.stats['verified_success'] >= self.target:
                logger.info(f"\n✅ Target reached: {self.target} verified applications")
                break
            
            self.stats['attempted'] += 1
            
            logger.info(f"\n[{i}/{len(self.discovered_jobs)}] {job['title']} @ {job['company']}")
            logger.info(f"    Platform: {job['platform']}")
            logger.info(f"    URL: {job['apply_url'][:70]}...")
            
            try:
                # Create new context for each job
                context, page = await browser.create_context()
                
                # Navigate to job
                await page.goto(job['apply_url'], wait_until='networkidle', timeout=60000)
                await asyncio.sleep(3)
                
                # Use V2 Agent
                agent = VisualFormAgentV2()
                await agent.initialize()
                
                result = await agent.apply(
                    page=page,
                    profile=self.profile,
                    job_data=job,
                    resume_path=self.resume_path
                )
                
                # Record result
                job_result = {
                    'job': job,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                }
                self.results.append(job_result)
                
                # Only count if VERIFIED success
                if result.get('verified'):
                    self.stats['verified_success'] += 1
                    logger.info(f"    ✅ VERIFIED SUCCESS! Confirmation: {result.get('confirmation_id')}")
                    
                    # Save immediately
                    self._save_progress()
                elif result.get('success') and not result.get('verified'):
                    self.stats['failed'] += 1
                    logger.warning(f"    ⚠️ Unverified success (likely false positive)")
                else:
                    self.stats['failed'] += 1
                    logger.warning(f"    ❌ Failed: {result.get('error', 'Unknown')}")
                
                await context.close()
                
                # Delay between applications
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"    ❌ Error: {e}")
                self.stats['failed'] += 1
                continue
        
        logger.info(f"\nApplications complete: {self.stats['verified_success']} verified / {self.stats['attempted']} attempted")
    
    def _save_progress(self):
        """Save current progress."""
        data = {
            'stats': self.stats,
            'verified_applications': [r for r in self.results if r['result'].get('verified')],
            'timestamp': datetime.now().isoformat()
        }
        
        path = self.output_dir / f'progress_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    async def _generate_report(self):
        """Generate final report."""
        logger.info("\n" + "=" * 60)
        logger.info("Final Report")
        logger.info("=" * 60)
        logger.info(f"Jobs discovered: {self.stats['discovered']}")
        logger.info(f"Jobs filtered: {self.stats['filtered']}")
        logger.info(f"Applications attempted: {self.stats['attempted']}")
        logger.info(f"Verified successful: {self.stats['verified_success']} ✅")
        logger.info(f"Failed: {self.stats['failed']}")
        
        if self.stats['verified_success'] > 0:
            success_rate = (self.stats['verified_success'] / self.stats['attempted']) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")
            
            logger.info("\nVerified Applications:")
            for r in self.results:
                if r['result'].get('verified'):
                    job = r['job']
                    logger.info(f"  ✅ {job['title']} @ {job['company']}")
                    logger.info(f"     Confirmation: {r['result'].get('confirmation_id')}")
        
        # Save final report
        report = {
            'stats': self.stats,
            'all_results': self.results,
            'timestamp': datetime.now().isoformat()
        }
        
        path = self.output_dir / f'REPORT_VERIFIED_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\nReport saved: {path}")


# Run it
if __name__ == "__main__":
    import sys
    import pandas as pd  # Needed for jobspy
    
    campaign = SimpleDirectCampaign(
        profile_path='campaigns/profiles/kevin_beltran.yaml',
        resume_path='Test Resumes/Kevin_Beltran_Resume.pdf',
        target=10
    )
    
    asyncio.run(campaign.run())
