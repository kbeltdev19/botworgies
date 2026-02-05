"""
Shared validation utilities for job application adapters.
Provides screenshot capture and success/failure detection.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional


class SubmissionValidator:
    """Validates job application submissions across all platforms."""
    
    # Success indicators by platform type
    SUCCESS_INDICATORS = {
        "indeed": [
            "application submitted",
            "successfully submitted",
            "thank you for applying",
            "your application has been received",
            "we've received your application",
            "application complete",
            "submitted successfully",
            "thank you for your interest",
            "we will review your application",
            "your application was sent",
            "confirmation",
        ],
        "greenhouse": [
            "application submitted",
            "thank you for applying",
            "we have received your application",
            "your application has been received",
        ],
        "lever": [
            "application submitted",
            "thank you for your application",
            "we've received your application",
        ],
        "workday": [
            "application submitted",
            "thank you",
            "your application has been submitted",
            "success",
        ],
        "ashby": [
            "submitted",
            "thank you",
            "application received",
        ],
        "linkedin": [
            "application sent",
            "successfully applied",
            "your application was sent",
        ],
        "ziprecruiter": [
            "application submitted",
            "success",
            "thank you",
        ],
        "generic": [
            "application submitted",
            "thank you for applying",
            "successfully submitted",
            "your application has been received",
            "we will review",
            "confirmation",
            "success",
            "submitted",
        ]
    }
    
    # Error indicators (universal)
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
    ]
    
    # URL patterns indicating success
    SUCCESS_URL_PATTERNS = [
        "confirmation", "success", "thank-you", "thankyou",
        "applied", "complete", "submitted", "done"
    ]
    
    @classmethod
    async def validate(
        cls,
        page,
        job_id: str,
        platform: str = "generic",
        screenshot_dir: str = "/tmp/submissions"
    ) -> dict:
        """
        Validate a submission by checking page content and URL.
        
        Args:
            page: Playwright page object
            job_id: Unique job identifier
            platform: Platform type (indeed, greenhouse, etc.)
            screenshot_dir: Directory to save screenshots
            
        Returns:
            dict with success status, message, confirmation_id, screenshot_path
        """
        # Create directory and screenshot path
        save_dir = Path(screenshot_dir) / platform
        save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        screenshot_path = str(save_dir / f"{job_id}_{timestamp}.png")
        
        # Take screenshot
        try:
            await page.screenshot(path=screenshot_path, full_page=True)
        except Exception as e:
            screenshot_path = None
        
        # Get page content and URL
        try:
            content = await page.content()
            content_lower = content.lower()
            current_url = page.url.lower()
        except:
            return {
                'success': False,
                'message': 'Could not retrieve page content for validation',
                'screenshot_path': screenshot_path
            }
        
        # Check for errors first (priority)
        found_errors = [e for e in cls.ERROR_INDICATORS if e in content_lower]
        if found_errors:
            return {
                'success': False,
                'message': f"Error indicators: {', '.join(found_errors[:2])}",
                'screenshot_path': screenshot_path
            }
        
        # Check for success indicators
        indicators = cls.SUCCESS_INDICATORS.get(platform, cls.SUCCESS_INDICATORS["generic"])
        found_success = [s for s in indicators if s in content_lower]
        
        # Check URL for success patterns
        url_success = any(p in current_url for p in cls.SUCCESS_URL_PATTERNS)
        
        # Extract confirmation ID
        confirmation_id = cls._extract_confirmation_id(content)
        
        # Determine result
        if found_success or url_success:
            return {
                'success': True,
                'message': found_success[0] if found_success else "URL indicates success",
                'confirmation_id': confirmation_id,
                'screenshot_path': screenshot_path
            }
        
        # Check if form still present (failure indicator)
        form_present = await cls._check_form_present(page)
        if form_present:
            return {
                'success': False,
                'message': "Form still present after submission attempt",
                'screenshot_path': screenshot_path
            }
        
        # Ambiguous - page changed but no clear indicators
        return {
            'success': True,
            'message': "Submission assumed successful (page navigated)",
            'confirmation_id': confirmation_id,
            'screenshot_path': screenshot_path
        }
    
    # False positive patterns to exclude
    FALSE_POSITIVES = ['window', 'document', 'function', 'var', 'const', 'let', 
                       'return', 'typeof', 'undefined', 'prototype', 'constructor',
                       'length', 'width', 'height', 'parent', 'children']
    
    @classmethod
    def _extract_confirmation_id(cls, content: str) -> Optional[str]:
        """Try to extract confirmation/reference ID from page content."""
        patterns = [
            r'confirmation[\s#:]+([A-Z0-9-]{5,})',
            r'reference[\s#:]+([A-Z0-9-]{5,})',
            r'application[\s#:]+([A-Z0-9-]{6,})',
            r'id[\s#:]+([A-Z0-9-]{6,})',
            r'number[\s#:]+([A-Z0-9-]{5,})',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                candidate = match.group(1)
                # Filter out common false positives
                if candidate.lower() not in cls.FALSE_POSITIVES:
                    return candidate
        return None
    
    @classmethod
    async def _check_form_present(cls, page) -> bool:
        """Check if a form is still present on the page."""
        form_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'form',
            '#indeedApplyButton',
            '.apply-button',
        ]
        for selector in form_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except:
                continue
        return False
