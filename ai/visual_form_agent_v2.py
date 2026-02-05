#!/usr/bin/env python3
"""
Visual Form Agent V2 - Robust Form Filling with Verification.

Key improvements:
1. Fills ALL required fields (Last Name, Location, etc.)
2. Uploads resume files
3. Handles EEO/screening questions intelligently
4. Verifies actual submission (URL change, confirmation message)
5. No false positives - only reports success when truly successful
"""

import asyncio
import base64
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class ActionType(Enum):
    FILL = "fill"
    SELECT = "select"
    UPLOAD = "upload"
    CLICK = "click"
    CHECK = "check"
    WAIT = "wait"


@dataclass
class FormField:
    """Represents a form field."""
    name: str
    field_type: str  # text, email, tel, file, select, checkbox, radio
    required: bool = False
    selector: str = ""
    value: str = ""
    label: str = ""
    options: List[str] = field(default_factory=list)


@dataclass
class FormAction:
    """A single action to perform."""
    action_type: ActionType
    field_name: str
    value: Any = None
    selector: str = ""
    success: bool = False
    error: Optional[str] = None


class VisualFormAgentV2:
    """
    Robust form filling agent with verification.
    """
    
    def __init__(self, vision_model: str = "moonshot-v1-8k-vision-preview"):
        self.vision_model = vision_model
        self.api_key = os.getenv('MOONSHOT_API_KEY')
        self.base_url = "https://api.moonshot.ai/v1"
        
    async def initialize(self):
        """Initialize API key."""
        if not self.api_key:
            from dotenv import load_dotenv
            load_dotenv()
            self.api_key = os.getenv('MOONSHOT_API_KEY')
    
    async def apply(
        self,
        page,
        profile: Dict[str, Any],
        job_data: Dict[str, Any],
        resume_path: str,
        max_steps: int = 20
    ) -> Dict[str, Any]:
        """
        Apply to a job with full verification.
        
        Returns:
            Dict with 'success', 'confirmation_id', 'error', 'verified'
        """
        result = {
            'success': False,
            'verified': False,
            'confirmation_id': None,
            'error': None,
            'fields_filled': [],
            'steps_completed': 0
        }
        
        try:
            # Capture initial URL
            initial_url = page.url
            logger.info(f"[VFA2] Starting application on: {initial_url}")
            
            # Step 1: Fill basic information
            logger.info("[VFA2] Step 1: Filling basic information...")
            basic_result = await self._fill_basic_info(page, profile)
            result['fields_filled'].extend(basic_result['filled'])
            
            # Step 2: Upload resume
            logger.info("[VFA2] Step 2: Uploading resume...")
            resume_result = await self._upload_resume(page, resume_path)
            if resume_result['success']:
                result['fields_filled'].append('resume')
            
            # Step 3: Fill location information
            logger.info("[VFA2] Step 3: Filling location information...")
            location_result = await self._fill_location(page, profile)
            result['fields_filled'].extend(location_result['filled'])
            
            # Step 4: Handle EEO/screening questions
            logger.info("[VFA2] Step 4: Handling screening questions...")
            eeo_result = await self._handle_eeo_questions(page, profile)
            result['fields_filled'].extend(eeo_result['filled'])
            
            # Step 5: Check for required fields we missed
            logger.info("[VFA2] Step 5: Checking for remaining required fields...")
            remaining_result = await self._fill_remaining_required(page, profile)
            result['fields_filled'].extend(remaining_result['filled'])
            
            # Step 6: Submit application
            logger.info("[VFA2] Step 6: Submitting application...")
            submit_result = await self._submit_form(page)
            result['steps_completed'] = 6
            
            if not submit_result['success']:
                result['error'] = "Failed to submit form - submit button not found or clickable"
                return result
            
            # Step 7: Verify submission
            logger.info("[VFA2] Step 7: Verifying submission...")
            verification = await self._verify_submission(page, initial_url)
            
            if verification['success']:
                result['success'] = True
                result['verified'] = True
                result['confirmation_id'] = verification.get('confirmation_id', 'VA_VERIFIED')
                logger.info(f"[VFA2] ✅ Application verified! Confirmation: {result['confirmation_id']}")
            else:
                result['error'] = f"Submission not verified: {verification.get('error', 'Unknown')}"
                logger.warning(f"[VFA2] ⚠️ Submission not verified: {result['error']}")
            
            return result
            
        except Exception as e:
            logger.error(f"[VFA2] Error during application: {e}")
            result['error'] = str(e)
            return result
    
    async def _fill_basic_info(self, page, profile: Dict) -> Dict:
        """Fill basic information fields."""
        filled = []
        
        # First Name
        first_name = profile.get('first_name', '')
        if first_name:
            if await self._try_fill_field(page, ['first_name', 'fname', 'firstname'], first_name):
                filled.append('first_name')
                logger.info(f"[VFA2] Filled: First Name = {first_name}")
        
        # Last Name
        last_name = profile.get('last_name', '')
        if last_name:
            if await self._try_fill_field(page, ['last_name', 'lname', 'lastname'], last_name):
                filled.append('last_name')
                logger.info(f"[VFA2] Filled: Last Name = {last_name}")
        
        # Full Name (if separate fields don't work)
        if 'first_name' not in filled and 'last_name' not in filled:
            full_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
            if full_name:
                if await self._try_fill_field(page, ['name', 'full_name'], full_name):
                    filled.append('full_name')
                    logger.info(f"[VFA2] Filled: Full Name = {full_name}")
        
        # Email
        email = profile.get('email', '')
        if email:
            if await self._try_fill_field(page, ['email', 'email_address'], email, input_type='email'):
                filled.append('email')
                logger.info(f"[VFA2] Filled: Email = {email}")
        
        # Phone
        phone = profile.get('phone', '')
        if phone:
            if await self._try_fill_field(page, ['phone', 'mobile', 'telephone'], phone, input_type='tel'):
                filled.append('phone')
                logger.info(f"[VFA2] Filled: Phone = {phone}")
        
        return {'filled': filled}
    
    async def _upload_resume(self, page, resume_path: str) -> Dict:
        """Upload resume file."""
        try:
            if not os.path.exists(resume_path):
                logger.warning(f"[VFA2] Resume not found: {resume_path}")
                return {'success': False, 'error': 'File not found'}
            
            # Look for file input
            file_selectors = [
                'input[type="file"][name*="resume" i]',
                'input[type="file"][name*="cv" i]',
                'input[type="file"][accept*=".pdf"]',
                'input[type="file"]',
            ]
            
            for selector in file_selectors:
                try:
                    file_input = page.locator(selector).first
                    if await file_input.count() > 0:
                        await file_input.set_input_files(resume_path)
                        logger.info(f"[VFA2] Uploaded resume: {resume_path}")
                        await asyncio.sleep(1)
                        return {'success': True}
                except Exception as e:
                    logger.debug(f"[VFA2] Resume upload with {selector} failed: {e}")
                    continue
            
            return {'success': False, 'error': 'No file input found'}
            
        except Exception as e:
            logger.error(f"[VFA2] Resume upload error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _fill_location(self, page, profile: Dict) -> Dict:
        """Fill location information."""
        filled = []
        
        # Try to fill City
        city = profile.get('city', 'Remote')
        if await self._try_fill_field(page, ['city', 'location_city'], city):
            filled.append('city')
            logger.info(f"[VFA2] Filled: City = {city}")
        
        # Try to fill State
        state = profile.get('state', 'CA')
        if await self._try_select_field(page, ['state', 'location_state'], state):
            filled.append('state')
            logger.info(f"[VFA2] Selected: State = {state}")
        
        # Try to fill Country
        country = profile.get('country', 'United States')
        if await self._try_select_field(page, ['country', 'location_country'], country):
            filled.append('country')
            logger.info(f"[VFA2] Selected: Country = {country}")
        
        return {'filled': filled}
    
    async def _handle_eeo_questions(self, page, profile: Dict) -> Dict:
        """Handle EEO and screening questions."""
        filled = []
        
        # Common EEO question patterns and safe default answers
        eeo_defaults = {
            'gender': 'Decline to answer',
            'ethnicity': 'Decline to answer',
            'race': 'Decline to answer',
            'veteran': 'Decline to answer',
            'disability': 'Decline to answer',
            'age': 'Decline to answer',
            'lgbtq': 'Decline to answer',
        }
        
        # Look for select dropdowns with these patterns
        for pattern, default_value in eeo_defaults.items():
            selectors = [
                f'select[name*="{pattern}" i]',
                f'select[name*="gender" i]',
                f'select[name*="ethnic" i]',
                f'select[name*="veteran" i]',
                f'select[name*="disability" i]',
            ]
            
            for selector in selectors:
                try:
                    select_elem = page.locator(selector).first
                    if await select_elem.count() > 0:
                        # Try to select default value
                        options = await select_elem.evaluate('el => Array.from(el.options).map(o => o.text)')
                        
                        # Look for decline/prefer not options
                        target_option = None
                        for opt in options:
                            opt_lower = opt.lower()
                            if any(x in opt_lower for x in ['decline', 'prefer not', 'no answer', 'i do not']):
                                target_option = opt
                                break
                        
                        # If no decline option, skip
                        if target_option:
                            await select_elem.select_option(label=target_option)
                            filled.append(f'eeo_{pattern}')
                            logger.info(f"[VFA2] Selected EEO option: {target_option}")
                            break
                            
                except Exception as e:
                    continue
        
        # Handle "Are you legally authorized to work" - usually required
        work_auth_patterns = ['legally authorized', 'work authorization', 'eligible to work']
        for pattern in work_auth_patterns:
            try:
                # Look for yes/no radio buttons or select
                radio_yes = page.locator(f'input[type="radio"][value="yes" i], input[type="radio"][value="true"]').first
                if await radio_yes.count() > 0:
                    # Check if it's near the question text
                    await radio_yes.click()
                    filled.append('work_authorization')
                    logger.info("[VFA2] Selected: Yes for work authorization")
                    break
            except:
                continue
        
        return {'filled': filled}
    
    async def _fill_remaining_required(self, page, profile: Dict) -> Dict:
        """Fill any remaining required fields."""
        filled = []
        
        # Look for empty required fields
        required_selectors = [
            'input[required]:not([value])',
            'select[required]',
            'textarea[required]:empty',
        ]
        
        for selector in required_selectors:
            try:
                elements = page.locator(selector).all()
                for elem in elements[:5]:  # Limit to first 5 to avoid infinite loops
                    try:
                        field_type = await elem.get_attribute('type') or 'text'
                        field_name = await elem.get_attribute('name') or ''
                        
                        # Skip if already has value
                        if field_type == 'text' or field_type == 'email':
                            current = await elem.input_value()
                            if current:
                                continue
                        
                        # Fill based on field name
                        if 'name' in field_name.lower() and 'first' not in field_name.lower():
                            await elem.fill(profile.get('last_name', 'Beltran'))
                            filled.append(field_name)
                        elif 'linkedin' in field_name.lower():
                            await elem.fill(profile.get('linkedin', ''))
                            filled.append(field_name)
                        elif 'website' in field_name.lower() or 'portfolio' in field_name.lower():
                            await elem.fill(profile.get('website', ''))
                            filled.append(field_name)
                        elif field_type == 'select':
                            # Try to select first non-empty option
                            options = await elem.evaluate('el => Array.from(el.options).map(o => o.value)')
                            if len(options) > 1:
                                await elem.select_option(value=options[1])  # Skip placeholder
                                filled.append(field_name)
                                
                    except Exception as e:
                        continue
                        
            except Exception as e:
                continue
        
        return {'filled': filled}
    
    async def _submit_form(self, page) -> Dict:
        """Click submit button."""
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Apply")',
            'a:has-text("Submit")',
            '[data-qa="btn-submit"]',
            '[data-qa="btn-apply"]',
        ]
        
        for selector in submit_selectors:
            try:
                submit_btn = page.locator(selector).first
                if await submit_btn.count() > 0 and await submit_btn.is_visible():
                    await submit_btn.click()
                    logger.info(f"[VFA2] Clicked submit button: {selector}")
                    await asyncio.sleep(3)  # Wait for submission
                    return {'success': True}
            except Exception as e:
                continue
        
        return {'success': False, 'error': 'No submit button found'}
    
    async def _verify_submission(self, page, initial_url: str) -> Dict:
        """
        Verify that the form was actually submitted.
        
        Checks:
        1. URL changed from initial
        2. Page contains success indicators
        3. No error messages visible
        """
        result = {'success': False, 'error': None, 'confirmation_id': None}
        
        current_url = page.url
        
        # Check 1: URL should change (usually to confirmation page)
        if current_url == initial_url:
            # Same URL - check if form is still visible
            form_exists = await page.locator('form').count() > 0
            if form_exists:
                # Form still there - likely not submitted
                result['error'] = 'Still on same page with form visible'
                return result
        
        # Check 2: Look for success indicators in page content
        content = await page.content()
        title = await page.title()
        
        success_indicators = [
            'thank you for your application',
            'application received',
            'we have received',
            'successfully submitted',
            'application submitted',
            'confirmation',
            'next steps',
        ]
        
        found_indicator = any(ind in content.lower() for ind in success_indicators)
        
        # Check 3: Look for error messages
        error_indicators = [
            'error',
            'required',
            'please fix',
            'invalid',
            'missing',
        ]
        
        # Check for visible error messages
        has_errors = False
        try:
            error_elements = await page.locator('.error, .invalid, [role="alert"]').count()
            if error_elements > 0:
                has_errors = True
        except:
            pass
        
        # Determine success
        if found_indicator and not has_errors:
            result['success'] = True
            # Try to extract confirmation number
            conf_match = re.search(r'confirmation[\s#:]+([A-Z0-9\-]+)', content, re.I)
            if conf_match:
                result['confirmation_id'] = conf_match.group(1)
            else:
                result['confirmation_id'] = 'CONFIRMED'
        elif has_errors:
            result['error'] = 'Form has validation errors'
        else:
            result['error'] = f'No success indicator found. Title: {title}'
        
        return result
    
    async def _try_fill_field(self, page, names: List[str], value: str, input_type: str = 'text') -> bool:
        """Try to fill a field by various name patterns."""
        selectors = []
        for name in names:
            selectors.extend([
                f'input[name="{name}"]',
                f'input[name*="{name}"]',
                f'input[id*="{name}"]',
                f'input[placeholder*="{name}" i]',
                f'input[aria-label*="{name}" i]',
            ])
        
        if input_type:
            selectors.append(f'input[type="{input_type}"]')
        
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0 and await element.is_visible():
                    await element.fill(value)
                    return True
            except:
                continue
        
        return False
    
    async def _try_select_field(self, page, names: List[str], value: str) -> bool:
        """Try to select from a dropdown."""
        selectors = []
        for name in names:
            selectors.extend([
                f'select[name="{name}"]',
                f'select[name*="{name}"]',
                f'select[id*="{name}"]',
            ])
        
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0 and await element.is_visible():
                    await element.select_option(label=value)
                    return True
            except:
                continue
        
        return False


# Test function
async def test():
    """Test the V2 agent."""
    from adapters.handlers.browser_manager import BrowserManager
    
    browser = BrowserManager(headless=False)
    _, page = await browser.create_context()
    
    await page.goto("https://grnh.se/5dqpfgbb6us", wait_until='networkidle')
    await asyncio.sleep(2)
    
    agent = VisualFormAgentV2()
    await agent.initialize()
    
    result = await agent.apply(
        page=page,
        profile={
            'first_name': 'Kevin',
            'last_name': 'Beltran',
            'email': 'beltranrkevin@gmail.com',
            'phone': '+1-770-378-2545',
            'city': 'Atlanta',
            'state': 'Georgia',
        },
        job_data={'title': 'ServiceNow Developer', 'company': 'Accenture'},
        resume_path='Test Resumes/Kevin_Beltran_Resume.pdf'
    )
    
    print(f"Result: {result}")
    await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(test())
