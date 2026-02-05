#!/usr/bin/env python3
"""
External Application Adapter
Handles job applications on external company sites.
Auto-detects ATS type and routes to appropriate handler.
"""

import asyncio
import re
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from urllib.parse import urlparse

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)
from .validation import SubmissionValidator


# Configuration constants
class Config:
    """Configuration constants for external adapter"""
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 2  # seconds
    PAGE_TIMEOUT = 30000  # 30 seconds
    NAVIGATION_TIMEOUT = 60000  # 60 seconds
    HUMAN_DELAY_MIN = 2
    HUMAN_DELAY_MAX = 4
    MAX_FORM_STEPS = 10


class ExternalApplicationAdapter(JobPlatformAdapter):
    """
    Adapter for external/company website applications.
    Automatically detects ATS type and uses appropriate strategy.
    """
    
    platform = PlatformType.EXTERNAL
    
    # ATS detection patterns
    ATS_PATTERNS = {
        "greenhouse": ["greenhouse.io", "boards.greenhouse"],
        "lever": ["lever.co", "jobs.lever"],
        "workday": ["myworkdayjobs.com", "workday.com"],
        "ashby": ["ashbyhq.com", "jobs.ashby"],
        "smartrecruiters": ["smartrecruiters.com"],
        "icims": ["icims.com"],
        "taleo": ["taleo.net", "taleo.com"],
        "jobvite": ["jobvite.com"],
        "successfactors": ["successfactors.com"],
        "bamboohr": ["bamboohr.com"],
        "brassring": ["brassring.com"],
        "applytojob": ["applytojob.com"],
        "breezy": ["breezy.hr"],
        "recruitee": ["recruitee.com"],
        "comeet": ["comeet.co"],
        "teamtailor": ["teamtailor.com"],
    }
    
    def __init__(self, browser_manager=None, ats_type: str = None):
        super().__init__(browser_manager)
        self.ats_type = ats_type
    
    def detect_ats(self, url: str) -> str:
        """Detect ATS type from URL."""
        url_lower = url.lower()
        for ats, patterns in self.ATS_PATTERNS.items():
            if any(p in url_lower for p in patterns):
                return ats
        return "generic"
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Not used for external adapter."""
        return []
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details from external page."""
        session = await self.get_session()
        page = session.page
        
        await page.goto(job_url, wait_until="domcontentloaded", timeout=Config.NAVIGATION_TIMEOUT)
        await self.browser_manager.human_like_delay(Config.HUMAN_DELAY_MIN, Config.HUMAN_DELAY_MAX)
        
        # Extract title
        title_selectors = ["h1", "[class*='title']", "[class*='job-title']"]
        title = "Job Position"
        for sel in title_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    title = (await el.inner_text()).strip()[:100]
                    break
            except:
                continue
        
        # Extract company from URL
        domain = urlparse(job_url).netloc
        company = domain.replace('www.', '').split('.')[0].title()
        
        return JobPosting(
            id=f"ext_{hash(job_url)}",
            platform=self.platform,
            title=title,
            company=company,
            location="",
            url=job_url
        )
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """Apply to job on external site with retry logic."""
        
        last_error = None
        for attempt in range(Config.MAX_RETRIES):
            try:
                return await self._apply_with_retry(
                    job, resume, profile, cover_letter, auto_submit, attempt
                )
            except Exception as e:
                last_error = str(e)
                if attempt < Config.MAX_RETRIES - 1:
                    wait_time = Config.RETRY_DELAY_BASE * (2 ** attempt)
                    print(f"    ⚠️  Retry {attempt + 1}/{Config.MAX_RETRIES} in {wait_time}s: {last_error[:50]}")
                    await asyncio.sleep(wait_time)
                else:
                    break
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message=f"Failed after {Config.MAX_RETRIES} attempts: {last_error[:100]}"
        )
    
    async def _apply_with_retry(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str],
        auto_submit: bool,
        attempt: int
    ) -> ApplicationResult:
        """Internal apply method with attempt tracking."""
        
        # Detect ATS type
        ats = self.ats_type or self.detect_ats(job.url)
        
        # Route to appropriate handler
        handlers = {
            "greenhouse": self._apply_greenhouse,
            "lever": self._apply_lever,
            "workday": self._apply_workday,
            "ashby": self._apply_ashby,
        }
        
        handler = handlers.get(ats, self._apply_generic)
        return await handler(job, resume, profile, cover_letter, auto_submit, attempt)
    
    async def _fill_standard_form(
        self,
        page,
        profile: UserProfile,
        resume: Resume,
        cover_letter: Optional[str]
    ) -> int:
        """
        Fill standard application form fields.
        Returns number of fields filled.
        """
        fields_filled = 0
        
        # Define field mappings: (selectors, value)
        field_mappings: List[Tuple[List[str], str]] = [
            # First name
            ([
                'input[name="firstName"]', 'input[name="first_name"]',
                'input[name="first-name"]', 'input[placeholder*="First" i]',
                'input[id*="first" i]', 'input[data-testid*="first" i]'
            ], profile.first_name),
            
            # Last name
            ([
                'input[name="lastName"]', 'input[name="last_name"]',
                'input[name="last-name"]', 'input[placeholder*="Last" i]',
                'input[id*="last" i]', 'input[data-testid*="last" i]'
            ], profile.last_name),
            
            # Email
            ([
                'input[name="email"]', 'input[type="email"]',
                'input[name="email_address"]', 'input[placeholder*="Email" i]',
                'input[id*="email" i]'
            ], profile.email),
            
            # Phone
            ([
                'input[name="phone"]', 'input[type="tel"]',
                'input[name="phoneNumber"]', 'input[name="phone_number"]',
                'input[placeholder*="Phone" i]', 'input[id*="phone" i]'
            ], profile.phone),
            
            # LinkedIn
            ([
                'input[name="linkedin"]', 'input[name="linkedinUrl"]',
                'input[placeholder*="LinkedIn" i]', 'input[id*="linkedin" i]'
            ], profile.linkedin_url or ""),
            
            # Website/Portfolio
            ([
                'input[name="website"]', 'input[name="portfolio"]',
                'input[name="personalWebsite"]', 'input[placeholder*="Website" i]'
            ], profile.portfolio_url or ""),
        ]
        
        # Fill each field
        for selectors, value in field_mappings:
            if not value:  # Skip empty values
                continue
                
            for selector in selectors:
                try:
                    field = page.locator(selector).first
                    if await field.count() > 0 and await field.is_visible():
                        await field.fill(value)
                        await self.browser_manager.human_like_delay(0.5, 1)
                        fields_filled += 1
                        break
                except Exception:
                    continue
        
        # Handle resume upload
        if resume and resume.file_path:
            resume_filled = await self._upload_resume(page, resume.file_path)
            if resume_filled:
                fields_filled += 1
        
        # Handle cover letter
        if cover_letter:
            cover_selectors = [
                'textarea[name="coverLetter"]', 'textarea[name="cover_letter"]',
                'textarea[placeholder*="Cover" i]', 'textarea[id*="cover" i]'
            ]
            for selector in cover_selectors:
                try:
                    field = page.locator(selector).first
                    if await field.count() > 0 and await field.is_visible():
                        await field.fill(cover_letter)
                        fields_filled += 1
                        break
                except Exception:
                    continue
        
        # Fill custom questions if available
        if hasattr(profile, 'custom_answers') and profile.custom_answers:
            fields_filled += await self._fill_custom_questions(page, profile.custom_answers)
        
        return fields_filled
    
    async def _upload_resume(self, page, resume_path: str) -> bool:
        """Upload resume file to form."""
        resume_selectors = [
            'input[type="file"][name*="resume" i]',
            'input[type="file"][accept*=".pdf"], input[type="file"][accept*=".doc"]',
            'input[data-testid*="resume" i]',
            'input[id*="resume" i]'
        ]
        
        for selector in resume_selectors:
            try:
                upload_input = page.locator(selector).first
                if await upload_input.count() > 0 and await upload_input.is_visible():
                    await upload_input.set_input_files(resume_path)
                    await self.browser_manager.human_like_delay(1, 2)
                    return True
            except Exception:
                continue
        
        return False
    
    async def _fill_custom_questions(self, page, custom_answers: Dict[str, str]) -> int:
        """Fill custom application questions."""
        filled = 0
        
        # Common question patterns
        question_patterns = {
            "salary": ["salary", "compensation", "pay", "expected"],
            "relocate": ["relocate", "relocation", "willing to move"],
            "authorized": ["authorized", "eligible", "work in", "citizenship"],
            "sponsor": ["sponsor", "visa", "h1b"],
            "start": ["start", "notice", "available"],
            "clearance": ["clearance", "security"],
        }
        
        # Find all textareas and inputs that might be custom questions
        try:
            custom_fields = await page.locator(
                'textarea:not([name="coverLetter"]), '
                'input[type="text"]:not([name*="first"]):not([name*="last"]):not([name*="email"]):not([name*="phone"])'
            ).all()
            
            for field in custom_fields:
                try:
                    # Get label or placeholder text
                    label_text = ""
                    field_id = await field.get_attribute("id") or ""
                    if field_id:
                        label = page.locator(f'label[for="{field_id}"]').first
                        if await label.count() > 0:
                            label_text = (await label.inner_text()).lower()
                    
                    if not label_text:
                        placeholder = await field.get_attribute("placeholder") or ""
                        label_text = placeholder.lower()
                    
                    # Match with custom answers
                    for answer_key, answer_value in custom_answers.items():
                        patterns = question_patterns.get(answer_key, [answer_key])
                        if any(p in label_text for p in patterns):
                            await field.fill(answer_value)
                            filled += 1
                            break
                except Exception:
                    continue
        except Exception:
            pass
        
        return filled
    
    async def _apply_greenhouse(
        self, job, resume, profile, cover_letter, auto_submit, attempt
    ) -> ApplicationResult:
        """Apply to Greenhouse-hosted job."""
        session = await self.get_session()
        page = session.page
        
        try:
            await page.goto(job.url, wait_until="networkidle", timeout=Config.NAVIGATION_TIMEOUT)
            await self.browser_manager.human_like_delay(Config.HUMAN_DELAY_MIN, Config.HUMAN_DELAY_MAX)
            
            # Click apply button if present
            apply_btn = page.locator('[href="#application_form"], .button:has-text("Apply"), button:has-text("Apply")').first
            if await apply_btn.count() > 0:
                await apply_btn.click()
                await self.browser_manager.human_like_delay(1, 2)
            
            # Fill form fields
            fields_filled = await self._fill_standard_form(page, profile, resume, cover_letter)
            
            if not auto_submit:
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message=f"Greenhouse form filled ({fields_filled} fields), ready for review"
                )
            
            # Submit
            submit_btn = page.locator('input[type="submit"], button[type="submit"], #submit_app').first
            if await submit_btn.count() > 0:
                await submit_btn.click(timeout=10000)
                await self.browser_manager.human_like_delay(3, 5)
                
                # VALIDATE submission
                validation = await SubmissionValidator.validate(page, job.id, platform="greenhouse")
                if validation['success']:
                    return ApplicationResult(
                        status=ApplicationStatus.SUBMITTED,
                        submitted_at=datetime.now(),
                        confirmation_id=validation.get('confirmation_id'),
                        screenshot_path=validation.get('screenshot_path'),
                        message=validation.get('message')
                    )
                else:
                    return ApplicationResult(
                        status=ApplicationStatus.ERROR,
                        message=f"Greenhouse validation failed: {validation.get('message')}",
                        screenshot_path=validation.get('screenshot_path')
                    )
            
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Could not submit Greenhouse application"
            )
            
        except Exception as e:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Greenhouse error: {str(e)}"
            )
    
    async def _apply_lever(
        self, job, resume, profile, cover_letter, auto_submit, attempt
    ) -> ApplicationResult:
        """Apply to Lever-hosted job."""
        session = await self.get_session()
        page = session.page
        
        try:
            await page.goto(job.url, wait_until="networkidle", timeout=Config.NAVIGATION_TIMEOUT)
            await self.browser_manager.human_like_delay(Config.HUMAN_DELAY_MIN, Config.HUMAN_DELAY_MAX)
            
            # Click apply button
            apply_btn = page.locator('.posting-btn-apply, button:has-text("Apply")').first
            if await apply_btn.count() > 0:
                await apply_btn.click()
                await self.browser_manager.human_like_delay(2, 3)
            
            # Fill form
            fields_filled = await self._fill_standard_form(page, profile, resume, cover_letter)
            
            if not auto_submit:
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message=f"Lever form filled ({fields_filled} fields), ready for review"
                )
            
            # Submit - Lever uses specific button text
            submit_btn = page.locator('.postings-btn-submit, button:has-text("Submit Application")').first
            if await submit_btn.count() > 0:
                await submit_btn.click(timeout=10000)
                await self.browser_manager.human_like_delay(3, 5)
                
                # VALIDATE submission
                validation = await SubmissionValidator.validate(page, job.id, platform="lever")
                if validation['success']:
                    return ApplicationResult(
                        status=ApplicationStatus.SUBMITTED,
                        submitted_at=datetime.now(),
                        confirmation_id=validation.get('confirmation_id'),
                        screenshot_path=validation.get('screenshot_path'),
                        message=validation.get('message')
                    )
                else:
                    return ApplicationResult(
                        status=ApplicationStatus.ERROR,
                        message=f"Lever validation failed: {validation.get('message')}",
                        screenshot_path=validation.get('screenshot_path')
                    )
            
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Could not submit Lever application"
            )
            
        except Exception as e:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Lever error: {str(e)}"
            )
    
    async def _apply_workday(
        self, job, resume, profile, cover_letter, auto_submit, attempt
    ) -> ApplicationResult:
        """Apply to Workday-hosted job."""
        session = await self.get_session()
        page = session.page
        
        try:
            await page.goto(job.url, wait_until="networkidle", timeout=Config.NAVIGATION_TIMEOUT)
            await self.browser_manager.human_like_delay(3, 5)
            
            # Workday often has an "Apply" button to start
            apply_btn = page.locator('button:has-text("Apply"), [data-automation-id="applyButton"]').first
            if await apply_btn.count() > 0:
                await apply_btn.click()
                await self.browser_manager.human_like_delay(3, 5)
            
            # Fill form (Workday has complex multi-step forms)
            for step in range(Config.MAX_FORM_STEPS):
                fields_filled = await self._fill_standard_form(page, profile, resume, cover_letter)
                
                # Look for next/submit
                next_btn = page.locator(
                    'button:has-text("Next"), button:has-text("Continue"), '
                    '[data-automation-id="bottomNavigation"]'
                ).first
                
                submit_btn = page.locator(
                    'button:has-text("Submit"), button:has-text("Apply"), '
                    '[data-automation-id="submitButton"]'
                ).first
                
                if await submit_btn.count() > 0 and await submit_btn.is_visible():
                    if auto_submit:
                        await submit_btn.click(timeout=10000)
                        await self.browser_manager.human_like_delay(3, 5)
                        
                        # VALIDATE submission
                        validation = await SubmissionValidator.validate(page, job.id, platform="workday")
                        if validation['success']:
                            return ApplicationResult(
                                status=ApplicationStatus.SUBMITTED,
                                submitted_at=datetime.now(),
                                confirmation_id=validation.get('confirmation_id'),
                                screenshot_path=validation.get('screenshot_path'),
                                message=validation.get('message')
                            )
                        else:
                            return ApplicationResult(
                                status=ApplicationStatus.ERROR,
                                message=f"Workday validation failed: {validation.get('message')}",
                                screenshot_path=validation.get('screenshot_path')
                            )
                    else:
                        return ApplicationResult(
                            status=ApplicationStatus.PENDING_REVIEW,
                            message=f"Workday form ready for submission ({fields_filled} fields filled)"
                        )
                
                if await next_btn.count() > 0 and await next_btn.is_visible():
                    await next_btn.click(timeout=10000)
                    await self.browser_manager.human_like_delay(2, 3)
                else:
                    break
            
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Could not complete Workday application"
            )
            
        except Exception as e:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Workday error: {str(e)}"
            )
    
    async def _apply_ashby(
        self, job, resume, profile, cover_letter, auto_submit, attempt
    ) -> ApplicationResult:
        """Apply to Ashby-hosted job."""
        session = await self.get_session()
        page = session.page
        
        try:
            await page.goto(job.url, wait_until="networkidle", timeout=Config.NAVIGATION_TIMEOUT)
            await self.browser_manager.human_like_delay(Config.HUMAN_DELAY_MIN, Config.HUMAN_DELAY_MAX)
            
            # Fill form
            fields_filled = await self._fill_standard_form(page, profile, resume, cover_letter)
            
            if not auto_submit:
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message=f"Ashby form filled ({fields_filled} fields), ready for review"
                )
            
            # Submit
            submit_btn = page.locator('button[type="submit"], button:has-text("Submit")').first
            if await submit_btn.count() > 0:
                await submit_btn.click(timeout=10000)
                await self.browser_manager.human_like_delay(3, 5)
                
                # VALIDATE submission
                validation = await SubmissionValidator.validate(page, job.id, platform="ashby")
                if validation['success']:
                    return ApplicationResult(
                        status=ApplicationStatus.SUBMITTED,
                        submitted_at=datetime.now(),
                        confirmation_id=validation.get('confirmation_id'),
                        screenshot_path=validation.get('screenshot_path'),
                        message=validation.get('message')
                    )
                else:
                    return ApplicationResult(
                        status=ApplicationStatus.ERROR,
                        message=f"Ashby validation failed: {validation.get('message')}",
                        screenshot_path=validation.get('screenshot_path')
                    )
            
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Could not submit Ashby application"
            )
            
        except Exception as e:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Ashby error: {str(e)}"
            )
    
    async def _apply_generic(
        self, job, resume, profile, cover_letter, auto_submit, attempt
    ) -> ApplicationResult:
        """Apply to generic company site."""
        session = await self.get_session()
        page = session.page
        
        try:
            await page.goto(job.url, wait_until="networkidle", timeout=Config.NAVIGATION_TIMEOUT)
            await self.browser_manager.human_like_delay(3, 5)
            
            # Try to find and click apply button
            apply_patterns = [
                'a:has-text("Apply")', 'button:has-text("Apply")',
                'a:has-text("Apply Now")', 'button:has-text("Apply Now")',
                'a[href*="apply"]', '[class*="apply"]'
            ]
            
            for pattern in apply_patterns:
                try:
                    btn = page.locator(pattern).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(timeout=10000)
                        await self.browser_manager.human_like_delay(2, 3)
                        break
                except:
                    continue
            
            # Fill the form
            fields_filled = await self._fill_standard_form(page, profile, resume, cover_letter)
            
            if not fields_filled:
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message="Could not detect application form"
                )
            
            if not auto_submit:
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message=f"External form filled ({fields_filled} fields), ready for review"
                )
            
            # Try to submit
            submit_patterns = [
                'button[type="submit"]', 'input[type="submit"]',
                'button:has-text("Submit")', 'button:has-text("Apply")',
                'button:has-text("Send")', 'button:has-text("Complete")'
            ]
            
            for pattern in submit_patterns:
                try:
                    btn = page.locator(pattern).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(timeout=10000)
                        await self.browser_manager.human_like_delay(3, 5)
                        
                        # VALIDATE submission
                        validation = await SubmissionValidator.validate(page, job.id, platform="generic")
                        if validation['success']:
                            return ApplicationResult(
                                status=ApplicationStatus.SUBMITTED,
                                submitted_at=datetime.now(),
                                confirmation_id=validation.get('confirmation_id'),
                                screenshot_path=validation.get('screenshot_path'),
                                message=validation.get('message')
                            )
                        else:
                            return ApplicationResult(
                                status=ApplicationStatus.ERROR,
                                message=f"Generic validation failed: {validation.get('message')}",
                                screenshot_path=validation.get('screenshot_path')
                            )
                except:
                    continue
            
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Could not find submit button on external site"
            )
            
        except Exception as e:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"External site error: {str(e)}"
            )
