"""
Platform-Specific Field Mappings

Defines selectors and field names for each job board and ATS platform.
Used by the application automation to correctly fill forms.
"""

from typing import Dict, List, Optional


class FieldMappings:
    """
    Field selectors and mappings for different job platforms.
    
    Each platform has its own HTML structure and field naming conventions.
    These mappings allow the automation to correctly identify and fill fields.
    """
    
    # Standard form field types
    FIELD_TYPES = [
        'first_name',
        'last_name',
        'email',
        'phone',
        'address',
        'city',
        'state',
        'zip',
        'country',
        'linkedin',
        'portfolio',
        'resume',
        'cover_letter',
        'salary_expectation',
        'start_date',
        'clearance_level',
    ]
    
    # Platform-specific field mappings
    MAPPINGS: Dict[str, Dict[str, List[str]]] = {
        # ===== GREENHOUSE =====
        'greenhouse': {
            'first_name': [
                '#first_name',
                'input[name="first_name"]',
                'input[autocomplete="given-name"]',
            ],
            'last_name': [
                '#last_name',
                'input[name="last_name"]',
                'input[autocomplete="family-name"]',
            ],
            'email': [
                '#email',
                'input[name="email"]',
                'input[type="email"]',
                'input[autocomplete="email"]',
            ],
            'phone': [
                '#phone',
                'input[name="phone"]',
                'input[type="tel"]',
                'input[autocomplete="tel"]',
            ],
            'resume': [
                '#resume',
                'input[name="resume"]',
                'input[type="file"][accept*=".pdf"]',
            ],
            'cover_letter': [
                '#cover_letter',
                'textarea[name="cover_letter"]',
            ],
            'linkedin': [
                '#job_application[linkedin_url]',
                'input[name*="linkedin"]',
            ],
            'portfolio': [
                '#job_application[website]',
                'input[name*="website"]',
                'input[name*="portfolio"]',
            ],
            'submit': [
                'input[type="submit"]',
                'button[type="submit"]',
                '#submit_app',
                '.apply-button',
            ],
        },
        
        # ===== LEVER =====
        'lever': {
            'first_name': [
                'input[name="name[first]"]',
                'input[placeholder*="First" i]',
                'input[data-field="first-name"]',
            ],
            'last_name': [
                'input[name="name[last]"]',
                'input[placeholder*="Last" i]',
                'input[data-field="last-name"]',
            ],
            'email': [
                'input[name="email"]',
                'input[type="email"]',
            ],
            'phone': [
                'input[name="phone"]',
                'input[type="tel"]',
            ],
            'resume': [
                'input[name="resume"]',
                'input[data-field="resume"]',
                'input[type="file"][accept*="pdf"]',
            ],
            'cover_letter': [
                'input[name="coverLetter"]',
                'textarea[name="coverLetter"]',
            ],
            'linkedin': [
                'input[name="urls[LinkedIn]"]',
                'input[data-field="linkedin"]',
            ],
            'portfolio': [
                'input[name="urls[Portfolio]"]',
                'input[name="urls[Other]"]',
            ],
            'submit': [
                'button[type="submit"]',
                '.postings-btn.template-btn-submit',
            ],
        },
        
        # ===== WORKDAY =====
        'workday': {
            'first_name': [
                'input[data-automation-id="firstName"]',
                'input[name="firstName"]',
                'input[placeholder*="First" i]',
            ],
            'last_name': [
                'input[data-automation-id="lastName"]',
                'input[name="lastName"]',
                'input[placeholder*="Last" i]',
            ],
            'email': [
                'input[data-automation-id="email"]',
                'input[name="email"]',
                'input[type="email"]',
            ],
            'phone': [
                'input[data-automation-id="phone"]',
                'input[name="phone"]',
            ],
            'resume': [
                'input[data-automation-id="file-upload-input"]',
                'input[type="file"][accept*="pdf"]',
            ],
            'cover_letter': [
                'textarea[data-automation-id="coverLetter"]',
            ],
            'linkedin': [
                'input[data-automation-id="linkedin"]',
            ],
            'submit': [
                'button[data-automation-id="submit"]',
                'button[title="Submit Application"]',
            ],
        },
        
        # ===== ASHBY =====
        'ashby': {
            'first_name': [
                'input[name="firstName"]',
                'input[placeholder*="First" i]',
            ],
            'last_name': [
                'input[name="lastName"]',
                'input[placeholder*="Last" i]',
            ],
            'email': [
                'input[name="email"]',
                'input[type="email"]',
            ],
            'phone': [
                'input[name="phone"]',
            ],
            'resume': [
                'input[name="resume"]',
                'input[type="file"]',
            ],
            'submit': [
                'button[type="submit"]',
                'button:has-text("Submit Application")',
            ],
        },
        
        # ===== CLEARANCEJOBS =====
        'clearancejobs': {
            'first_name': [
                'input[name="first_name"]',
                'input[id="firstName"]',
                'input[placeholder*="First" i]',
            ],
            'last_name': [
                'input[name="last_name"]',
                'input[id="lastName"]',
                'input[placeholder*="Last" i]',
            ],
            'email': [
                'input[name="email"]',
                'input[type="email"]',
            ],
            'phone': [
                'input[name="phone"]',
                'input[type="tel"]',
            ],
            'clearance_level': [
                'select[name="clearance_level"]',
                'select[id="clearanceLevel"]',
                'input[name="clearance_level"]',
            ],
            'resume': [
                'input[name="resume"]',
                'input[type="file"][accept*=".docx"]',
                'input[type="file"][accept*=".pdf"]',
            ],
            'cover_letter': [
                'textarea[name="cover_letter"]',
            ],
            'submit': [
                'button[type="submit"]',
                'input[type="submit"]',
                '.apply-button',
            ],
        },
        
        # ===== DICE =====
        'dice': {
            'first_name': [
                'input[name="firstName"]',
                'input[id="firstName"]',
            ],
            'last_name': [
                'input[name="lastName"]',
                'input[id="lastName"]',
            ],
            'email': [
                'input[name="email"]',
                'input[type="email"]',
            ],
            'phone': [
                'input[name="phone"]',
            ],
            'resume': [
                'input[name="resume"]',
                'input[type="file"]',
            ],
            'skills': [
                'input[name="skills"]',
                'input[placeholder*="Skills" i]',
            ],
            'submit': [
                'button[type="submit"]',
                '.apply-button',
                'button:has-text("Apply")',
            ],
        },
        
        # ===== INDEED =====
        'indeed': {
            'first_name': [
                'input[name="firstName"]',
                'input[id="first-name"]',
            ],
            'last_name': [
                'input[name="lastName"]',
                'input[id="last-name"]',
            ],
            'email': [
                'input[name="email"]',
                'input[type="email"]',
            ],
            'phone': [
                'input[name="phone"]',
                'input[id="phone"]',
            ],
            'resume': [
                'input[name="resume"]',
                'input[type="file"]',
            ],
            'submit': [
                'button[type="submit"]',
                '.ia-SubmitButton',
                'button:has-text("Submit")',
            ],
        },
        
        # ===== SMARTRECRUITERS =====
        'smartrecruiters': {
            'first_name': [
                'input[name="firstName"]',
                'input[autocomplete="given-name"]',
            ],
            'last_name': [
                'input[name="lastName"]',
                'input[autocomplete="family-name"]',
            ],
            'email': [
                'input[name="email"]',
                'input[type="email"]',
            ],
            'resume': [
                'input[name="resume"]',
                'input[type="file"]',
            ],
            'submit': [
                'button[type="submit"]',
            ],
        },
        
        # ===== BAMBOOHR =====
        'bamboohr': {
            'first_name': [
                'input[name="firstName"]',
            ],
            'last_name': [
                'input[name="lastName"]',
            ],
            'email': [
                'input[name="email"]',
            ],
            'resume': [
                'input[name="resume"]',
            ],
            'submit': [
                'button[type="submit"]',
            ],
        },
    }
    
    @classmethod
    def get_selectors(cls, platform: str, field_type: str) -> List[str]:
        """Get selectors for a specific platform and field type."""
        platform_mappings = cls.MAPPINGS.get(platform.lower(), {})
        return platform_mappings.get(field_type, [])
        
    @classmethod
    def get_all_field_types(cls) -> List[str]:
        """Get all supported field types."""
        return cls.FIELD_TYPES.copy()
        
    @classmethod
    def get_supported_platforms(cls) -> List[str]:
        """Get all supported platforms."""
        return list(cls.MAPPINGS.keys())
        
    @classmethod
    def has_mapping(cls, platform: str, field_type: str) -> bool:
        """Check if a mapping exists for platform and field type."""
        return bool(cls.get_selectors(platform, field_type))


