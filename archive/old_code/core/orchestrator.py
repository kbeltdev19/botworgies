"""
Job Application Orchestrator - Ties all components together for 1000+ apps/day.

Usage:
    orchestrator = JobOrchestrator(config)
    await orchestrator.start()  # Runs continuously
    await orchestrator.stop()   # Graceful shutdown
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from .browser_pool import BrowserPool
from .browserbase_pool import BrowserBasePool, create_browserbase_pool
from .job_discovery import JobDiscoveryService, JobQueue
from .captcha_solver import CaptchaSolver
from .proxy_manager import ProxyManager
from .platform_balancer import PlatformBalancer
from .session_manager import SessionManager
from .error_handler import ErrorHandler, ErrorCategory

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the job orchestrator."""
    # Throughput - BrowserBase supports 100 concurrent!
    max_concurrent_applications: int = 100
    target_applications_per_day: int = 5000
    use_browserbase: bool = True  # Use cloud browsers
    
    # Timing
    min_delay_between_apps: float = 30.0
    max_delay_between_apps: float = 90.0
    job_discovery_interval: int = 1800  # 30 minutes
    
    # Limits
    max_retries_per_job: int = 3
    max_daily_failures: int = 100
    
    # Features (BrowserBase handles CAPTCHA + proxies natively)
    enable_captcha_solving: bool = False  # BrowserBase does this
    enable_proxy_rotation: bool = False   # BrowserBase does this
    enable_session_rotation: bool = True
    
    # Paths
    database_path: str = "data/orchestrator.db"
    resume_path: str = "data/resume.pdf"
    
    # Candidate info
    candidate_name: str = ""
    candidate_email: str = ""
    candidate_linkedin: str = ""


