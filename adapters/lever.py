"""
Lever Adapter - Tier 1 (API-Based)
Public JSON API, no browser needed.
"""

import aiohttp
import asyncio
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


# Popular companies using Lever
DEFAULT_LEVER_COMPANIES = [
    "netflix", "twitch", "lyft", "spotify", "cloudflare",
    "databricks", "dbt-labs", "hashicorp", "pulumi", "temporal",
    "cockroachlabs", "materialize", "singlestore", "neon", "supabase",
    "railway", "render", "fly", "modal", "replicate",
]


class LeverAdapter(JobPlatformAdapter):
    """
    Lever job board adapter.
    Uses public JSON API - no browser needed.
    """
    
    platform = PlatformType.LEVER
    tier = "api"
    
    def __init__(self, browser_manager=None, companies: List[str] = None, session_cookie: str = None):
        super().__init__(browser_manager)
        self.companies = companies or DEFAULT_LEVER_COMPANIES
        self._session = None
    
    async def _get_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"}
            )
        return self._session
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search Lever job boards across multiple companies."""
        session = await self._get_session()
        all_jobs = []
        
        for company in self.companies:
            try:
                url = f"https://api.lever.co/v0/postings/{company}?mode=json"
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        continue
                    
                    jobs = await resp.json()
                    
                    for job in jobs:
                        title = job.get("text", "").lower()
                        location = job.get("categories", {}).get("location", "").lower()
                        
                        # Filter by role keywords
                        if not any(kw.lower() in title for kw in criteria.roles):
                            continue
                        
                        # Filter by location if specified
                        if criteria.locations:
                            if not any(loc.lower() in location or "remote" in location 
                                      for loc in criteria.locations):
                                continue
                        
                        all_jobs.append(JobPosting(
                            id=f"lever_{job['id']}",
                            platform=self.platform,
                            title=job.get("text", ""),
                            company=company.replace("-", " ").title(),
                            location=job.get("categories", {}).get("location", ""),
                            url=job.get("hostedUrl", job.get("applyUrl", "")),
                            description=job.get("descriptionPlain", ""),
                            easy_apply=True,
                            remote="remote" in location
                        ))
                
                await asyncio.sleep(0.2)
                
            except Exception as e:
                print(f"[Lever] Error fetching {company}: {e}")
                continue
        
        print(f"[Lever] Found {len(all_jobs)} jobs across {len(self.companies)} companies")
        return all_jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details from Lever."""
        session = await self._get_session()
        
        # Extract job ID from URL
        # Format: https://jobs.lever.co/{company}/{id}
        parts = job_url.rstrip("/").split("/")
        job_id = parts[-1]
        company = parts[-2] if len(parts) >= 2 else "unknown"
        
        url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
        
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Job not found: {job_url}")
            
            data = await resp.json()
            
            return JobPosting(
                id=f"lever_{job_id}",
                platform=self.platform,
                title=data.get("text", ""),
                company=company.replace("-", " ").title(),
                location=data.get("categories", {}).get("location", ""),
                url=data.get("hostedUrl", job_url),
                description=data.get("descriptionPlain", ""),
                easy_apply=True,
                remote="remote" in data.get("categories", {}).get("location", "").lower()
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
        Apply to a Lever posting via the public web form.

        - Fill core fields + resume upload.
        - If CAPTCHA is present, do not attempt to bypass; return PENDING_REVIEW.
        - If auto_submit is False, stop at review with a screenshot.
        """
        if not self.browser_manager:
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message=f"Apply at: {job.url}",
                external_url=job.url,
            )

        session = await self.browser_manager.create_session(self.platform.value)
        page = session.page

        async def try_fill(selectors: List[str], value: str) -> bool:
            value = (value or "").strip()
            if not value:
                return False
            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.fill(value)
                        await asyncio.sleep(0.2)
                        return True
                except Exception:
                    continue
            return False

        async def try_upload(selectors: List[str], file_path: str) -> bool:
            if not file_path or not Path(file_path).exists():
                return False
            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0:
                        await loc.set_input_files(file_path)
                        await asyncio.sleep(0.5)
                        return True
                except Exception:
                    continue
            return False

        async def detect_captcha() -> bool:
            selectors = [
                'iframe[src*="recaptcha"]',
                'iframe[src*="captcha"]',
                ".g-recaptcha",
                "[data-sitekey]",
            ]
            for sel in selectors:
                try:
                    if await page.locator(sel).count() > 0:
                        return True
                except Exception:
                    continue
            return False

        async def fill_additional_fields() -> dict:
            """
            Best-effort fill for additional required fields (screening/EEO/etc).
            Returns dict: {filled: int, missing_required: [question,...]}.
            """
            try:
                from ai.form_intelligence import get_form_intelligence

                fi = get_form_intelligence()
            except Exception:
                fi = None

            profile_ctx = {
                "first_name": getattr(profile, "first_name", ""),
                "last_name": getattr(profile, "last_name", ""),
                "email": getattr(profile, "email", ""),
                "phone": getattr(profile, "phone", ""),
                "location": getattr(profile, "location", ""),
                "work_authorization": getattr(profile, "work_authorization", "Yes"),
                "sponsorship_required": getattr(profile, "sponsorship_required", "No"),
                "years_experience": getattr(profile, "years_experience", None),
                "custom_answers": getattr(profile, "custom_answers", {}) or {},
            }
            resume_text = getattr(resume, "raw_text", "") or ""
            job_desc = getattr(job, "description", "") or ""

            filled = 0
            missing_required: list[str] = []
            processed_radio_names: set[str] = set()

            controls = page.locator("form input, form select, form textarea")
            try:
                total = await controls.count()
            except Exception:
                return {"filled": 0, "missing_required": []}

            max_controls = min(total, 200)
            for i in range(max_controls):
                el = controls.nth(i)
                try:
                    if not await el.is_visible():
                        continue
                except Exception:
                    continue

                try:
                    tag = await el.evaluate("e => e.tagName.toLowerCase()")
                except Exception:
                    continue

                itype = ""
                if tag == "input":
                    try:
                        itype = (await el.get_attribute("type") or "").lower()
                    except Exception:
                        itype = ""
                    if itype in {"hidden", "submit", "button", "image", "reset"}:
                        continue
                    if itype == "file":
                        continue

                try:
                    required = bool(
                        await el.evaluate("e => !!(e.required || e.getAttribute('aria-required') === 'true')")
                    )
                except Exception:
                    required = False

                # Already filled?
                try:
                    if tag == "input" and itype == "checkbox":
                        if await el.is_checked():
                            continue
                    elif tag == "input" and itype == "radio":
                        name = (await el.get_attribute("name") or "").strip()
                        if name in processed_radio_names:
                            continue
                        group_checked = await el.evaluate(
                            """(e) => {
                                const name = e.getAttribute('name');
                                if (!name) return e.checked;
                                const sel = `input[type="radio"][name="${CSS.escape(name)}"]`;
                                return Array.from(document.querySelectorAll(sel)).some(r => r.checked);
                            }"""
                        )
                        if group_checked:
                            processed_radio_names.add(name)
                            continue
                    else:
                        val = (await el.input_value()) if hasattr(el, "input_value") else ""
                        if (val or "").strip():
                            continue
                except Exception:
                    pass

                # Question text
                question = ""
                try:
                    question = (
                        await el.evaluate(
                            """(e) => {
                                const byFor = e.id ? document.querySelector(`label[for="${e.id}"]`) : null;
                                const label = byFor?.innerText || e.closest('label')?.innerText || '';
                                const legend = e.closest('fieldset')?.querySelector('legend')?.innerText || '';
                                const aria = e.getAttribute('aria-label') || '';
                                const ph = e.getAttribute('placeholder') || '';
                                const nm = e.getAttribute('name') || '';
                                return (legend || label || aria || ph || nm || '').trim();
                            }"""
                        )
                        or ""
                    )
                except Exception:
                    question = ""

                if tag == "input" and itype == "checkbox":
                    if required:
                        try:
                            await el.check()
                            filled += 1
                        except Exception:
                            missing_required.append(question or "required_checkbox")
                    continue

                if tag == "input" and itype == "radio":
                    try:
                        group = await el.evaluate(
                            """(e) => {
                                const name = e.getAttribute('name') || '';
                                const sel = name ? `input[type="radio"][name="${CSS.escape(name)}"]` : '';
                                const radios = sel ? Array.from(document.querySelectorAll(sel)) : [e];
                                const legend = e.closest('fieldset')?.querySelector('legend')?.innerText || '';
                                const opts = radios.map(r => ({
                                    id: r.id || '',
                                    value: r.value || '',
                                    label: (document.querySelector(`label[for="${r.id}"]`)?.innerText || r.closest('label')?.innerText || '').trim()
                                }));
                                const req = radios.some(r => r.required || r.getAttribute('aria-required') === 'true');
                                return {name, legend, options: opts, required: req};
                            }"""
                        )
                        name = (group or {}).get("name") or ""
                        processed_radio_names.add(name)
                        opts = (group or {}).get("options") or []
                        opt_labels = [o.get("label") or o.get("value") for o in opts if (o.get("label") or o.get("value"))]
                        qtxt = (group or {}).get("legend") or question or "Please choose an option"
                        if not opt_labels:
                            if (group or {}).get("required"):
                                missing_required.append(qtxt)
                            continue

                        if fi:
                            ans = await fi.answer_question(
                                question=qtxt,
                                question_type="radio",
                                options=opt_labels,
                                profile=profile_ctx,
                                resume_text=resume_text,
                                job_description=job_desc,
                                context={"company": getattr(job, "company", ""), "title": getattr(job, "title", "")},
                            )
                        else:
                            ans = opt_labels[0]

                        clicked = False
                        for o in opts:
                            lbl = (o.get("label") or o.get("value") or "").strip()
                            if not lbl:
                                continue
                            if lbl.lower() == str(ans).lower():
                                if o.get("id"):
                                    await page.locator(f"label[for='{o['id']}']").first.click()
                                else:
                                    await el.click()
                                clicked = True
                                filled += 1
                                break
                        if not clicked:
                            await el.click()
                            filled += 1
                        continue
                    except Exception:
                        if required:
                            missing_required.append(question or "required_radio")
                        continue

                if tag == "select":
                    try:
                        options_text = [t.strip() for t in await el.locator("option").all_inner_texts() if t.strip()]
                    except Exception:
                        options_text = []
                    if not options_text:
                        if required:
                            missing_required.append(question or "required_select")
                        continue
                    if fi:
                        ans = await fi.answer_question(
                            question=question or "Select an option",
                            question_type="select",
                            options=options_text,
                            profile=profile_ctx,
                            resume_text=resume_text,
                            job_description=job_desc,
                            context={"company": getattr(job, "company", ""), "title": getattr(job, "title", "")},
                        )
                    else:
                        ans = options_text[0]
                    try:
                        await el.select_option(label=str(ans))
                    except Exception:
                        try:
                            await el.select_option(value=str(ans))
                        except Exception:
                            pass
                    filled += 1
                    continue

                if tag in {"input", "textarea"}:
                    if fi:
                        ans = await fi.answer_question(
                            question=question or "Answer",
                            question_type="text",
                            options=None,
                            profile=profile_ctx,
                            resume_text=resume_text,
                            job_description=job_desc,
                            context={"company": getattr(job, "company", ""), "title": getattr(job, "title", "")},
                        )
                    else:
                        ans = "Not specified"
                    try:
                        await el.fill(str(ans))
                        filled += 1
                    except Exception:
                        if required:
                            missing_required.append(question or "required_text")
                    continue

            return {"filled": filled, "missing_required": missing_required}

        screenshot_path = None
        try:
            await page.goto(job.url, wait_until="domcontentloaded", timeout=60000)
            await self.browser_manager.human_like_delay(2, 4)

            # Lever often hides the form behind an "Apply" CTA.
            for sel in [
                'a:has-text("Apply")',
                'button:has-text("Apply")',
                'a[href*="apply"]',
            ]:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(1)
                        break
                except Exception:
                    continue

            full_name = f"{profile.first_name} {profile.last_name}".strip()
            await try_fill(
                [
                    "input[name='name']",
                    "input#name",
                    "input[placeholder*='Name' i]",
                ],
                full_name,
            )
            await try_fill(
                [
                    "input[name='email']",
                    "input#email",
                    "input[type='email']",
                ],
                profile.email,
            )
            await try_fill(
                [
                    "input[name='phone']",
                    "input#phone",
                    "input[type='tel']",
                ],
                profile.phone,
            )

            await try_upload(
                [
                    "input[name='resume']",
                    "input#resume",
                    "input[type='file']",
                ],
                resume.file_path,
            )

            if cover_letter:
                await try_fill(
                    [
                        "textarea[name='comments']",
                        "textarea#comments",
                        "textarea[name*='cover' i]",
                    ],
                    cover_letter,
                )

            extra = await fill_additional_fields()
            if extra.get("missing_required"):
                screenshot_path = f"/tmp/lever_required_missing_{job.id}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message=f"Missing required fields ({len(extra.get('missing_required'))}); manual review required.",
                    screenshot_path=screenshot_path,
                    external_url=job.url,
                )

            if await detect_captcha():
                screenshot_path = f"/tmp/lever_captcha_{job.id}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message="CAPTCHA detected; manual completion required.",
                    screenshot_path=screenshot_path,
                    external_url=job.url,
                )

            if not auto_submit:
                screenshot_path = f"/tmp/lever_review_{job.id}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message="Lever application filled; ready for review.",
                    screenshot_path=screenshot_path,
                    external_url=job.url,
                )

            # Submit
            submitted = False
            for sel in [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text(\"Submit\")",
                "button:has-text(\"Send\")",
                "button:has-text(\"Apply\")",
            ]:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible() and await btn.is_enabled():
                        await btn.click()
                        await asyncio.sleep(3)
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                screenshot_path = f"/tmp/lever_submit_missing_{job.id}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message="Submit button not found/clickable.",
                    screenshot_path=screenshot_path,
                    external_url=job.url,
                )

            content = (await page.content()).lower()
            if "thank you" in content or "application submitted" in content:
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message="Application submitted",
                    submitted_at=datetime.now(),
                )

            screenshot_path = f"/tmp/lever_post_submit_{job.id}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Submitted, but confirmation not detected. Please verify.",
                screenshot_path=screenshot_path,
                external_url=job.url,
            )
        except Exception as e:
            screenshot_path = screenshot_path or f"/tmp/lever_error_{job.id}.png"
            try:
                await page.screenshot(path=screenshot_path, full_page=True)
            except Exception:
                pass
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Lever apply failed: {e}",
                screenshot_path=screenshot_path,
                external_url=job.url,
                error=str(e),
            )
        finally:
            try:
                await self.browser_manager.close_session(session.session_id)
            except Exception:
                pass


async def test_lever():
    """Test Lever adapter."""
    from .base import SearchConfig
    
    adapter = LeverAdapter()
    
    criteria = SearchConfig(
        roles=["software engineer", "backend", "platform"],
        locations=["Remote"],
        posted_within_days=30
    )
    
    try:
        jobs = await adapter.search_jobs(criteria)
        print(f"\nFound {len(jobs)} jobs:")
        for job in jobs[:10]:
            print(f"  - {job.title} at {job.company} ({job.location})")
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(test_lever())
