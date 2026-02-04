#!/usr/bin/env python3
"""
MATT EDWARDS - 1000 PRODUCTION CAMPAIGN V2
Features:
- Session pooling for efficiency
- Job URL validation
- Real vs Synthetic mode toggle
- Auto-submit vs Review mode toggle
- Retry logic with exponential backoff
- Comprehensive logging
"""

import sys
import os
import asyncio
import json
import time
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

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


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

class Config:
    """Production configuration constants"""
    # Session Management
    MAX_CONCURRENT_SESSIONS = 5
    SESSION_REUSE = True
    SESSION_IDLE_TIMEOUT = 300  # 5 minutes
    
    # Rate Limiting
    RATE_LIMIT_DELAY_MIN = 2
    RATE_LIMIT_DELAY_MAX = 5
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2
    
    # Timeouts
    PAGE_TIMEOUT = 30000
    NAVIGATION_TIMEOUT = 60000
    
    # Validation
    VALIDATE_URLS = True
    REQUIRED_URL_PATTERNS = ['greenhouse', 'lever', 'workday', 'ashby', 
                            'indeed.com/viewjob', 'linkedin.com/jobs/view']
    
    # Output
    PROGRESS_SAVE_INTERVAL = 25
    SCREENSHOT_DIR = "campaigns/output/matt_edwards_v2/screenshots"


# ============================================================================
# MODE ENUMS
# ============================================================================

class ApplicationMode(Enum):
    """Real vs Synthetic (Test) Mode"""
    REAL = "real"
    SYNTHETIC = "synthetic"


class SubmitMode(Enum):
    """Auto-submit vs Review Mode"""
    AUTO_SUBMIT = "auto_submit"
    REVIEW = "review"


@dataclass
class CampaignConfig:
    """Campaign configuration"""
    application_mode: ApplicationMode = ApplicationMode.REAL
    submit_mode: SubmitMode = ApplicationMode.AUTO_SUBMIT
    max_jobs: int = 1000
    concurrent_sessions: int = Config.MAX_CONCURRENT_SESSIONS
    enable_validation: bool = True
    enable_retry: bool = True
    enable_screenshots: bool = True


# ============================================================================
# MATT'S PROFILE
# ============================================================================

MATT_PROFILE = {
    "first_name": "Matt",
    "last_name": "Edwards",
    "email": "edwardsdmatt@gmail.com",
    "phone": "404-680-8472",
    "location": "Atlanta, GA",
    "linkedin_url": "https://linkedin.com/in/matt-edwards-",
    "portfolio_url": None,
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
        "start_date": "2 weeks notice",
        "clearance": "Secret Security Clearance (Active)"
    }
}


# ============================================================================
# SESSION POOL
# ============================================================================

class SessionPool:
    """Manages browser session pooling for efficiency"""
    
    def __init__(self, browser_manager: StealthBrowserManager, max_size: int = 5):
        self.browser_manager = browser_manager
        self.max_size = max_size
        self.sessions: Dict[str, dict] = {}
        self.available: asyncio.Queue = asyncio.Queue()
        self.lock = asyncio.Lock()
        self._session_counter = 0
        
    async def initialize(self):
        """Pre-create initial sessions"""
        print(f"  Creating {self.max_size} browser sessions...")
        for i in range(self.max_size):
            try:
                session = await self._create_session()
                if session:
                    await self.available.put(session['session_id'])
                    print(f"    ✅ Session {i+1}/{self.max_size} ready")
            except Exception as e:
                print(f"    ⚠️  Session {i+1} failed: {e}")
        print(f"  ✅ Session pool initialized with {self.available.qsize()} sessions")
    
    async def _create_session(self) -> Optional[dict]:
        """Create a new browser session"""
        self._session_counter += 1
        session_id = f"session_{self._session_counter}_{int(time.time())}"
        
        try:
            browser_session = await self.browser_manager.create_stealth_session(
                platform="generic",
                use_proxy=True,
                force_local=False
            )
            
            session_data = {
                'session_id': browser_session.session_id,
                'browser_session': browser_session,
                'page': browser_session.page,
                'created_at': time.time(),
                'use_count': 0
            }
            
            self.sessions[browser_session.session_id] = session_data
            return session_data
            
        except Exception as e:
            # Try local fallback
            try:
                browser_session = await self.browser_manager.create_stealth_session(
                    platform="generic",
                    use_proxy=False,
                    force_local=True
                )
                
                session_data = {
                    'session_id': browser_session.session_id,
                    'browser_session': browser_session,
                    'page': browser_session.page,
                    'created_at': time.time(),
                    'use_count': 0,
                    'is_local': True
                }
                
                self.sessions[browser_session.session_id] = session_data
                return session_data
                
            except Exception as e2:
                print(f"    ❌ Both BrowserBase and local failed: {e2}")
                return None
    
    async def acquire(self, timeout: float = 30.0) -> Optional[dict]:
        """Acquire a session from the pool"""
        try:
            session_id = await asyncio.wait_for(
                self.available.get(), 
                timeout=timeout
            )
            
            session = self.sessions.get(session_id)
            if session:
                session['use_count'] += 1
                session['last_used'] = time.time()
                return session
            
            # Session not found, create new
            return await self._create_session()
            
        except asyncio.TimeoutError:
            # Pool exhausted, create emergency session
            return await self._create_session()
    
    async def release(self, session: dict):
        """Release a session back to the pool"""
        if session and session.get('session_id'):
            # Check if session is still healthy
            age = time.time() - session.get('created_at', 0)
            if age > Config.SESSION_IDLE_TIMEOUT:
                # Session too old, close it
                await self._close_session(session)
                # Create replacement
                new_session = await self._create_session()
                if new_session:
                    await self.available.put(new_session['session_id'])
            else:
                # Return to pool
                await self.available.put(session['session_id'])
    
    async def _close_session(self, session: dict):
        """Close a browser session"""
        try:
            await self.browser_manager.close_session(session['session_id'])
        except:
            pass
        self.sessions.pop(session['session_id'], None)
    
    async def cleanup(self):
        """Close all sessions"""
        print("\n  🧹 Cleaning up session pool...")
        for session in list(self.sessions.values()):
            await self._close_session(session)
        print(f"  ✅ Closed {len(self.sessions)} sessions")


