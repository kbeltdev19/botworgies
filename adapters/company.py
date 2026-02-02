"""
Generic Company Website Adapter
Handles job applications on company career pages (non-ATS).
"""

import asyncio
import re
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


class CompanyWebsiteAdapter(JobPlatformAdapter):
    """
    Generic adapter for company career pages.
    Uses AI to detect form fields and fill them appropriately.
    """
    
    platform = PlatformType.COMPANY_WEBSITE
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """
        Scrape jobs from a company careers page.
        Requires a careers URL to be provided in criteria.
        """
        session = await self.get_session()
        page = session.page
        
        # Get careers page URL from criteria
        careers_url = getattr(criteria, 'careers_url', None)
        if not careers_url:
            return []
        
        await page.goto(careers_url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 4)
        
        jobs = []
        
        # Common job listing selectors
        job_selectors = [
            "a[href*='job'], a[href*='career'], a[href*='position']",
            ".job-listing, .job-card, .career-item, .position-card",
            "[class*='job'], [class*='career'], [class*='position']",
            "li:has(a[href*='apply'])"
        ]
        
        for selector in job_selectors:
            try:
                items = await page.locator(selector).all()
                if len(items) > 0:
                    for item in items[:50]:  # Limit to 50 jobs
                        try:
                            # Try to extract job info
                            text = await item.inner_text()
                            link = item.locator("a").first if "a" not in selector else item
                            href = await link.get_attribute("href") if await link.count() > 0 else ""
                            
                            if href and len(text) > 5:
                                # Parse job title from text
                                title = text.split('\n')[0][:100].strip()
                                
                                # Make URL absolute
                                if href.startswith('/'):
                                    from urllib.parse import urljoin
                                    href = urljoin(careers_url, href)
                                
                                jobs.append(JobPosting(
                                    id=f"company_{hash(href)}",
                                    platform=self.platform,
                                    title=title,
                                    company=self._extract_company_name(careers_url),
                                    location="See job page",
                                    url=href,
                                    easy_apply=False
                                ))
                        except:
                            continue
                    break
            except:
                continue
        
        # Filter by role keywords if provided
        if criteria.roles:
            role_keywords = [r.lower() for r in criteria.roles]
            jobs = [j for j in jobs if any(kw in j.title.lower() for kw in role_keywords)]
        
        return jobs
    
    def _extract_company_name(self, url: str) -> str:
        """Extract company name from URL."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        # Remove www. and common suffixes
        name = domain.replace('www.', '').replace('.com', '').replace('.io', '').replace('.co', '')
        name = name.replace('careers.', '').replace('jobs.', '')
        return name.title()
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details from company job page."""
        session = await self.get_session()
        page = session.page
        
        await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)
        
        # Extract title
        title_selectors = ["h1", ".job-title", "[class*='title']", "title"]
        title = "Job Position"
        for sel in title_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    title = (await el.inner_text()).strip()[:100]
                    break
            except:
                continue
        
        # Extract description
        desc_selectors = [".job-description", ".description", "[class*='description']", "main", "article"]
        description = ""
        for sel in desc_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    description = (await el.inner_text())[:5000]
                    break
            except:
                continue
        
        return JobPosting(
            id=f"company_{hash(job_url)}",
            platform=self.platform,
            title=title,
            company=self._extract_company_name(job_url),
            location="",
            url=job_url,
            description=description
        )
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Apply to job on company website.
        Uses intelligent form detection and filling.
        """
        session = await self.get_session()
        page = session.page
        
        await page.goto(job.url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)
        
        # Find apply button
        apply_selectors = [
            "a:has-text('Apply'), button:has-text('Apply')",
            "a[href*='apply'], button[onclick*='apply']",
            ".apply-button, .btn-apply, [class*='apply']"
        ]
        
        for sel in apply_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await self.browser_manager.human_like_click(page, sel)
                    await self.browser_manager.human_like_delay(2, 3)
                    break
            except:
                continue
        
        # Now fill the form
        form_filled = await self._fill_application_form(page, profile, resume, cover_letter)
        
        if not form_filled:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Could not detect or fill application form"
            )
        
        if not auto_submit:
            screenshot_path = f"/tmp/company_review_{hash(job.url)}.png"
            await page.screenshot(path=screenshot_path)
            
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Form filled, ready for review",
                screenshot_path=screenshot_path
            )
        
        # Find and click submit
        submit_selectors = [
            "button[type='submit']",
            "button:has-text('Submit'), input[type='submit']",
            "button:has-text('Apply'), button:has-text('Send')"
        ]
        
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await self.browser_manager.human_like_click(page, sel)
                    await self.browser_manager.human_like_delay(3, 5)
                    
                    return ApplicationResult(
                        status=ApplicationStatus.SUBMITTED,
                        message="Application submitted",
                        submitted_at=datetime.now()
                    )
            except:
                continue
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not find submit button"
        )
    
    async def _fill_application_form(
        self, page, profile: UserProfile, resume: Resume, cover_letter: Optional[str]
    ) -> bool:
        """Intelligently fill application form fields."""
        
        # Common field mappings (selector pattern -> value)
        field_map = {
            # Name fields
            r"(first.?name|fname|given)": profile.first_name,
            r"(last.?name|lname|surname|family)": profile.last_name,
            r"(full.?name|name)": f"{profile.first_name} {profile.last_name}",
            
            # Contact fields
            r"(email|e-mail)": profile.email,
            r"(phone|mobile|tel)": profile.phone,
            r"(linkedin|profile.?url)": profile.linkedin_url or "",
            
            # Experience
            r"(years?.?experience|experience.?years)": str(profile.years_experience or ""),
        }
        
        filled_count = 0
        
        # Find all input fields
        inputs = await page.locator("input[type='text'], input[type='email'], input[type='tel'], textarea").all()
        
        for input_el in inputs:
            try:
                # Get field identifiers
                name = (await input_el.get_attribute("name") or "").lower()
                id_attr = (await input_el.get_attribute("id") or "").lower()
                placeholder = (await input_el.get_attribute("placeholder") or "").lower()
                
                identifier = f"{name} {id_attr} {placeholder}"
                
                # Match against patterns
                for pattern, value in field_map.items():
                    if re.search(pattern, identifier, re.IGNORECASE) and value:
                        await input_el.fill(value)
                        filled_count += 1
                        break
            except:
                continue
        
        # Handle file upload for resume
        file_input = page.locator("input[type='file']").first
        if await file_input.count() > 0:
            try:
                await file_input.set_input_files(resume.file_path)
                filled_count += 1
            except:
                pass
        
        # Handle cover letter textarea
        if cover_letter:
            cover_textarea = page.locator("textarea[name*='cover'], textarea[id*='cover'], textarea[placeholder*='cover']").first
            if await cover_textarea.count() > 0:
                await cover_textarea.fill(cover_letter)
                filled_count += 1
        
        return filled_count > 0
