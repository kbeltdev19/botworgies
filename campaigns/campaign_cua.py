#!/usr/bin/env python3
"""
CUA Campaign - Computer Use Agent for job applications.

Combines BrowserBase-inspired patterns:
1. Exa AI semantic job discovery
2. Stagehand-style Agent for autonomous form filling
3. Kimi Vision for screenshot analysis
4. Verified submission (no false positives)
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


class CUACampaign:
    """
    Campaign using Computer Use Agent pattern.
    
    Key features:
    - Semantic job discovery (Exa + JobSpy)
    - Autonomous form filling (CUA Agent)
    - Real-time screenshot analysis
    - Verified submission only
    """
    
    def __init__(
        self,
        profile_path: str,
        resume_path: str,
        target: int = 10,
        max_steps_per_job: int = 20
    ):
        self.profile_path = profile_path
        self.resume_path = resume_path
        self.target = target
        self.max_steps = max_steps_per_job
        
        # Load profile
        with open(profile_path) as f:
            self.profile = yaml.safe_load(f)
        
        self.jobs: List[Dict] = []
        self.results: List[Dict] = []
        self.stats = {
            'discovered': 0,
            'attempted': 0,
            'verified_success': 0,
            'failed': 0,
        }
        
        self.output_dir = Path('campaigns/output')
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def run(self):
        """Run the CUA campaign."""
        logger.info("=" * 70)
        logger.info("CUA Campaign - Computer Use Agent")
        logger.info("=" * 70)
        logger.info(f"Profile: {self.profile.get('first_name')} {self.profile.get('last_name')}")
        logger.info(f"Target: {self.target} verified applications")
        logger.info(f"Max steps per job: {self.max_steps}")
        logger.info("=" * 70)
        
        # Phase 1: Discover jobs
        await self._discover_jobs()
        
        # Phase 2: Apply using CUA Agent
        await self._apply_with_agent()
        
        # Phase 3: Report
        await self._generate_report()
    
    async def _discover_jobs(self):
        """Discover jobs using hybrid approach."""
        logger.info("\n[Phase 1] Discovering jobs...")
        
        from ai.exa_job_search import HybridJobDiscovery
        
        discovery = HybridJobDiscovery()
        
        # Build search from profile
        desired_roles = self.profile.get('desired_roles', ['Software Engineer'])
        skills = self.profile.get('skills', ['Python', 'JavaScript'])[:5]
        
        primary_role = desired_roles[0] if desired_roles else "Software Engineer"
        
        self.jobs = await discovery.discover_jobs(
            role=primary_role,
            skills=skills,
            location="remote",
            target_count=self.target * 3  # Buffer for failures
        )
        
        self.stats['discovered'] = len(self.jobs)
        logger.info(f"Discovered: {len(self.jobs)} jobs")
        
        # Show breakdown
        by_source = {}
        for job in self.jobs:
            s = job.get('source', 'unknown')
            by_source[s] = by_source.get(s, 0) + 1
        
        logger.info("By source:")
        for s, count in by_source.items():
            logger.info(f"  - {s}: {count}")
    
    async def _apply_with_agent(self):
        """Apply using CUA Agent."""
        logger.info("\n[Phase 2] Applying with CUA Agent...")
        
        from adapters.handlers.browser_manager import BrowserManager
        from ai.job_agent_cua import JobAgentCUA
        
        browser = BrowserManager(headless=False)
        
        for i, job in enumerate(self.jobs, 1):
            if self.stats['verified_success'] >= self.target:
                logger.info(f"\n✅ Target reached: {self.target} verified applications")
                break
            
            self.stats['attempted'] += 1
            
            logger.info(f"\n[{i}/{len(self.jobs)}] {job['title'][:50]} @ {job['company']}")
            logger.info(f"    URL: {job['url'][:60]}...")
            
            try:
                # Create fresh context for each job
                context, page = await browser.create_context()
                
                # Initialize CUA Agent
                agent = JobAgentCUA()
                await agent.initialize()
                
                # Execute application
                instruction = f"""Apply for this {job['title']} position at {job['company']}.

Fill all required fields including:
- First and Last Name
- Email address
- Phone number
- Location (if required)
- Upload resume PDF
- Answer any required screening questions
- Submit the application

Verify the application was successfully submitted."""
                
                result = await agent.execute(
                    page=page,
                    instruction=instruction,
                    profile=self.profile,
                    resume_path=self.resume_path,
                    max_steps=self.max_steps
                )
                
                # Record result
                job_result = {
                    'job': job,
                    'result': result.to_dict(),
                    'actions': [
                        {
                            'type': a.action_type.value,
                            'description': a.description,
                            'success': a.success,
                            'error': a.error
                        }
                        for a in result.actions
                    ],
                    'timestamp': datetime.now().isoformat()
                }
                self.results.append(job_result)
                
                # Only count VERIFIED successes
                if result.success and result.completed:
                    self.stats['verified_success'] += 1
                    logger.info(f"    ✅ VERIFIED SUCCESS!")
                    logger.info(f"    Confirmation: {result.confirmation_id or 'N/A'}")
                    logger.info(f"    Actions: {len(result.actions)}")
                    
                    # Save progress
                    self._save_checkpoint()
                else:
                    self.stats['failed'] += 1
                    logger.warning(f"    ❌ Failed: {result.error or result.message}")
                
                await context.close()
                
                # Delay between jobs
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"    ❌ Error: {e}")
                self.stats['failed'] += 1
                continue
        
        logger.info(f"\nApplications complete:")
        logger.info(f"  Verified successful: {self.stats['verified_success']}")
        logger.info(f"  Failed: {self.stats['failed']}")
    
    def _save_checkpoint(self):
        """Save checkpoint with verified applications."""
        verified = [r for r in self.results if r['result'].get('verified')]
        
        data = {
            'stats': self.stats,
            'verified_applications': verified,
            'timestamp': datetime.now().isoformat()
        }
        
        path = self.output_dir / f'cua_checkpoint_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    async def _generate_report(self):
        """Generate final report."""
        logger.info("\n" + "=" * 70)
        logger.info("Final Report - CUA Campaign")
        logger.info("=" * 70)
        logger.info(f"Jobs discovered: {self.stats['discovered']}")
        logger.info(f"Applications attempted: {self.stats['attempted']}")
        logger.info(f"Verified successful: {self.stats['verified_success']} ✅")
        logger.info(f"Failed: {self.stats['failed']}")
        
        if self.stats['attempted'] > 0:
            success_rate = (self.stats['verified_success'] / self.stats['attempted']) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")
        
        # Show verified applications
        verified = [r for r in self.results if r['result'].get('verified')]
        if verified:
            logger.info("\nVerified Applications:")
            for r in verified:
                job = r['job']
                logger.info(f"  ✅ {job['title'][:50]} @ {job['company']}")
                conf = r['result'].get('confirmation_id')
                if conf:
                    logger.info(f"     Confirmation: {conf}")
        
        # Save report
        report = {
            'campaign_type': 'CUA (Computer Use Agent)',
            'stats': self.stats,
            'all_results': self.results,
            'timestamp': datetime.now().isoformat()
        }
        
        path = self.output_dir / f'REPORT_CUA_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\nReport saved: {path}")


# Run
if __name__ == "__main__":
    campaign = CUACampaign(
        profile_path='campaigns/profiles/kevin_beltran.yaml',
        resume_path='Test Resumes/Kevin_Beltran_Resume.pdf',
        target=5,
        max_steps_per_job=20
    )
    
    asyncio.run(campaign.run())