# ============================================================================
# URL VALIDATOR
# ============================================================================

class URLValidator:
    """Validates job URLs before processing"""
    
    VALID_PATTERNS = [
        # Direct application URLs
        (r'boards\.greenhouse\.io/[^/]+/jobs/\d+', 'greenhouse'),
        (r'jobs\.lever\.co/[^/]+/[^/]+', 'lever'),
        (r'[^/]+\.myworkdayjobs\.com/[^/]+/job/[^/]+', 'workday'),
        (r'jobs\.ashbyhq\.com/[^/]+/[^/]+', 'ashby'),
        # Job board URLs
        (r'indeed\.com/viewjob\?jk=[a-f0-9]+', 'indeed'),
        (r'linkedin\.com/jobs/view/\d+', 'linkedin'),
        (r'ziprecruiter\.com/job/[a-f0-9]+', 'ziprecruiter'),
    ]
    
    INVALID_PATTERNS = [
        # Generic career pages (not direct jobs)
        r'careers\.[a-z]+\.com/?$',
        r'jobs\.[a-z]+\.com/?$',
        r'[a-z]+\.com/careers/?$',
        r'[a-z]+\.com/jobs/?$',
        r'indeed\.com/jobs\?',
        r'linkedin\.com/jobs/search',
    ]
    
    @classmethod
    def validate(cls, url: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate a job URL.
        Returns: (is_valid, reason, platform)
        """
        if not url or not url.startswith('http'):
            return False, "Invalid URL format", None
        
        url_lower = url.lower()
        
        # Check for invalid patterns
        for pattern in cls.INVALID_PATTERNS:
            import re
            if re.search(pattern, url_lower):
                return False, "Generic career page (not direct job posting)", None
        
        # Check for valid patterns
        for pattern, platform in cls.VALID_PATTERNS:
            import re
            if re.search(pattern, url_lower):
                return True, "Valid direct job URL", platform
        
        # Unknown but potentially valid
        return True, "Unknown platform (will attempt generic handling)", "generic"


# ============================================================================
# CAMPAIGN RUNNER
# ============================================================================

class MattProductionCampaignV2:
    """Production campaign runner with all improvements"""
    
    def __init__(self, config: CampaignConfig):
        self.config = config
        self.results: List[dict] = []
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "invalid_url": 0,
            "external": 0,
            "pending_review": 0,
            "retried": 0
        }
        self.browser_manager: Optional[StealthBrowserManager] = None
        self.session_pool: Optional[SessionPool] = None
        self.output_dir = Path("campaigns/output/matt_edwards_v2")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    async def initialize(self):
        """Initialize browser and session pool"""
        print("\n🌐 Initializing browser infrastructure...")
        self.browser_manager = StealthBrowserManager(prefer_local=False)
        await self.browser_manager.initialize()
        
        # Initialize session pool
        self.session_pool = SessionPool(
            self.browser_manager,
            max_size=self.config.concurrent_sessions
        )
        await self.session_pool.initialize()
        
        print("✅ Infrastructure ready\n")
    
    async def apply_to_job(self, job: dict, attempt: int = 0) -> dict:
        """Apply to a single job with retry logic"""
        url = job.get("url", "")
        job_id = job.get("id", f"job_{int(time.time())}")
        
        # Validate URL if enabled
        if self.config.enable_validation:
            is_valid, reason, platform = URLValidator.validate(url)
            if not is_valid:
                self.stats["invalid_url"] += 1
                return {
                    "status": "invalid_url",
                    "error": reason,
                    "platform": None
                }
            job['detected_platform'] = platform
        
        session = None
        try:
            # Acquire session from pool
            session = await self.session_pool.acquire(timeout=30)
            if not session:
                raise Exception("Could not acquire browser session")
            
            page = session['page']
            
            # Navigate to job
            await page.goto(url, timeout=Config.NAVIGATION_TIMEOUT)
            await asyncio.sleep(random.uniform(2, 4))
            
            # Get current state
            current_url = page.url
            content = await page.content()
            
            # SYNTHETIC MODE: Just check if we can access the page
            if self.config.application_mode == ApplicationMode.SYNTHETIC:
                return {
                    "status": "synthetic_success",
                    "message": "Test mode - page accessible",
                    "platform": job.get('detected_platform', 'unknown'),
                    "url": current_url
                }
            
            # REAL MODE: Attempt application
            # Check for apply buttons
            apply_selectors = [
                'button:has-text("Apply")',
                'a:has-text("Apply")',
                '[data-testid="apply-button"]',
                '.apply-button',
                'button:has-text("Apply now")',
                '.posting-btn-apply',  # Lever
                '[href="#application_form"]',  # Greenhouse
            ]
            
            apply_clicked = False
            for selector in apply_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(timeout=5000)
                        apply_clicked = True
                        await asyncio.sleep(2)
                        break
                except:
                    continue
            
            if not apply_clicked:
                # Check if already on application form
                form_indicators = ['input[type="file"]', 'input[name="email"]', 
                                  'textarea[name="coverLetter"]']
                form_present = False
                for indicator in form_indicators:
                    try:
                        if await page.locator(indicator).count() > 0:
                            form_present = True
                            break
                    except:
                        continue
                
                if not form_present:
                    return {
                        "status": "external",
                        "error": "No apply button or form found",
                        "url": current_url
                    }
            
            # Fill form fields
            fields_filled = await self._fill_form_fields(page)
            
            # REVIEW MODE: Stop here for manual review
            if self.config.submit_mode == SubmitMode.REVIEW:
                return {
                    "status": "pending_review",
                    "message": f"Form filled ({fields_filled} fields). Ready for manual review.",
                    "fields_filled": fields_filled,
                    "url": current_url
                }
            
            # AUTO-SUBMIT MODE: Submit the form
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Submit")',
                'button:has-text("Submit application")',
                'button:has-text("Apply")',
                '.postings-btn-submit',  # Lever
                '#submit_app',  # Greenhouse
            ]
            
            submitted = False
            for selector in submit_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(timeout=10000)
                        submitted = True
                        await asyncio.sleep(3)
                        break
                except:
                    continue
            
            if not submitted:
                return {
                    "status": "filled",
                    "message": f"Form filled ({fields_filled} fields) but could not submit",
                    "fields_filled": fields_filled
                }
            
            # Validate submission
            final_content = await page.content()
            success_indicators = [
                "thank you", "submitted", "success", "received",
                "application complete", "confirmation", "we've received"
            ]
            found_success = any(s in final_content.lower() for s in success_indicators)
            
            if found_success:
                return {
                    "status": "success",
                    "message": "Application submitted successfully",
                    "fields_filled": fields_filled,
                    "url": page.url
                }
            else:
                return {
                    "status": "submitted",
                    "message": "Form submitted but success unclear",
                    "fields_filled": fields_filled,
                    "url": page.url
                }
                
        except Exception as e:
            error_msg = str(e)
            
            # Retry on specific errors
            if self.config.enable_retry and attempt < Config.MAX_RETRIES - 1:
                if any(err in error_msg.lower() for err in ['timeout', 'network', 'navigation']):
                    self.stats["retried"] += 1
                    wait_time = Config.RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                    return await self.apply_to_job(job, attempt + 1)
            
            return {
                "status": "error",
                "error": error_msg[:100],
                "attempt": attempt + 1
            }
        
        finally:
            if session:
                await self.session_pool.release(session)
    
    async def _fill_form_fields(self, page) -> int:
        """Fill standard form fields"""
        fields_filled = 0
        
        field_mappings = [
            (['input[name="firstName"]', 'input[name="first_name"]', 
              'input[placeholder*="First" i]'], MATT_PROFILE["first_name"]),
            (['input[name="lastName"]', 'input[name="last_name"]', 
              'input[placeholder*="Last" i]'], MATT_PROFILE["last_name"]),
            (['input[name="email"]', 'input[type="email"]'], MATT_PROFILE["email"]),
            (['input[name="phone"]', 'input[type="tel"]'], MATT_PROFILE["phone"]),
        ]
        
        for selectors, value in field_mappings:
            for selector in selectors:
                try:
                    field = page.locator(selector).first
                    if await field.count() > 0 and await field.is_visible():
                        await field.fill(value)
                        await asyncio.sleep(0.5)
                        fields_filled += 1
                        break
                except:
                    continue
        
        return fields_filled
    
    async def run_campaign(self, jobs: List[dict]):
        """Run the full campaign"""
        await self.initialize()
        
        total = min(len(jobs), self.config.max_jobs)
        semaphore = asyncio.Semaphore(self.config.concurrent_sessions)
        start_time = datetime.now()
        
        # Print campaign header
        print("="*80)
        print("🚀 MATT EDWARDS - 1000 PRODUCTION CAMPAIGN V2")
        print("="*80)
        print(f"Mode: {'🟢 REAL' if self.config.application_mode == ApplicationMode.REAL else '🔵 SYNTHETIC (TEST)'}")
        print(f"Submit: {'🟢 AUTO-SUBMIT' if self.config.submit_mode == SubmitMode.AUTO_SUBMIT else '🟡 REVIEW MODE'}")
        print(f"Candidate: {MATT_PROFILE['first_name']} {MATT_PROFILE['last_name']}")
        print(f"Email: {MATT_PROFILE['email']}")
        print(f"Clearance: {MATT_PROFILE['clearance']}")
        print(f"Total Jobs: {total}")
        print(f"Concurrent: {self.config.concurrent_sessions}")
        print(f"Started: {start_time.strftime('%H:%M:%S')}")
        print("="*80 + "\n")
        
        async def process_job(job, index):
            async with semaphore:
                # Rate limiting
                delay = random.uniform(Config.RATE_LIMIT_DELAY_MIN, Config.RATE_LIMIT_DELAY_MAX)
                await asyncio.sleep(delay)
                
                company = job.get("company", "Unknown")[:25]
                title = job.get("title", "Unknown")[:30]
                
                print(f"[{index+1:4d}/{total}] {title:30} @ {company:25} ... ", end="", flush=True)
                
                result = await self.apply_to_job(job)
                
                self.results.append({
                    "job_id": job.get("id"),
                    "company": job.get("company"),
                    "title": job.get("title"),
                    "url": job.get("url"),
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                })
                
                self.stats["total"] += 1
                
                # Print result
                if result["status"] == "success":
                    self.stats["success"] += 1
                    print("✅ SUCCESS")
                elif result["status"] == "synthetic_success":
                    self.stats["success"] += 1
                    print("✅ TEST PASSED")
                elif result["status"] == "pending_review":
                    self.stats["pending_review"] += 1
                    print("⏸️  REVIEW")
                elif result["status"] == "external":
                    self.stats["external"] += 1
                    print("↪️  EXTERNAL")
                elif result["status"] == "invalid_url":
                    print(f"⚠️  INVALID")
                else:
                    self.stats["failed"] += 1
                    error = result.get("error", "Unknown")[:25]
                    print(f"❌ {error}")
                
                # Progress update
                if (index + 1) % Config.PROGRESS_SAVE_INTERVAL == 0:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    success_rate = self.stats["success"] / (index + 1) * 100
                    print(f"\n{'='*80}")
                    print(f"📊 Progress: {index+1}/{total} | Success: {self.stats['success']} | "
                          f"Rate: {success_rate:.1f}% | Time: {elapsed:.1f}min")
                    print(f"{'='*80}\n")
                    self._save_progress()
        
        # Process all jobs
        tasks = [process_job(job, i) for i, job in enumerate(jobs[:total])]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60
        
        # Cleanup
        await self.session_pool.cleanup()
        
        # Generate report
        report = self._generate_report(total, duration, start_time, end_time)
        return report
    
    def _save_progress(self):
        """Save intermediate progress"""
        progress_file = self.output_dir / f"progress_{datetime.now().strftime('%H%M%S')}.json"
        with open(progress_file, 'w') as f:
            json.dump({
                "stats": self.stats,
                "results": self.results[-Config.PROGRESS_SAVE_INTERVAL:]
            }, f, indent=2)
    
    def _generate_report(self, total: int, duration: float, start_time: datetime, end_time: datetime):
        """Generate final campaign report"""
        report = {
            "campaign_id": f"matt_v2_{start_time.strftime('%Y%m%d_%H%M')}",
            "config": {
                "application_mode": self.config.application_mode.value,
                "submit_mode": self.config.submit_mode.value,
                "max_jobs": self.config.max_jobs,
                "concurrent_sessions": self.config.concurrent_sessions
            },
            "candidate": {
                "name": f"{MATT_PROFILE['first_name']} {MATT_PROFILE['last_name']}",
                "email": MATT_PROFILE['email'],
                "clearance": MATT_PROFILE['clearance']
            },
            "stats": self.stats,
            "total_jobs": total,
            "success_rate": (self.stats["success"] / total * 100) if total > 0 else 0,
            "duration_minutes": duration,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "results": self.results
        }
        
        report_file = self.output_dir / f"FINAL_REPORT_{start_time.strftime('%H%M')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Print summary
        print("\n" + "="*80)
        print("✅ CAMPAIGN COMPLETE")
        print("="*80)
        print(f"Mode: {self.config.application_mode.value.upper()}")
        print(f"Submit: {self.config.submit_mode.value.upper()}")
        print(f"\n📊 RESULTS:")
        print(f"   Total Jobs: {total}")
        print(f"   ✅ Success: {self.stats['success']}")
        print(f"   ⏸️  Review Pending: {self.stats['pending_review']}")
        print(f"   ↪️  External: {self.stats['external']}")
        print(f"   ⚠️  Invalid URLs: {self.stats['invalid_url']}")
        print(f"   ❌ Failed: {self.stats['failed']}")
        print(f"   🔄 Retried: {self.stats['retried']}")
        print(f"\n📈 Success Rate: {report['success_rate']:.1f}%")
        print(f"⏱️  Duration: {duration:.1f} minutes")
        print(f"💾 Report: {report_file}")
        print("="*80)
        
        return report


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main entry point with configuration"""
    
    # Parse command line arguments for toggles
    import argparse
    parser = argparse.ArgumentParser(description='Matt Edwards 1000 Job Campaign V2')
    parser.add_argument('--mode', choices=['real', 'synthetic'], default='real',
                       help='Application mode: real or synthetic (test)')
    parser.add_argument('--submit', choices=['auto', 'review'], default='auto',
                       help='Submit mode: auto-submit or review')
    parser.add_argument('--max-jobs', type=int, default=1000,
                       help='Maximum jobs to process')
    parser.add_argument('--concurrent', type=int, default=5,
                       help='Number of concurrent sessions')
    args = parser.parse_args()
    
    # Create configuration
    config = CampaignConfig(
        application_mode=ApplicationMode.REAL if args.mode == 'real' else ApplicationMode.SYNTHETIC,
        submit_mode=SubmitMode.AUTO_SUBMIT if args.submit == 'auto' else SubmitMode.REVIEW,
        max_jobs=args.max_jobs,
        concurrent_sessions=args.concurrent
    )
    
    # Load jobs
    jobs_file = Path("campaigns/matt_edwards_1000_jobs.json")
    if not jobs_file.exists():
        print("❌ Jobs file not found")
        return
    
    with open(jobs_file) as f:
        data = json.load(f)
        jobs = data.get("jobs", [])
    
    print(f"📋 Loaded {len(jobs)} jobs")
    
    # Show confirmation for real mode
    if config.application_mode == ApplicationMode.REAL:
        print("\n" + "⚠️ "*40)
        print("⚠️  REAL APPLICATION MODE IS ENABLED")
        print("⚠️  This will ACTUALLY submit job applications!")
        if config.submit_mode == SubmitMode.AUTO_SUBMIT:
            print("⚠️  AUTO-SUBMIT: Applications will be submitted automatically!")
        else:
            print("⚠️  REVIEW MODE: Applications will stop for manual review")
        print("⚠️ "*40)
        print("\nStarting in 5 seconds... (Ctrl+C to cancel)")
        await asyncio.sleep(5)
    else:
        print("\n🔵 SYNTHETIC MODE: Test run only (no actual submissions)")
    
    # Run campaign
    campaign = MattProductionCampaignV2(config)
    report = await campaign.run_campaign(jobs)
    
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
