"""
ATS Router - Detects ATS type and routes to appropriate handler
"""

import asyncio
from typing import Optional, List, Dict
import aiohttp
from .models import ATSPlatform, ApplicationResult, UserProfile
from .browserbase_manager import BrowserBaseManager
from .generic_mapper import GenericFieldMapper

# Import all handlers
from .handlers.workday import WorkdayHandler
from .handlers.taleo import TaleoHandler
from .handlers.icims import iCIMSHandler
from .handlers.successfactors import SuccessFactorsHandler
from .handlers.adp import ADPHandler
from .handlers.angellist import AngelListHandler, GreenhouseHandler
from .handlers.dice import DiceHandler
from .handlers.indeed import IndeedHandler
from .handlers.linkedin import LinkedInHandler


class ATSRouter:
    """
    Main router for ATS automation.
    Detects ATS platform from URL and routes to correct handler.
    """
    
    def __init__(self, user_profile: UserProfile, ai_client=None):
        self.profile = user_profile
        self.ai_client = ai_client
        self.browser = BrowserBaseManager()
        
        # Initialize all handlers
        self.handlers = [
            WorkdayHandler(self.browser, user_profile, ai_client),
            TaleoHandler(self.browser, user_profile, ai_client),
            iCIMSHandler(self.browser, user_profile, ai_client),
            SuccessFactorsHandler(self.browser, user_profile, ai_client),
            ADPHandler(self.browser, user_profile, ai_client),
            AngelListHandler(self.browser, user_profile, ai_client),
            GreenhouseHandler(self.browser, user_profile, ai_client),
            DiceHandler(self.browser, user_profile, ai_client),
            IndeedHandler(self.browser, user_profile, ai_client),
            LinkedInHandler(self.browser, user_profile, ai_client),
        ]
    
    async def detect_platform(self, url: str) -> ATSPlatform:
        """
        Detect which ATS platform a job URL uses
        
        Tries URL matching first, then content-based detection
        """
        url_lower = url.lower()
        
        # URL-based detection (fast)
        for handler in self.handlers:
            if await handler.can_handle(url):
                return handler.PLATFORM
        
        # Content-based detection (slower, requires fetch)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        content = (await resp.text()).lower()
                        
                        if 'workday' in content:
                            return ATSPlatform.WORKDAY
                        elif 'taleo' in content:
                            return ATSPlatform.TALEO
                        elif 'icims' in content:
                            return ATSPlatform.ICIMS
                        elif 'successfactors' in content or 'sap' in content:
                            return ATSPlatform.SUCCESSFACTORS
                        elif 'adp' in content:
                            return ATSPlatform.ADP
                        elif 'greenhouse' in content:
                            return ATSPlatform.GREENHOUSE
                        elif 'dice.com' in url_lower:
                            return ATSPlatform.DICE
        except Exception as e:
            print(f"Content detection error: {e}")
        
        return ATSPlatform.UNKNOWN
    
    async def apply(self, job_url: str) -> ApplicationResult:
        """
        Apply to a job - auto-detects platform and routes to handler
        """
        # Detect platform
        platform = await self.detect_platform(job_url)
        print(f"Detected platform: {platform.value}")
        
        # Find appropriate handler
        for handler in self.handlers:
            if await handler.can_handle(job_url):
                print(f"Using handler: {handler.__class__.__name__}")
                return await handler.apply(job_url)
        
        # Unknown platform - try generic approach
        print("No specific handler found, using generic approach")
        return await self._generic_apply(job_url)
    
    async def _generic_apply(self, job_url: str) -> ApplicationResult:
        """
        Fallback generic application method
        
        Uses field mapper to attempt filling any form
        """
        session = await self.browser.create_stealth_session("generic")
        page = session["page"]
        session_id = session["session_id"]
        
        try:
            await page.goto(job_url, wait_until='networkidle')
            await asyncio.sleep(3)
            
            # Check for captcha
            if not await self.browser.solve_captcha_if_present(session_id, page):
                return ApplicationResult(
                    success=False,
                    platform=ATSPlatform.UNKNOWN,
                    job_id=job_url,
                    job_url=job_url,
                    status='captcha_blocked',
                    session_id=session_id
                )
            
            # Use generic mapper
            mapper = GenericFieldMapper(page, self.profile, self.ai_client)
            mappings = await mapper.analyze_page()
            
            # Safety check: only submit if we have high confidence on required fields
            required = [m for m in mappings if m.required]
            high_conf = [m for m in required if m.confidence > 0.7]
            
            if required and len(high_conf) / len(required) < 0.7:
                return ApplicationResult(
                    success=False,
                    platform=ATSPlatform.UNKNOWN,
                    job_id=job_url,
                    job_url=job_url,
                    status='low_confidence',
                    error_message=f'Only {len(high_conf)}/{len(required)} required fields confident',
                    total_fields=len(mappings),
                    fields_filled=0,
                    session_id=session_id
                )
            
            # Fill fields
            filled_count = await mapper.fill_all_fields(mappings)
            
            # Try to find submit button
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Submit")',
                'button:has-text("Apply")',
                'input[value="Submit"]',
                'input[value="Apply"]'
            ]
            
            for selector in submit_selectors:
                try:
                    submit_btn = await page.query_selector(selector)
                    if submit_btn and await submit_btn.is_visible():
                        await submit_btn.click()
                        await asyncio.sleep(3)
                        
                        return ApplicationResult(
                            success=True,
                            platform=ATSPlatform.UNKNOWN,
                            job_id=job_url,
                            job_url=job_url,
                            status='submitted_generic',
                            message='Submitted using generic handler',
                            total_fields=len(mappings),
                            fields_filled=filled_count,
                            session_id=session_id
                        )
                except:
                    continue
            
            return ApplicationResult(
                success=False,
                platform=ATSPlatform.UNKNOWN,
                job_id=job_url,
                job_url=job_url,
                status='no_submit_button',
                total_fields=len(mappings),
                fields_filled=filled_count,
                session_id=session_id
            )
            
        except Exception as e:
            return ApplicationResult(
                success=False,
                platform=ATSPlatform.UNKNOWN,
                job_id=job_url,
                job_url=job_url,
                status='error',
                error_message=str(e),
                session_id=session_id
            )
        finally:
            await self.browser.close_session(session_id)
    
    async def apply_batch(
        self, 
        job_urls: List[str],
        concurrent: int = 5
    ) -> List[ApplicationResult]:
        """
        Apply to multiple jobs with concurrency control
        """
        semaphore = asyncio.Semaphore(concurrent)
        
        async def apply_with_limit(url):
            async with semaphore:
                return await self.apply(url)
        
        tasks = [apply_with_limit(url) for url in job_urls]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def search_and_apply_dice(
        self,
        query: str,
        location: str = "",
        remote: bool = False,
        max_jobs: int = 10
    ) -> List[ApplicationResult]:
        """
        Search Dice.com and apply to Easy Apply jobs
        """
        dice = DiceHandler(self.browser, self.profile, self.ai_client)
        
        # Search for jobs
        jobs = await dice.search_jobs(
            query=query,
            location=location,
            remote=remote,
            max_results=max_jobs * 2  # Get more since not all are Easy Apply
        )
        
        # Apply to Easy Apply jobs
        return await dice.quick_apply_batch(jobs, max_jobs)
    
    def get_handler_stats(self) -> Dict:
        """Get statistics about handler usage"""
        return {
            "available_handlers": [h.__class__.__name__ for h in self.handlers],
            "active_sessions": self.browser.get_active_session_count(),
            "profile_loaded": bool(self.profile.email)
        }
    
    async def cleanup(self):
        """Clean up all resources"""
        await self.browser.close_all_sessions()
