"""
Workday ATS Handler
Enterprise standard - multi-step wizard, heavy JavaScript
"""

import asyncio
import random
import re
from typing import Optional
from ..models import ApplicationResult, ATSPlatform
from .base_handler import BaseATSHandler


class WorkdayHandler(BaseATSHandler):
    """Handler for Workday ATS (myworkdayjobs.com)"""
    
    IDENTIFIERS = ['myworkdayjobs.com', 'workday.com', 'wd101.myworkdayjobs.com']
    PLATFORM = ATSPlatform.WORKDAY
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is a Workday job posting"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def apply(self, job_url: str) -> ApplicationResult:
        """Apply to Workday job"""
        session = await self.browser.create_stealth_session("workday")
        page = session["page"]
        session_id = session["session_id"]
        
        try:
            # Navigate with extra wait for React hydration
            await page.goto(job_url, wait_until='networkidle')
            await asyncio.sleep(4)
            
            # Check for captcha
            if not await self.browser.solve_captcha_if_present(session_id, page):
                return ApplicationResult(
                    success=False,
                    platform=self.PLATFORM,
                    job_id=job_url,
                    job_url=job_url,
                    status='captcha_blocked',
                    error_message='CAPTCHA detected and could not be solved',
                    session_id=session_id
                )
            
            # Click Apply button
            apply_btn = await page.wait_for_selector(
                '[data-automation-id="applyButton"], '
                'button:has-text("Apply"), '
                'a:has-text("Apply")',
                timeout=10000
            )
            await apply_btn.click()
            await self._human_delay(2, 4)
            
            # Handle login/account creation
            if await page.query_selector('text="Sign In"'):
                await self._handle_workday_login(page)
            
            # Multi-step wizard
            max_steps = 10
            for step in range(max_steps):
                step_type = await self._detect_step_type(page)
                print(f"Workday step {step}: {step_type}")
                
                if step_type == 'my_info':
                    await self._fill_my_info(page)
                elif step_type == 'experience':
                    await self._fill_experience(page)
                elif step_type == 'questions':
                    await self._fill_questions(page)
                elif step_type == 'eeo':
                    await self._fill_eeo(page)
                elif step_type == 'review':
                    if await self._submit_application(page):
                        return await self._extract_confirmation(page, job_url, session_id)
                    break
                elif step_type == 'complete':
                    return await self._extract_confirmation(page, job_url, session_id)
                
                # Click next
                next_btn = await page.wait_for_selector(
                    '[data-automation-id="nextButton"], '
                    'button:has-text("Continue"), '
                    'button:has-text("Next")',
                    timeout=5000
                )
                await next_btn.click()
                await self._human_delay(3, 5)
            
            return ApplicationResult(
                success=False,
                platform=self.PLATFORM,
                job_id=job_url,
                job_url=job_url,
                status='incomplete',
                error_message=f'Stuck at step after {max_steps} attempts',
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
        finally:
            await self.browser.close_session(session_id)
    
    async def _handle_workday_login(self, page):
        """Handle Workday login or account creation"""
        # Look for "Apply as Guest" option
        guest_btn = await page.query_selector('text="Apply as Guest"')
        if guest_btn:
            await guest_btn.click()
            await self._human_delay(2, 3)
            return
        
        # Create account option
        create_btn = await page.query_selector('text="Create Account"')
        if create_btn:
            await create_btn.click()
            await self._human_delay(2, 3)
            
            # Fill registration
            await self._fill_with_mapper(page, ['email'])
            
            # Password
            password = self._generate_temp_password()
            pwd_field = await page.query_selector('input[type="password"]')
            if pwd_field:
                await pwd_field.fill(password)
            
            await self._find_and_click(page, [
                'button:has-text("Create Account")',
                '[data-automation-id="createAccountButton"]'
            ])
            await self._human_delay(3, 5)
    
    async def _detect_step_type(self, page) -> str:
        """Detect which step of the application we're on"""
        try:
            content = await page.content()
            
            # Check for completion first
            if any(text in content for text in ['Application Submitted', 'Thank you for applying', 'Confirmation']):
                return 'complete'
            
            if 'My Information' in content or 'Personal Information' in content or 'My Info' in content:
                return 'my_info'
            elif 'My Experience' in content or 'Experience' in content or 'Resume' in content:
                return 'experience'
            elif 'Application Questions' in content or 'Screening Questions' in content or 'Questions' in content:
                return 'questions'
            elif 'Voluntary Disclosures' in content or 'EEO' in content or 'Demographics' in content:
                return 'eeo'
            elif 'Review' in content and 'Submit' in content:
                return 'review'
            elif 'Documents' in content:
                return 'documents'
            
            return 'unknown'
        except:
            return 'unknown'
    
    async def _fill_my_info(self, page):
        """Fill personal information step"""
        await self._fill_with_mapper(page, [
            'first_name', 'last_name', 'email', 'phone', 
            'address', 'linkedin', 'website'
        ])
    
    async def _fill_experience(self, page):
        """Handle resume upload and experience"""
        # Upload resume
        upload_input = await page.query_selector('input[type="file"]')
        if upload_input:
            await upload_input.set_input_files(self.profile.resume_path)
            await asyncio.sleep(5)  # Wait for parsing
        
        # Fill additional fields
        await self._fill_with_mapper(page, ['linkedin', 'website', 'github'])
    
    async def _fill_questions(self, page):
        """Handle screening questions"""
        # Workday uses various selectors for questions
        question_containers = await page.query_selector_all(
            '[data-automation-id="formField"], '
            '.css-1vn1bu7, '
            '[data-automation-id="question"]'
        )
        
        for container in question_containers:
            try:
                # Get question text
                question_text = await container.inner_text()
                
                # Find input
                input_el = await container.query_selector('input, select, textarea')
                if not input_el:
                    continue
                
                # Generate answer based on question
                answer = await self._generate_answer(question_text)
                
                # Fill based on input type
                tag_name = await input_el.evaluate('el => el.tagName.toLowerCase()')
                
                if tag_name == 'select':
                    await input_el.select_option(label=answer)
                elif tag_name == 'input':
                    input_type = await input_el.get_attribute('type')
                    if input_type == 'checkbox':
                        if answer.lower() in ['yes', 'true']:
                            await input_el.check()
                    else:
                        await input_el.fill(answer)
                else:
                    await input_el.fill(answer)
                    
            except Exception as e:
                print(f"Error filling question: {e}")
                continue
    
    async def _generate_answer(self, question_text: str) -> str:
        """Generate answer for screening question"""
        q_lower = question_text.lower()
        
        # Salary expectations
        if any(word in q_lower for word in ['salary', 'compensation', 'pay']):
            return self.profile.salary_expectation or 'Negotiable'
        
        # Start date/availability
        if any(word in q_lower for word in ['start', 'availability', 'notice']):
            return '2 weeks'
        
        # Experience years
        if 'experience' in q_lower and any(word in q_lower for word in ['years', 'how many']):
            return str(self.profile.years_experience) if self.profile.years_experience else '3'
        
        # Yes/No questions
        if any(word in q_lower for word in ['authorized', 'legally', 'sponsorship']):
            return 'Yes'
        
        if 'relocation' in q_lower or 'relocate' in q_lower:
            return 'Open to discussion'
        
        # Default
        return 'N/A'
    
    async def _fill_eeo(self, page):
        """Fill EEO/voluntary disclosure information"""
        # Select "Prefer not to answer" for all EEO fields
        selects = await page.query_selector_all('select')
        
        for select in selects:
            try:
                options = await select.query_selector_all('option')
                for option in options:
                    text = await option.inner_text()
                    text_lower = text.lower()
                    
                    if any(phrase in text_lower for phrase in [
                        'prefer not', 'decline', 'do not wish', 
                        'not to answer', 'choose not'
                    ]):
                        await select.select_option(text=text)
                        break
            except:
                continue
    
    async def _submit_application(self, page) -> bool:
        """Click final submit button"""
        try:
            submit_btn = await page.wait_for_selector(
                '[data-automation-id="submitButton"], '
                'button:has-text("Submit Application"), '
                'button[type="submit"]',
                timeout=5000
            )
            await submit_btn.click()
            await asyncio.sleep(3)
            return True
        except:
            return False
    
    async def _extract_confirmation(
        self, 
        page, 
        job_url: str, 
        session_id: str
    ) -> ApplicationResult:
        """Extract confirmation number if available"""
        try:
            content = await page.content()
            
            # Look for confirmation patterns
            confirmation = None
            patterns = [
                r'confirmation\s*#?\s*:?\s*([A-Z0-9\-]+)',
                r'reference\s*#?\s*:?\s*([A-Z0-9\-]+)',
                r'application\s*#?\s*:?\s*([A-Z0-9\-]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    confirmation = match.group(1)
                    break
            
            return ApplicationResult(
                success=True,
                platform=self.PLATFORM,
                job_id=job_url,
                job_url=job_url,
                status='submitted',
                confirmation_number=confirmation,
                session_id=session_id
            )
        except Exception as e:
            return ApplicationResult(
                success=True,  # Still consider success if we got here
                platform=self.PLATFORM,
                job_id=job_url,
                job_url=job_url,
                status='submitted',
                error_message=f'Confirmation extraction failed: {e}',
                session_id=session_id
            )
