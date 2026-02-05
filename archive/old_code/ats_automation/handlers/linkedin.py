"""
LinkedIn Job Board Handler (Improved)

Handles LinkedIn job pages - extracts job details and detects Easy Apply vs external apply
Includes: retry logic, multiple selectors, faster processing
"""

import asyncio
from typing import Optional
from ..models import ATSPlatform, ApplicationResult, UserProfile
from ..browserbase_manager import BrowserBaseManager
from .base_handler import BaseATSHandler
from ..utils.retry import async_retry, RetryConfig, should_retry


class LinkedInHandler(BaseATSHandler):
    """Handler for LinkedIn job board with retry logic"""
    
    IDENTIFIERS = ['linkedin.com/jobs/view', 'linkedin.com/jobs/cmp', 'linkedin.com/job/view']
    PLATFORM = ATSPlatform.LINKEDIN
    
    # All possible selectors for apply buttons (ordered by specificity)
    EASY_APPLY_SELECTORS = [
        'button:has-text("Easy Apply")',
        'button:has-text("Easy apply")',
        'button:has-text("EASY APPLY")',
        '[data-control-name="jobdetails_topcard_inapply"]',
        '.jobs-apply-button--top-card',
        'button.jobs-apply-button',
        'button[data-job-id]',
        'button.jobs-apply-button--trigger',
        '[data-testid="apply-button"]',
        'button:has-text("Apply")',
    ]
    
    EXTERNAL_APPLY_SELECTORS = [
        'a:has-text("Apply")',
        'a:has-text("apply")',
        'a:has-text("APPLY")',
        '[data-control-name="jobdetails_topcard_external_apple"]',
        '[data-control-name="jobdetails_topcard_external_apply"]',
        'a.jobs-apply-button[href]',
        'button:has-text("Apply on company website")',
        'a[href*="apply"][target="_blank"]',
        'a[href*://]:not([href*="linkedin.com"])',
        'a[href*="boards.greenhouse.io"]',
        'a[href*="jobs.lever.co"]',
        'a[href*="myworkdayjobs.com"]',
        'a[href*="careers"][target="_blank"]',
        'a[href*="smartrecruiters.com"]',
        'a[href*="applytojob.com"]',
    ]
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is a LinkedIn job page"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def apply(self, job_url: str, attempt: int = 0) -> ApplicationResult:
        """
        Apply to a LinkedIn job with retry logic
        
        Args:
            job_url: URL of the job
            attempt: Current retry attempt (0 = first try)
        """
        result = await self._try_apply(job_url, attempt)
        
        # Retry on specific failures
        if should_retry(result.status) and attempt < RetryConfig.LINKEDIN_RETRIES:
            wait_time = RetryConfig.LINKEDIN_DELAY * (2 ** attempt)
            print(f"⏳ Retrying LinkedIn job (attempt {attempt + 1}/{RetryConfig.LINKEDIN_RETRIES + 1}) in {wait_time}s...")
            await asyncio.sleep(wait_time)
            return await self.apply(job_url, attempt + 1)
        
        return result
    
    async def _try_apply(self, job_url: str, attempt: int = 0) -> ApplicationResult:
        """Internal apply method"""
        session = None
        try:
            session = await self.browser.create_stealth_session(platform="linkedin")
            page = session["page"]
            
            print(f"Navigating to LinkedIn job: {job_url}")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            
            # Dynamic wait: start with 2s, add 1s per retry attempt (max 4s)
            wait_time = min(2 + attempt, 4)
            await asyncio.sleep(wait_time)
            
            # Strategy 1: Look for Easy Apply button
            for selector in self.EASY_APPLY_SELECTORS:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        text = await button.text_content() or ""
                        if "easy" in text.lower():
                            print("✅ Found LinkedIn Easy Apply button")
                            return ApplicationResult(
                                success=False,
                                status="easy_apply_requires_login",
                                error_message="LinkedIn Easy Apply requires login - not automated",
                                platform=ATSPlatform.LINKEDIN,
                                job_id=job_url,
                                job_url=job_url,
                                session_id=session["session_id"]
                            )
                except:
                    continue
            
            # Strategy 2: Look for external "Apply" button
            for selector in self.EXTERNAL_APPLY_SELECTORS:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        href = await button.get_attribute('href')
                        text = await button.text_content() or ""
                        if href and href.startswith('http') and 'linkedin.com' not in href:
                            print(f"✅ Found external apply link: {href[:60]}...")
                            return ApplicationResult(
                                success=False,
                                status="redirect",
                                error_message=f"Redirect to company ATS: {href}",
                                platform=ATSPlatform.LINKEDIN,
                                job_id=job_url,
                                job_url=job_url,
                                session_id=session["session_id"],
                                redirect_url=href
                            )
                except:
                    continue
            
            # Strategy 3: Look for any link that might be an external apply
            try:
                all_links = await page.query_selector_all('a[href^="http"]')
                for link in all_links[:20]:  # Limit to first 20 links
                    try:
                        href = await link.get_attribute('href')
                        text = await link.text_content() or ""
                        if href and 'linkedin.com' not in href and ('apply' in text.lower() or 'job' in text.lower()):
                            print(f"✅ Found potential external link: {href[:60]}...")
                            return ApplicationResult(
                                success=False,
                                status="redirect",
                                error_message=f"Potential external apply: {href}",
                                platform=ATSPlatform.LINKEDIN,
                                job_id=job_url,
                                job_url=job_url,
                                session_id=session["session_id"],
                                redirect_url=href
                            )
                    except:
                        continue
            except:
                pass
            
            # Strategy 4: Check page content for apply-related text
            try:
                page_content = await page.content()
                content_lower = page_content.lower()
                if 'apply' in content_lower or 'application' in content_lower:
                    # Check if it's a job that requires external apply
                    if any(marker in content_lower for marker in ['external', 'company site', 'company website']):
                        print("✅ External application detected from page content")
                        return ApplicationResult(
                            success=False,
                            status="external_redirect",
                            error_message="External application required",
                            platform=ATSPlatform.LINKEDIN,
                            job_id=job_url,
                            job_url=job_url,
                            session_id=session["session_id"]
                        )
            except:
                pass
            
            # If we get here, couldn't detect application method
            return ApplicationResult(
                success=False,
                status="unknown_format",
                error_message="Could not detect application method on LinkedIn page",
                platform=ATSPlatform.LINKEDIN,
                job_id=job_url,
                job_url=job_url,
                session_id=session["session_id"]
            )
            
        except Exception as e:
            print(f"❌ LinkedIn application error: {e}")
            return ApplicationResult(
                success=False,
                status="error",
                error_message=str(e),
                platform=ATSPlatform.LINKEDIN,
                job_id=job_url,
                job_url=job_url,
                session_id=session["session_id"] if session else None
            )
        finally:
            if session:
                await self.browser.close_session(session["session_id"])