# Custom field handlers for special cases
class CustomFieldHandlers:
    """Handlers for non-standard form fields."""
    
    @staticmethod
    def handle_clearance_level(page, level: str) -> bool:
        """
        Handle clearance level dropdown on ClearanceJobs.
        
        Args:
            page: Playwright page object
            level: Clearance level string (e.g., "Secret", "TS/SCI")
            
        Returns:
            True if field was filled successfully
        """
        try:
            # Map common clearance levels to option values
            level_mapping = {
                'secret': ['Secret', 'SECRET', 'S'],
                'top secret': ['Top Secret', 'TOP SECRET', 'TS'],
                'ts/sci': ['TS/SCI', 'TS-SCI', 'Top Secret/SCI'],
                'ts/sci with polygraph': ['TS/SCI with Poly', 'TS/SCI Poly', 'Full Scope'],
                'public trust': ['Public Trust', 'PT'],
            }
            
            level_lower = level.lower()
            search_terms = level_mapping.get(level_lower, [level])
            
            # Try to find and select the option
            select_locator = page.locator('select[name*="clearance"]').first
            if select_locator.count() > 0:
                options = select_locator.locator('option').all_text_contents()
                
                for option_text in options:
                    for term in search_terms:
                        if term.lower() in option_text.lower():
                            select_locator.select_option(label=option_text.strip())
                            return True
                            
            return False
            
        except Exception:
            return False
            
    @staticmethod
    def handle_dice_skills(page, skills: List[str]) -> bool:
        """
        Handle skills input on Dice (usually tag-based).
        
        Args:
            page: Playwright page object
            skills: List of skill strings
            
        Returns:
            True if skills were added successfully
        """
        try:
            skills_input = page.locator('input[name*="skill"], input[placeholder*="Skill"]').first
            
            if skills_input.count() > 0:
                for skill in skills[:5]:  # Limit to top 5 skills
                    skills_input.fill(skill)
                    skills_input.press('Enter')
                    page.wait_for_timeout(300)
                    
                return True
                
            return False
            
        except Exception:
            return False


# Export
__all__ = ['FieldMappings', 'CustomFieldHandlers']