class JobOrchestrator:
    """
    Main orchestrator for high-volume job applications.
    
    Coordinates:
    - Browser pool for parallel applications
    - Job discovery for continuous job supply
    - Captcha solving for uninterrupted flow
    - Proxy rotation to avoid bans
    - Platform balancing for quota management
    - Session management for authentication
    - Error handling for resilience
    """
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        
        # Initialize components - use BrowserBase for 100 concurrent sessions
        if config.use_browserbase:
            self.browser_pool = BrowserBasePool(max_sessions=config.max_concurrent_applications)
        else:
            self.browser_pool = BrowserPool(max_browsers=config.max_concurrent_applications)
        self.job_queue = JobQueue(config.database_path)
        self.job_discovery = JobDiscoveryService(
            job_queue=self.job_queue,
            interval=config.job_discovery_interval
        )
        self.captcha_solver = CaptchaSolver() if config.enable_captcha_solving else None
        self.proxy_manager = ProxyManager() if config.enable_proxy_rotation else None
        self.platform_balancer = PlatformBalancer(config.database_path)
        self.session_manager = SessionManager(config.database_path)
        self.error_handler = ErrorHandler()
        
        # State
        self._running = False
        self._workers: list = []
        self._stats = {
            "started_at": None,
            "applications_submitted": 0,
            "applications_failed": 0,
            "captchas_solved": 0,
            "sessions_rotated": 0,
        }
    
    async def start(self):
        """Start the orchestrator and all workers."""
        if self._running:
            logger.warning("Orchestrator already running")
            return
        
        self._running = True
        self._stats["started_at"] = datetime.now()
        
        logger.info("Starting Job Orchestrator...")
        
        # Initialize components
        await self.browser_pool.initialize()
        await self.job_discovery.start()
        
        # Start worker tasks
        for i in range(self.config.max_concurrent_applications):
            worker = asyncio.create_task(self._application_worker(i))
            self._workers.append(worker)
        
        logger.info(f"Started {len(self._workers)} application workers")
        
        # Start stats reporter
        self._stats_task = asyncio.create_task(self._stats_reporter())
        
        # Wait for workers
        await asyncio.gather(*self._workers, return_exceptions=True)
    
    async def stop(self):
        """Stop the orchestrator gracefully."""
        logger.info("Stopping Job Orchestrator...")
        self._running = False
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        
        # Stop components
        await self.job_discovery.stop()
        await self.browser_pool.shutdown()
        
        logger.info("Orchestrator stopped")
    
    async def _application_worker(self, worker_id: int):
        """Worker that processes job applications."""
        import random
        
        logger.info(f"Worker {worker_id} started")
        
        while self._running:
            try:
                # Check daily failure limit
                if self._stats["applications_failed"] >= self.config.max_daily_failures:
                    logger.warning("Daily failure limit reached, pausing...")
                    await asyncio.sleep(3600)  # Wait 1 hour
                    continue
                
                # Get next platform with quota
                platform = self.platform_balancer.get_next_platform()
                if not platform:
                    logger.info("All platforms at quota, waiting...")
                    await asyncio.sleep(300)  # Wait 5 minutes
                    continue
                
                # Get next job for platform
                job = await self.job_queue.get_next(platform)
                if not job:
                    logger.debug(f"No jobs for {platform}, waiting...")
                    await asyncio.sleep(60)
                    continue
                
                # Apply to job
                success = await self._apply_to_job(worker_id, job, platform)
                
                if success:
                    self._stats["applications_submitted"] += 1
                    self.platform_balancer.track_application(platform, job["id"])
                else:
                    self._stats["applications_failed"] += 1
                
                # Human-like delay
                delay = random.uniform(
                    self.config.min_delay_between_apps,
                    self.config.max_delay_between_apps
                )
                await asyncio.sleep(delay)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(10)
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _apply_to_job(self, worker_id: int, job: Dict, platform: str) -> bool:
        """Apply to a single job with all features enabled."""
        browser = None
        
        try:
            # Acquire browser
            browser = await self.browser_pool.acquire()
            
            # Get proxy if enabled
            proxy = None
            if self.proxy_manager:
                proxy = self.proxy_manager.get_proxy()
            
            # Get session if available
            session = None
            if self.session_manager:
                session = await self.session_manager.get_session(platform)
            
            # Create browser context with proxy
            context_options = {}
            if proxy:
                context_options = self.proxy_manager.get_playwright_context_options(proxy)
            
            context = await browser.new_context(**context_options)
            page = await context.new_page()
            
            # Set session cookies if available
            if session and session.get("cookies"):
                await context.add_cookies(session["cookies"])
            
            # Navigate to job
            await page.goto(job["url"], timeout=30000)
            
            # Check for CAPTCHA
            if self.captcha_solver:
                captcha_detected = await self.captcha_solver.detect_captcha(page)
                if captcha_detected:
                    logger.info(f"[Worker {worker_id}] Solving CAPTCHA...")
                    solved = await self.captcha_solver.solve(page)
                    if solved:
                        self._stats["captchas_solved"] += 1
                    else:
                        raise Exception("CAPTCHA solve failed")
            
            # Fill application form
            filled = await self._fill_application_form(page, job)
            
            if filled:
                # Submit
                submit_btn = page.locator('button[type="submit"], input[type="submit"]')
                if await submit_btn.count() > 0:
                    await submit_btn.click()
                    await asyncio.sleep(3)
                
                logger.info(f"[Worker {worker_id}] ✅ Applied: {job['title']} @ {job['company']}")
                
                # Mark proxy as successful
                if proxy:
                    self.proxy_manager.mark_success(proxy)
                
                return True
            else:
                logger.warning(f"[Worker {worker_id}] ❌ Could not fill form: {job['title']}")
                return False
                
        except Exception as e:
            # Handle error
            action = self.error_handler.handle_error(e, {"job": job, "platform": platform})
            
            if action == "RETRY" and job.get("retries", 0) < self.config.max_retries_per_job:
                job["retries"] = job.get("retries", 0) + 1
                await self.job_queue.requeue(job)
            
            # Mark proxy as failed
            if self.proxy_manager and proxy:
                self.proxy_manager.mark_failed(proxy)
            
            logger.error(f"[Worker {worker_id}] Error applying: {e}")
            return False
            
        finally:
            if browser:
                await self.browser_pool.release(browser)
    
    async def _fill_application_form(self, page, job: Dict) -> bool:
        """Fill out the application form."""
        filled = 0
        config = self.config
        
        # First name
        fn = page.locator('#first_name, input[name*="first_name"]')
        if await fn.count() > 0:
            name_parts = config.candidate_name.split()
            await fn.first.fill(name_parts[0] if name_parts else "")
            filled += 1
        
        # Last name  
        ln = page.locator('#last_name, input[name*="last_name"]')
        if await ln.count() > 0:
            name_parts = config.candidate_name.split()
            await ln.first.fill(name_parts[-1] if len(name_parts) > 1 else "")
            filled += 1
        
        # Email
        email = page.locator('#email, input[type="email"]')
        if await email.count() > 0:
            await email.first.fill(config.candidate_email)
            filled += 1
        
        # LinkedIn
        linkedin = page.locator('input[name*="linkedin"], input[id*="linkedin"]')
        if await linkedin.count() > 0:
            await linkedin.first.fill(config.candidate_linkedin)
            filled += 1
        
        # Resume
        resume_input = page.locator('input[type="file"]')
        if await resume_input.count() > 0 and config.resume_path:
            try:
                await resume_input.first.set_input_files(config.resume_path)
                filled += 1
            except:
                pass
        
        return filled >= 3  # At least name and email
    
    async def _stats_reporter(self):
        """Periodically report statistics."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                elapsed = datetime.now() - self._stats["started_at"]
                rate = self._stats["applications_submitted"] / (elapsed.total_seconds() / 3600)
                
                logger.info(f"""
=== Orchestrator Stats ===
Running: {elapsed}
Applications: {self._stats['applications_submitted']} submitted, {self._stats['applications_failed']} failed
Rate: {rate:.1f}/hour (target: {self.config.target_applications_per_day / 24:.1f}/hour)
CAPTCHAs solved: {self._stats['captchas_solved']}
Queue size: {await self.job_queue.size()}
==========================
""")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stats reporter error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        return {
            **self._stats,
            "running": self._running,
            "workers": len(self._workers),
            "queue_size": self.job_queue.size() if hasattr(self.job_queue, 'size') else 0,
        }


async def run_orchestrator(config: OrchestratorConfig):
    """Run the orchestrator until stopped."""
    orchestrator = JobOrchestrator(config)
    
    try:
        await orchestrator.start()
    except KeyboardInterrupt:
        await orchestrator.stop()
    
    return orchestrator.get_stats()


# Example usage
if __name__ == "__main__":
    config = OrchestratorConfig(
        max_concurrent_applications=10,
        target_applications_per_day=1000,
        candidate_name="Matt Edwards",
        candidate_email="edwardsdmatt@gmail.com",
        candidate_linkedin="https://www.linkedin.com/in/matt-edwards-/",
        resume_path="data/matt_edwards_resume.pdf",
    )
    
    asyncio.run(run_orchestrator(config))
