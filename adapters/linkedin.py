"""
LinkedIn Adapter - Production-Ready Easy Apply Automation

LinkedIn has the most jobs but best anti-bot detection.
Requires li_at session cookie from browser.

Features:
- Complete multi-step Easy Apply flow
- AI-powered custom question answering
- Robust success/failure detection
- Screenshot capture at each step
- Final submission with confirmation extraction

WARNING: This performs REAL application submissions. Use test accounts only.
"""

import aiohttp
import asyncio
import random
import json
import re
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)

# Import AI service for question answering
try:
    from ai.kimi_service import KimiResumeOptimizer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    KimiResumeOptimizer = None


class LinkedInAdapter(JobPlatformAdapter):
    """
    LinkedIn job search and Easy Apply automation.
    
    Requires authentication via li_at cookie.
    
    Usage:
        adapter = LinkedInAdapter(browser_manager, session_cookie="your_li_at_cookie")
        jobs = await adapter.search_jobs(criteria)
        result = await adapter.apply_to_job(job, resume, profile, auto_submit=True)
    """
    
    platform = PlatformType.LINKEDIN
    tier = "aggressive"
    
    # Rate limits (conservative to avoid bans)
    MAX_DAILY_APPLICATIONS = 5
    MAX_SEARCHES_PER_HOUR = 10
    COOLDOWN_BETWEEN_ACTIONS = (3, 8)  # seconds
    
    BASE_URL = "https://www.linkedin.com"
    
    # Success indicators for application completion
    SUCCESS_INDICATORS = [
        "application sent",
        "application submitted",
        "thank you for applying",
        "your application has been received",
        "we've received your application",
        "successfully applied",
        "applied successfully"
    ]
    
    # Confirmation ID patterns
    CONFIRMATION_PATTERNS = [
        r'confirmation[\s#:]*([A-Z0-9\-]+)',
        r'reference[\s#:]*([A-Z0-9\-]+)',
        r'application[\s#:]*([A-Z0-9\-]+)',
        r'id[\s#:]*([A-Z0-9\-]{5,})'
    ]
    
    def __init__(self, browser_manager=None, session_cookie: str = None):
        super().__init__(browser_manager)
        self.session_cookie = session_cookie
        self._session = None
        self._search_count = 0
        self._application_count = 0
        self._last_action = None
        self.ai_service = KimiResumeOptimizer() if AI_AVAILABLE else None
        
        # Screenshot directory
        self.screenshot_dir = Path("/tmp/linkedin_screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
    
    async def _get_session(self):
        """Get authenticated aiohttp session."""
        if not self._session and self.session_cookie:
            cookies = {
                "li_at": self.session_cookie,
                "JSESSIONID": f"ajax:{random.randint(1000000000, 9999999999)}"
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/vnd.linkedin.normalized+json+2.1",
                "X-Restli-Protocol-Version": "2.0.0",
                "X-Li-Lang": "en_US",
                "X-Li-Track": json.dumps({
                    "clientVersion": "1.13.1795",
                    "mpVersion": "1.13.1795",
                    "osName": "web",
                    "timezoneOffset": -8,
                    "deviceFormFactor": "DESKTOP"
                })
            }
            self._session = aiohttp.ClientSession(cookies=cookies, headers=headers)
        return self._session
    
    async def close(self):
        """Close session."""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _human_delay(self):
        """Add human-like delay between actions."""
        delay = random.uniform(*self.COOLDOWN_BETWEEN_ACTIONS)
        await asyncio.sleep(delay)
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """
        Search LinkedIn for jobs.
        
        Note: This uses the Voyager API (private, may break).
        For more reliability, use browser automation.
        """
        if not self.session_cookie:
            raise ValueError("LinkedIn requires li_at session cookie")
        
        session = await self._get_session()
        
        await self._human_delay()
        
        # Build search query
        keywords = quote(" ".join(criteria.roles))
        location = quote(criteria.locations[0] if criteria.locations else "")
        
        # LinkedIn Voyager API
        url = f"{self.BASE_URL}/voyager/api/search/dash/clusters"
        params = {
            "decorationId": "com.linkedin.voyager.dash.deco.search.SearchClusterCollection-175",
            "origin": "SWITCH_SEARCH_VERTICAL",
            "q": "all",
            "query": f"(keywords:{keywords},locationUnion:(geoId:103644278))",
            "start": 0,
            "count": 25,
        }
        
        # Add Easy Apply filter
        if criteria.easy_apply_only:
            params["query"] += ",f_AL:true"
        
        jobs = []
        
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 429:
                    print("[LinkedIn] Rate limited!")
                    return []
                
                if resp.status == 401:
                    print("[LinkedIn] Session expired - need new li_at cookie")
                    return []
                
                if resp.status != 200:
                    print(f"[LinkedIn] Search failed: {resp.status}")
                    return []
                
                data = await resp.json()
                jobs = self._parse_search_results(data)
                
        except Exception as e:
            print(f"[LinkedIn] Search error: {e}")
        
        self._search_count += 1
        print(f"[LinkedIn] Found {len(jobs)} jobs")
        
        return jobs
    
    def _parse_search_results(self, data: dict) -> List[JobPosting]:
        """Parse LinkedIn Voyager API search results."""
        jobs = []
        
        try:
            included = data.get("included", [])
            
            for item in included:
                if item.get("$type") == "com.linkedin.voyager.dash.jobs.JobPosting":
                    try:
                        job_id = item.get("dashEntityUrn", "").split(":")[-1]
                        title = item.get("title", "")
                        company_name = ""
                        location = ""
                        
                        # Extract company
                        company_ref = item.get("primaryDescription", {})
                        if company_ref:
                            company_name = company_ref.get("text", "")
                        
                        # Extract location
                        location_ref = item.get("secondaryDescription", {})
                        if location_ref:
                            location = location_ref.get("text", "")
                        
                        # Check for Easy Apply
                        easy_apply = item.get("applyMethod", {}).get("$type", "").endswith("EasyApplyOnlineApplyMethod")
                        
                        if title:
                            jobs.append(JobPosting(
                                id=f"linkedin_{job_id}",
                                platform=self.platform,
                                title=title,
                                company=company_name or "(see posting)",
                                location=location,
                                url=f"{self.BASE_URL}/jobs/view/{job_id}",
                                easy_apply=easy_apply,
                                remote="remote" in location.lower()
                            ))
                    except Exception:
                        continue
                        
        except Exception as e:
            print(f"[LinkedIn] Parse error: {e}")
        
        return jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details using browser."""
        if not self.browser_manager:
            raise ValueError("Job details require browser_manager")
        
        session = await self.browser_manager.create_stealth_session("linkedin")
        page = session.page
        
        try:
            # Set cookie if available
            if self.session_cookie:
                await page.context.add_cookies([{
                    "name": "li_at",
                    "value": str(self.session_cookie),
                    "domain": ".linkedin.com",
                    "path": "/"
                }])
            else:
                logger.warning("[LinkedIn] No session cookie provided - authentication may fail")
            
            await page.goto(job_url, wait_until="domcontentloaded")
            await self._human_delay()
            
            # Extract details with multiple selector fallbacks
            title = await self._get_element_text(page, [
                ".job-details-jobs-unified-top-card__job-title",
                "h1.job-details-jobs-unified-top-card__job-title",
                "[data-test-id='job-title']"
            ])
            
            company = await self._get_element_text(page, [
                ".job-details-jobs-unified-top-card__company-name",
                "a.job-details-jobs-unified-top-card__company-name",
                ".company-name"
            ])
            
            location = await self._get_element_text(page, [
                ".job-details-jobs-unified-top-card__primary-description-container",
                ".job-details-jobs-unified-top-card__bullet",
                ".location"
            ])
            
            description = await self._get_element_text(page, [
                ".jobs-description__content",
                ".job-details-jobs-unified-top-card__job-description",
                "[data-test-id='job-description']"
            ])
            
            # Check for Easy Apply button
            easy_apply_selectors = [
                ".jobs-apply-button--top-card",
                "button:has-text('Easy Apply')",
                "[data-test-id='easy-apply-button']"
            ]
            easy_apply = False
            for selector in easy_apply_selectors:
                try:
                    if await page.locator(selector).count() > 0:
                        easy_apply = True
                        break
                except:
                    continue
            
            return JobPosting(
                id=job_url.split("/")[-1],
                platform=self.platform,
                title=title.strip() if title else "Unknown",
                company=company.strip() if company else "Unknown",
                location=location.strip() if location else "",
                url=job_url,
                description=description,
                easy_apply=easy_apply,
                remote="remote" in location.lower() if location else False
            )
            
        finally:
            await self.browser_manager.close_session(session.session_id)
    
    async def _get_element_text(self, page, selectors: List[str]) -> Optional[str]:
        """Try multiple selectors to get element text."""
        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0:
                    text = await loc.inner_text()
                    if text:
                        return text
            except:
                continue
        return None
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Apply via LinkedIn Easy Apply with REAL submission.
        
        Args:
            job: Job posting to apply to
            resume: Resume to use
            profile: User profile information
            cover_letter: Optional cover letter text
            auto_submit: If True, actually submits the application
                        If False, stops for review before final submit
        
        Returns:
            ApplicationResult with status and confirmation details
        """
        if self._application_count >= self.MAX_DAILY_APPLICATIONS:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Daily application limit reached"
            )
        
        if not job.easy_apply:
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message="Not Easy Apply - requires external application",
                external_url=job.url
            )
        
        if not self.browser_manager:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Browser automation required for Easy Apply"
            )
        
        session = await self.browser_manager.create_stealth_session("linkedin")
        page = session.page
        
        # Track screenshots for each step
        screenshots = []
        step_number = 0
        
        try:
            # Set cookie if available
            if self.session_cookie:
                await page.context.add_cookies([{
                    "name": "li_at",
                    "value": str(self.session_cookie),
                    "domain": ".linkedin.com",
                    "path": "/"
                }])
            else:
                logger.warning("[LinkedIn] No session cookie provided - authentication may fail")
            
            # Navigate to job
            print(f"[LinkedIn] Navigating to {job.url}")
            await page.goto(job.url, wait_until="networkidle")
            await self._human_delay()
            
            # Capture initial screenshot
            step_number += 1
            screenshot_path = await self._capture_step_screenshot(page, job.id, step_number, "initial")
            screenshots.append(screenshot_path)
            
            # Click Easy Apply button
            easy_apply_btn = page.locator(".jobs-apply-button--top-card, button:has-text('Easy Apply')").first
            if await easy_apply_btn.count() == 0:
                return ApplicationResult(
                    status=ApplicationStatus.EXTERNAL_APPLICATION,
                    message="Easy Apply button not found",
                    screenshot_path=screenshots[-1]
                )
            
            await self.browser_manager.human_like_click(page, ".jobs-apply-button--top-card")
            await asyncio.sleep(2)
            
            step_number += 1
            screenshot_path = await self._capture_step_screenshot(page, job.id, step_number, "apply_modal_open")
            screenshots.append(screenshot_path)
            
            # Handle multi-step form
            max_steps = 15
            form_data = {
                "fields_filled": [],
                "questions_answered": [],
                "steps_completed": 0
            }
            
            for step in range(max_steps):
                print(f"[LinkedIn] Processing step {step + 1}")
                await asyncio.sleep(1)
                
                # Capture screenshot of current step
                step_number += 1
                screenshot_path = await self._capture_step_screenshot(page, job.id, step_number, f"step_{step + 1}")
                screenshots.append(screenshot_path)
                
                # Check for completion indicators
                if await self._is_application_submitted(page):
                    self._application_count += 1
                    confirmation_id = await self._extract_confirmation_id(page)
                    
                    # Capture success screenshot
                    step_number += 1
                    success_screenshot = await self._capture_step_screenshot(page, job.id, step_number, "success")
                    screenshots.append(success_screenshot)
                    
                    return ApplicationResult(
                        status=ApplicationStatus.SUBMITTED,
                        message="Application submitted successfully via LinkedIn Easy Apply",
                        confirmation_id=confirmation_id,
                        screenshot_path=success_screenshot,
                        submitted_at=datetime.now()
                    )
                
                # Check for error messages
                error_msg = await self._check_for_errors(page)
                if error_msg:
                    return ApplicationResult(
                        status=ApplicationStatus.ERROR,
                        message=f"Application error: {error_msg}",
                        screenshot_path=screenshots[-1]
                    )
                
                # Fill contact info
                fields_filled = await self._fill_contact_info(page, profile)
                form_data["fields_filled"].extend(fields_filled)
                
                # Handle resume upload
                if resume.file_path and Path(resume.file_path).exists():
                    await self._upload_resume(page, resume.file_path)
                    form_data["fields_filled"].append("resume")
                
                # Handle cover letter if provided
                if cover_letter:
                    await self._fill_cover_letter(page, cover_letter)
                    form_data["fields_filled"].append("cover_letter")
                
                # Handle custom questions with AI
                questions_answered = await self._answer_custom_questions(page, resume, profile)
                form_data["questions_answered"].extend(questions_answered)
                
                # Check if this is the final submit step
                is_final_step = await self._is_final_step(page)
                
                if is_final_step:
                    # Review step - capture screenshot
                    step_number += 1
                    review_screenshot = await self._capture_step_screenshot(page, job.id, step_number, "review")
                    screenshots.append(review_screenshot)
                    
                    if not auto_submit:
                        # Stop for human review
                        return ApplicationResult(
                            status=ApplicationStatus.PENDING_REVIEW,
                            message=f"Application ready for final submission. Review screenshot: {review_screenshot}",
                            screenshot_path=review_screenshot,
                            external_url=job.url  # User can manually complete
                        )
                    
                    # Click final submit
                    print("[LinkedIn] Submitting application...")
                    submit_success = await self._click_final_submit(page)
                    
                    if submit_success:
                        await asyncio.sleep(3)
                        
                        # Check for success
                        if await self._is_application_submitted(page):
                            self._application_count += 1
                            confirmation_id = await self._extract_confirmation_id(page)
                            
                            step_number += 1
                            success_screenshot = await self._capture_step_screenshot(page, job.id, step_number, "submitted")
                            screenshots.append(success_screenshot)
                            
                            return ApplicationResult(
                                status=ApplicationStatus.SUBMITTED,
                                message="Application submitted successfully via LinkedIn Easy Apply",
                                confirmation_id=confirmation_id,
                                screenshot_path=success_screenshot,
                                submitted_at=datetime.now()
                            )
                    else:
                        return ApplicationResult(
                            status=ApplicationStatus.ERROR,
                            message="Failed to click submit button",
                            screenshot_path=screenshots[-1]
                        )
                
                # Click Next/Continue to proceed
                next_clicked = await self._click_next(page)
                if not next_clicked:
                    # No next button - might be done or stuck
                    print("[LinkedIn] No next button found, checking completion status")
                    if await self._is_application_submitted(page):
                        self._application_count += 1
                        confirmation_id = await self._extract_confirmation_id(page)
                        return ApplicationResult(
                            status=ApplicationStatus.SUBMITTED,
                            message="Application submitted",
                            confirmation_id=confirmation_id,
                            screenshot_path=screenshots[-1],
                            submitted_at=datetime.now()
                        )
                    break
                
                await self._human_delay()
                form_data["steps_completed"] = step + 1
            
            # Max steps reached without completion
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Could not complete application flow after {max_steps} steps",
                screenshot_path=screenshots[-1]
            )
            
        except Exception as e:
            # Capture error screenshot
            try:
                error_screenshot = await self._capture_step_screenshot(page, job.id, step_number, "error")
                screenshots.append(error_screenshot)
            except:
                pass
            
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Application error: {str(e)}",
                screenshot_path=screenshots[-1] if screenshots else None,
                error=str(e)
            )
            
        finally:
            await self.browser_manager.close_session(session.session_id)
    
    async def _capture_step_screenshot(self, page, job_id: str, step: int, label: str) -> str:
        """Capture screenshot of current step."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"linkedin_{job_id}_step{step:02d}_{label}_{timestamp}.png"
        filepath = self.screenshot_dir / filename
        
        try:
            await page.screenshot(path=str(filepath), full_page=True)
            print(f"[LinkedIn] Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"[LinkedIn] Screenshot failed: {e}")
            return ""
    
    async def _is_application_submitted(self, page) -> bool:
        """Check if application has been successfully submitted."""
        # Check for success indicators
        for indicator in self.SUCCESS_INDICATORS:
            try:
                loc = page.locator(f"text={indicator}").first
                if await loc.count() > 0 and await loc.is_visible():
                    return True
            except:
                continue
        
        # Check for success modal
        success_selectors = [
            ".artdeco-modal--confirmation",
            ".jobs-post-apply-modal",
            "[data-test-modal-id='post-apply-modal']"
        ]
        for selector in success_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except:
                continue
        
        return False
    
    async def _extract_confirmation_id(self, page) -> Optional[str]:
        """Extract confirmation/reference ID from success page."""
        try:
            # Get page text
            content = await page.content()
            text = await page.inner_text("body")
            
            # Search for confirmation patterns
            for pattern in self.CONFIRMATION_PATTERNS:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    return matches[0].strip()
            
            # Check for LinkedIn-specific confirmation elements
            confirmation_selectors = [
                ".artdeco-modal__content .artdeco-entity-lockup__title",
                ".jobs-post-apply-modal__content",
                "[data-test-id='confirmation-message']"
            ]
            for selector in confirmation_selectors:
                try:
                    loc = page.locator(selector).first
                    if await loc.count() > 0:
                        text = await loc.inner_text()
                        for pattern in self.CONFIRMATION_PATTERNS:
                            matches = re.findall(pattern, text, re.IGNORECASE)
                            if matches:
                                return matches[0].strip()
                except:
                    continue
            
        except Exception as e:
            print(f"[LinkedIn] Failed to extract confirmation ID: {e}")
        
        return None
    
    async def _check_for_errors(self, page) -> Optional[str]:
        """Check for error messages on the page."""
        error_selectors = [
            ".artdeco-inline-feedback__message",
            ".jobs-easy-apply-form-section__error-message",
            ".artdeco-modal__error",
            "[role='alert']"
        ]
        
        for selector in error_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    return await loc.inner_text()
            except:
                continue
        
        return None
    
    async def _fill_contact_info(self, page, profile: UserProfile) -> List[str]:
        """Fill contact information fields."""
        fields_filled = []
        
        field_mappings = {
            'input[name="phoneNumber"], input[type="tel"], input[id*="phone"]': profile.phone,
            'input[name="email"], input[type="email"], input[id*="email"]': profile.email,
            'input[name="firstName"], input[id*="first"], input[placeholder*="First"]': profile.first_name,
            'input[name="lastName"], input[id*="last"], input[placeholder*="Last"]': profile.last_name,
            'input[name="linkedin"], input[id*="linkedin"], input[placeholder*="LinkedIn"]': profile.linkedin_url or "",
        }
        
        for selector, value in field_mappings.items():
            try:
                if value:
                    loc = page.locator(selector).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.fill(str(value))
                        fields_filled.append(selector.split(',')[0])
                        await asyncio.sleep(0.5)
            except Exception as e:
                print(f"[LinkedIn] Failed to fill field {selector}: {e}")
        
        return fields_filled
    
    async def _upload_resume(self, page, file_path: str):
        """Upload resume file."""
        try:
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                await file_input.set_input_files(file_path)
                print(f"[LinkedIn] Resume uploaded: {file_path}")
                await asyncio.sleep(2)  # Wait for upload
        except Exception as e:
            print(f"[LinkedIn] Resume upload failed: {e}")
    
    async def _fill_cover_letter(self, page, cover_letter: str):
        """Fill cover letter textarea."""
        try:
            # Look for cover letter textarea
            selectors = [
                'textarea[name="coverLetter"], textarea[id*="cover"], textarea[placeholder*="cover"]',
                "textarea[data-test-id='cover-letter-textarea']"
            ]
            for selector in selectors:
                loc = page.locator(selector).first
                if await loc.count() > 0:
                    await loc.fill(cover_letter)
                    print("[LinkedIn] Cover letter filled")
                    break
        except Exception as e:
            print(f"[LinkedIn] Cover letter fill failed: {e}")
    
    async def _answer_custom_questions(self, page, resume: Resume, profile: UserProfile) -> List[Dict]:
        """Answer custom application questions using AI."""
        questions_answered = []
        
        if not self.ai_service:
            print("[LinkedIn] AI service not available for question answering")
            return questions_answered
        
        try:
            # Find all question containers
            question_selectors = [
                ".jobs-easy-apply-form-section__question",
                ".artdeco-text-input",
                ".artdeco-text-area",
                ".artdeco-dropdown"
            ]
            
            for selector in question_selectors:
                questions = await page.locator(selector).all()
                
                for question_el in questions:
                    try:
                        # Get question label/text
                        label = await question_el.locator("label, .artdeco-text-input__label, .artdeco-text-area__label").inner_text()
                        
                        if not label:
                            continue
                        
                        # Check if already answered
                        input_el = question_el.locator("input, textarea, select").first
                        current_value = await input_el.input_value() if await input_el.count() > 0 else ""
                        
                        if current_value:
                            continue  # Already filled
                        
                        # Get input type
                        input_type = await input_el.get_attribute("type") if await input_el.count() > 0 else "text"
                        
                        # Answer with AI
                        answer = await self.ai_service.answer_application_question(
                            question=label,
                            resume_context=resume.raw_text[:2000],
                            existing_answers=profile.custom_answers
                        )
                        
                        # Fill the answer
                        if input_type in ["text", "email", "tel", "number"]:
                            await input_el.fill(answer)
                        elif input_type == "textarea":
                            await input_el.fill(answer)
                        
                        questions_answered.append({
                            "question": label,
                            "answer": answer
                        })
                        
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        print(f"[LinkedIn] Failed to answer question: {e}")
                        continue
            
        except Exception as e:
            print(f"[LinkedIn] Question answering error: {e}")
        
        return questions_answered
    
    async def _is_final_step(self, page) -> bool:
        """Check if current step is the final review/submit step."""
        # Look for submit button
        submit_selectors = [
            'button[aria-label*="Submit"]',
            'button:has-text("Submit application")',
            'button[type="submit"]:has-text("Submit")',
            "[data-test-id='submit-application-button']"
        ]
        
        for selector in submit_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    return True
            except:
                continue
        
        # Check for review step indicators
        review_indicators = [
            "review your application",
            "verify your information",
            "check your details"
        ]
        
        for indicator in review_indicators:
            try:
                loc = page.locator(f"text={indicator}").first
                if await loc.count() > 0 and await loc.is_visible():
                    return True
            except:
                continue
        
        return False
    
    async def _click_next(self, page) -> bool:
        """Click Next/Continue button to proceed."""
        next_selectors = [
            'button[aria-label*="Continue"]',
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'button[type="button"]:has-text("Next")',
            "[data-test-id='continue-button']"
        ]
        
        for selector in next_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible() and await loc.is_enabled():
                    await self.browser_manager.human_like_click(page, selector)
                    print(f"[LinkedIn] Clicked: {selector}")
                    return True
            except Exception as e:
                print(f"[LinkedIn] Failed to click {selector}: {e}")
                continue
        
        return False
    
    async def _click_final_submit(self, page) -> bool:
        """Click the final submit button."""
        submit_selectors = [
            'button[aria-label*="Submit"]',
            'button:has-text("Submit application")',
            'button[type="submit"]',
            'button.artdeco-button--primary:has-text("Submit")',
            "[data-test-id='submit-application-button']"
        ]
        
        for selector in submit_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible() and await loc.is_enabled():
                    await self.browser_manager.human_like_click(page, selector)
                    print(f"[LinkedIn] Clicked submit: {selector}")
                    return True
            except Exception as e:
                print(f"[LinkedIn] Failed to click submit {selector}: {e}")
                continue
        
        return False


async def test_linkedin():
    """Test LinkedIn adapter with real submission (requires li_at cookie)."""
    import os
    
    li_at = os.environ.get("LINKEDIN_LI_AT")
    if not li_at:
        print("Set LINKEDIN_LI_AT environment variable")
        return
    
    from core import UnifiedBrowserManager
    
    manager = UnifiedBrowserManager(prefer_local=True)
    adapter = LinkedInAdapter(manager, session_cookie=li_at)
    
    from adapters.base import SearchConfig
    criteria = SearchConfig(
        roles=["software engineer"],
        locations=["San Francisco"],
        easy_apply_only=True,
        posted_within_days=7
    )
    
    try:
        # Search for jobs
        jobs = await adapter.search_jobs(criteria)
        print(f"Found {len(jobs)} Easy Apply jobs")
        
        for job in jobs[:3]:
            print(f"  - {job.title} at {job.company}")
        
        # To actually apply (be careful!):
        # job = jobs[0]
        # result = await adapter.apply_to_job(job, resume, profile, auto_submit=False)
        # print(f"Application result: {result}")
        
    finally:
        await adapter.close()
        await manager.close_all()


if __name__ == "__main__":
    asyncio.run(test_linkedin())
