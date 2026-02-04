"""
FIXED Validation System for Job Applications
Properly detects real submissions vs Cloudflare blocks
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict


class SubmissionValidatorFixed:
    """
    FIXED validator that properly distinguishes between:
    - Real successful submissions
    - Cloudflare/CAPTCHA blocks
    - Form errors
    - External redirects
    """
    
    # REAL success indicators - must be present for submission to count
    SUCCESS_PHRASES = [
        "application submitted",
        "application was submitted",
        "successfully submitted",
        "thank you for applying",
        "thank you for your application",
        "your application has been received",
        "we've received your application",
        "we have received your application",
        "application complete",
        "submitted successfully",
        "your application was sent",
        "we will review your application",
        "application confirmation",
        "your application is complete",
        "you have successfully applied",
    ]
    
    # Cloudflare/CAPTCHA indicators - if present, it's NOT a success
    CLOUDFLARE_INDICATORS = [
        "additional verification required",
        "ray id",
        "cloudflare",
        "checking your browser",
        "please wait",
        "verifying you are human",
        "ddos protection",
        "just a moment",
        "attention required",
        "captcha",
        "i'm not a robot",
        "verify you are human",
    ]
    
    # Error indicators - submission failed
    ERROR_INDICATORS = [
        "error occurred",
        "something went wrong",
        "failed to submit",
        "please try again",
        "required field",
        "invalid",
        "error:",
        "could not submit",
        "unexpected error",
        "fix the following errors",
        "submission failed",
        "an error has occurred",
    ]
    
    # URL patterns that indicate success
    SUCCESS_URL_PATTERNS = [
        "confirmation",
        "success",
        "thank-you",
        "thankyou",
        "applied",
        "complete",
        "submitted",
    ]
    
    @classmethod
    async def validate(
        cls,
        page,
        job_id: str,
        platform: str = "indeed",
        screenshot_dir: str = "/tmp/validated_submissions"
    ) -> Dict:
        """
        Properly validate a submission with strict checks.
        
        Returns:
            {
                'success': bool,  # TRUE only if real submission confirmed
                'message': str,
                'confirmation_id': Optional[str],
                'screenshot_path': str,
                'is_cloudflare': bool,  # NEW: explicit flag
                'is_error': bool,
            }
        """
        # Create directory
        save_dir = Path(screenshot_dir) / platform
        save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        screenshot_path = str(save_dir / f"{job_id}_{timestamp}.png")
        
        # Take screenshot
        try:
            await page.screenshot(path=screenshot_path, full_page=True)
        except Exception as e:
            screenshot_path = f"failed_{e}"
        
        # Get content and URL
        try:
            content = await page.content()
            content_lower = content.lower()
            current_url = page.url.lower()
        except Exception as e:
            return {
                'success': False,
                'message': f'Could not retrieve page content: {e}',
                'screenshot_path': screenshot_path,
                'is_cloudflare': False,
                'is_error': True,
            }
        
        # STEP 1: Check for Cloudflare/CAPTCHA (DEFINITE FAILURE)
        for indicator in cls.CLOUDFLARE_INDICATORS:
            if indicator in content_lower:
                return {
                    'success': False,
                    'message': f'BLOCKED: Cloudflare/CAPTCHA detected ({indicator})',
                    'screenshot_path': screenshot_path,
                    'is_cloudflare': True,
                    'is_error': True,
                    'confirmation_id': None,
                }
        
        # STEP 2: Check for explicit errors
        for error in cls.ERROR_INDICATORS:
            if error in content_lower:
                return {
                    'success': False,
                    'message': f'ERROR: {error}',
                    'screenshot_path': screenshot_path,
                    'is_cloudflare': False,
                    'is_error': True,
                    'confirmation_id': None,
                }
        
        # STEP 3: Check for REAL success indicators (REQUIRED)
        found_success = False
        matched_phrase = None
        for phrase in cls.SUCCESS_PHRASES:
            if phrase in content_lower:
                found_success = True
                matched_phrase = phrase
                break
        
        # STEP 4: Check URL for success patterns (supporting evidence)
        url_success = any(pattern in current_url for pattern in cls.SUCCESS_URL_PATTERNS)
        
        # STEP 5: Extract confirmation ID if present
        confirmation_id = cls._extract_confirmation_id(content)
        
        # STEP 6: FINAL DECISION - must have success phrase to pass
        if found_success:
            return {
                'success': True,
                'message': f'Submission confirmed: "{matched_phrase}"',
                'confirmation_id': confirmation_id,
                'screenshot_path': screenshot_path,
                'is_cloudflare': False,
                'is_error': False,
            }
        
        # If no success phrase found, it's NOT a submission
        # This is the KEY FIX - we don't assume success anymore
        return {
            'success': False,
            'message': 'NO SUCCESS INDICATOR: Page loaded but no confirmation message found',
            'screenshot_path': screenshot_path,
            'is_cloudflare': False,
            'is_error': True,
            'confirmation_id': None,
        }
    
    @classmethod
    def _extract_confirmation_id(cls, content: str) -> Optional[str]:
        """Extract confirmation/reference number."""
        patterns = [
            r'confirmation[\s#:]+([A-Z0-9-]{5,20})',
            r'reference[\s#:]+([A-Z0-9-]{5,20})',
            r'application[\s#:]+([A-Z0-9-]{6,20})',
            r'number[\s#:]+([A-Z0-9-]{5,20})',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    @classmethod
    def check_is_cloudflare_page(cls, content: str) -> bool:
        """Quick check if page is Cloudflare blocked."""
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in cls.CLOUDFLARE_INDICATORS)
