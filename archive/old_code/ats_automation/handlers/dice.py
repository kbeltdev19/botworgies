"""
Dice.com Handler
Tech-focused job board with Easy Apply feature
"""

import asyncio
import json
from typing import List, Optional, Dict, Any
from ..models import ApplicationResult, ATSPlatform, DiceJob
from .base_handler import BaseATSHandler


class DiceHandler(BaseATSHandler):
    """Handler for Dice.com job applications"""
    
    IDENTIFIERS = ['dice.com', 'www.dice.com']
    PLATFORM = ATSPlatform.DICE
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is Dice.com job posting"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def search_jobs(
        self,
        query: str = "",
        location: str = "",
        remote: bool = False,
        job_type: str = "",  # contract, fulltime, etc.
        max_results: int = 50
    ) -> List[DiceJob]:
        """
        Search for jobs on Dice.com
        
        Note: This uses the web interface since Dice doesn't have a public API
        """
        session = await self.browser.create_stealth_session("dice")
        page = session["page"]
        session_id = session["session_id"]
        
        jobs = []
        
        try:
            # Build search URL
            search_url = "https://www.dice.com/jobs"
            params = []
            
            if query:
                params.append(f"q={query.replace(' ', '%20')}")
            if location:
                params.append(f"location={location.replace(' ', '%20')}")
            if remote:
                params.append("remote=true")
            if job_type:
                params.append(f"employmentType={job_type}")
            
            if params:
                search_url += "?" + "&".join(params)
            
            await page.goto(search_url, wait_until='networkidle')
            await self._human_delay(3, 5)
            
            # Scroll to load more jobs
            for _ in range(min(max_results // 10, 5)):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self._human_delay(1, 2)
            
            # Extract job listings
            job_cards = await page.query_selector_all(
                '[data-cy="search-result"], '
                '.search-result, '
                '[data-testid="job-card"]'
            )
            
            for card in job_cards[:max_results]:
                try:
                    job = await self._extract_dice_job(card)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    print(f"Error extracting Dice job: {e}")
                    continue
            
        except Exception as e:
            print(f"Error searching Dice: {e}")
        finally:
            await self.browser.close_session(session_id)
        
        return jobs
    
    async def _extract_dice_job(self, card) -> Optional[DiceJob]:
        """Extract job data from Dice job card"""
        try:
            # Title
            title_el = await card.query_selector('a[id*="position-title"], .job-title, h3 a')
            title = await title_el.inner_text() if title_el else "Unknown"
            
            # Company
            company_el = await card.query_selector('[data-cy="company-name"], .company-name, .employer-name')
            company = await company_el.inner_text() if company_el else "Unknown"
            
            # Location
            location_el = await card.query_selector('[data-cy="location"], .location, .search-result-location')
            location = await location_el.inner_text() if location_el else ""
            
            # URL
            link_el = await card.query_selector('a[href*="/job/"]')
            url = await link_el.get_attribute('href') if link_el else ""
            if url and not url.startswith('http'):
                url = f"https://www.dice.com{url}"
            
            # Job ID from URL
            job_id = url.split('/job/')[-1].split('/')[0] if '/job/' in url else ""
            
            # Check if Easy Apply
            easy_apply_el = await card.query_selector('text="Easy Apply", .easy-apply')
            easy_apply = easy_apply_el is not None
            
            # Remote check
            remote = 'remote' in location.lower() or 'work from home' in title.lower()
            
            # Job type (Contract/Full-time)
            job_type_el = await card.query_selector('.job-type, [data-cy="employment-type"]')
            job_type = await job_type_el.inner_text() if job_type_el else ""
            
            return DiceJob(
                id=job_id,
                title=title.strip(),
                company=company.strip(),
                location=location.strip(),
                url=url,
                easy_apply=easy_apply,
                remote=remote,
                job_type=job_type.strip()
            )
            
        except Exception as e:
            print(f"Error in _extract_dice_job: {e}")
            return None
    
    async def apply(self, job_url: str) -> ApplicationResult:
        """
        Apply to Dice.com job
        
        Dice has two types:
        1. Easy Apply - In-page application (preferred)
        2. External Apply - Redirects to company site
        """
        session = await self.browser.create_stealth_session("dice")
        page = session["page"]
        session_id = session["session_id"]
        
        try:
            await page.goto(job_url, wait_until='networkidle')
            await self._human_delay(3, 5)
            
            # Check for Easy Apply
            easy_apply_btn = await page.query_selector(
                'button:has-text("Easy Apply"), '
                'a:has-text("Easy Apply"), '
                '.easy-apply-button'
            )
            
            if easy_apply_btn:
                return await self._apply_easy_apply(page, easy_apply_btn, job_url, session_id)
            else:
                # External apply - redirect to company site
                return await self._apply_external(page, job_url, session_id)
            
        except Exception as e:
            return ApplicationResult(
                success=False,
                platform=self.PLATFORM,
                job_id=job_url,
                job_url=job_url,
                status='error',
                error_message=str(e),
                session_id=session_id
            )
        finally:
            await self.browser.close_session(session_id)
    
    async def _apply_easy_apply(
        self, 
        page, 
        easy_apply_btn, 
        job_url: str, 
        session_id: str
    ) -> ApplicationResult:
        """Apply using Dice Easy Apply"""
        try:
            await easy_apply_btn.click()
            await self._human_delay(3, 5)
            
            # Check if login required
            if await page.query_selector('text="Sign In", text="Login"'):
                await self._handle_dice_login(page)
            
            # Fill application form
            fields_filled = await self._fill_with_mapper(page)
            
            # Submit
            submit_btn = await page.query_selector(
                'button:has-text("Submit"), '
                'button:has-text("Send Application"), '
                'input[value="Submit"]'
            )
            
            if submit_btn:
                await submit_btn.click()
                await self._human_delay(3, 5)
                
                # Check for success message
                content = await page.content()
                success_indicators = [
                    'application has been submitted',
                    'successfully applied',
                    'thank you for applying',
                    'application sent'
                ]
                
                success = any(ind in content.lower() for ind in success_indicators)
                
                return ApplicationResult(
                    success=success,
                    platform=self.PLATFORM,
                    job_id=job_url,
                    job_url=job_url,
                    status='submitted' if success else 'pending_verification',
                    fields_filled=fields_filled,
                    session_id=session_id
                )
            
            return ApplicationResult(
                success=False,
                platform=self.PLATFORM,
                job_id=job_url,
                job_url=job_url,
                status='incomplete',
                error_message='Submit button not found',
                fields_filled=fields_filled,
                session_id=session_id
            )
            
        except Exception as e:
            return ApplicationResult(
                success=False,
                platform=self.PLATFORM,
                job_id=job_url,
                job_url=job_url,
                status='error',
                error_message=str(e),
                session_id=session_id
            )
    
    async def _apply_external(
        self, 
        page, 
        job_url: str, 
        session_id: str
    ) -> ApplicationResult:
        """Handle external apply (redirect to company site)"""
        try:
            # Click external apply button
            apply_btn = await page.query_selector(
                'button:has-text("Apply"), '
                'a:has-text("Apply"), '
                '.apply-button'
            )
            
            if apply_btn:
                await apply_btn.click()
                await self._human_delay(2, 3)
                
                # Check if new tab opened
                pages = page.context.pages
                if len(pages) > 1:
                    new_page = pages[-1]
                    new_url = new_page.url
                    
                    return ApplicationResult(
                        success=False,  # We didn't complete, just redirected
                        platform=self.PLATFORM,
                        job_id=job_url,
                        job_url=job_url,
                        status='external_redirect',
                        error_message=f'Redirected to external site: {new_url}',
                        session_id=session_id
                    )
            
            return ApplicationResult(
                success=False,
                platform=self.PLATFORM,
                job_id=job_url,
                job_url=job_url,
                status='external_redirect',
                error_message='External application required',
                session_id=session_id
            )
            
        except Exception as e:
            return ApplicationResult(
                success=False,
                platform=self.PLATFORM,
                job_id=job_url,
                job_url=job_url,
                status='error',
                error_message=str(e),
                session_id=session_id
            )
    
    async def _handle_dice_login(self, page):
        """Handle Dice.com login"""
        # Check if we can use stored credentials or apply without login
        email_field = await page.query_selector('input[type="email"], input[name="email"]')
        if email_field:
            await email_field.fill(self.profile.email)
        
        # Look for "Continue without login" or similar
        continue_btn = await page.query_selector(
            'button:has-text("Continue"), '
            'button:has-text("Next"), '
            'button:has-text("Apply as Guest")'
        )
        
        if continue_btn:
            await continue_btn.click()
            await self._human_delay(2, 3)
    
    async def quick_apply_batch(
        self,
        jobs: List[DiceJob],
        max_applications: int = 10
    ) -> List[ApplicationResult]:
        """
        Quickly apply to multiple Easy Apply jobs on Dice
        
        Only applies to jobs with easy_apply=True
        """
        results = []
        easy_apply_jobs = [j for j in jobs if j.easy_apply][:max_applications]
        
        print(f"Applying to {len(easy_apply_jobs)} Easy Apply jobs on Dice...")
        
        for job in easy_apply_jobs:
            print(f"  Applying to {job.title} at {job.company}...")
            result = await self.apply(job.url)
            results.append(result)
            
            # Delay between applications
            await asyncio.sleep(5)
        
        return results
