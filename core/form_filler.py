"""
Intelligent Form Filling Service

Eliminates duplicated field filling logic across 15+ adapter files.
Provides automatic field detection, smart matching, and validation.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable, Tuple
from enum import Enum
from playwright.async_api import Page

from adapters.base import UserProfile, Resume

logger = logging.getLogger(__name__)


class FillStrategy(Enum):
    """Strategies for form filling."""
    STANDARD = "standard"      # Fill standard fields only
    AGGRESSIVE = "aggressive"  # Try to fill everything
    CAUTIOUS = "cautious"      # Only fill clearly matched fields
    AI_ASSISTED = "ai"         # Use AI for unknown fields


@dataclass
class FieldMapping:
    """Maps a profile field to form selectors."""
    profile_field: str
    selectors: List[str]
    value_transform: Optional[Callable[[Any], str]] = None
    required: bool = False
    field_type: str = "text"  # text, email, tel, file, etc.


@dataclass
class DetectedField:
    """A field detected on a form."""
    selector: Optional[str]
    name: Optional[str]
    id: Optional[str]
    field_type: str
    input_type: Optional[str]
    label: str
    placeholder: str
    required: bool
    is_visible: bool
    options: List[str] = field(default_factory=list)  # For select/radio
    bounding_box: Optional[Dict[str, float]] = None
    
    @property
    def best_selector(self) -> Optional[str]:
        """Get the best available selector for this field."""
        if self.selector:
            return self.selector
        if self.id:
            return f"#{self.id}"
        if self.name:
            return f"[name='{self.name}']"
        return None


@dataclass
class FilledField:
    """Record of a filled field."""
    detected: DetectedField
    profile_field: str
    value: str
    success: bool
    error: Optional[str] = None


@dataclass
class FillResult:
    """Result of form filling operation."""
    filled: List[FilledField]
    detected_count: int
    filled_count: int
    failed_count: int
    validation: Dict[str, Any]
    
    @property
    def success_rate(self) -> float:
        if self.detected_count == 0:
            return 0.0
        return self.filled_count / self.detected_count


class FormFiller:
    """
    Intelligent form filling with automatic detection and matching.
    
    Replaces duplicated _fill_field methods in adapters.
    
    Usage:
        filler = FormFiller()
        
        # Define mappings for a platform
        mappings = {
            'first_name': FieldMapping('first_name', [
                '#first_name',
                'input[name="firstName"]',
                'input[placeholder*="First"]'
            ]),
            # ... more fields
        }
        
        # Fill the form
        result = await filler.fill_all(page, profile, mappings)
        
        if result.success_rate > 0.8:
            print("Form filled successfully!")
    """
    
    # Standard field mappings that work across most platforms
    STANDARD_MAPPINGS = {
        'first_name': FieldMapping(
            profile_field='first_name',
            selectors=[
                '#first_name',
                'input[name*="first"]',
                'input[placeholder*="First"]',
                'input[autocomplete="given-name"]',
                '[data-testid*="first"]',
            ],
            required=True
        ),
        'last_name': FieldMapping(
            profile_field='last_name',
            selectors=[
                '#last_name',
                'input[name*="last"]',
                'input[placeholder*="Last"]',
                'input[autocomplete="family-name"]',
                '[data-testid*="last"]',
            ],
            required=True
        ),
        'email': FieldMapping(
            profile_field='email',
            selectors=[
                '#email',
                'input[type="email"]',
                'input[name*="email"]',
                'input[autocomplete="email"]',
            ],
            field_type='email',
            required=True
        ),
        'phone': FieldMapping(
            profile_field='phone',
            selectors=[
                '#phone',
                'input[type="tel"]',
                'input[name*="phone"]',
                'input[name*="mobile"]',
                'input[name*="cell"]',
            ],
            field_type='tel'
        ),
        'linkedin_url': FieldMapping(
            profile_field='linkedin_url',
            selectors=[
                'input[name*="linkedin"]',
                'input[placeholder*="LinkedIn"]',
                'input[id*="linkedin"]',
            ]
        ),
        'website': FieldMapping(
            profile_field='website',
            selectors=[
                'input[name*="website"]',
                'input[name*="portfolio"]',
                'input[name*="url"]',
            ]
        ),
        'years_experience': FieldMapping(
            profile_field='years_experience',
            selectors=[
                'input[name*="experience"]',
                'input[name*="years"]',
                'select[name*="experience"]',
            ],
            value_transform=lambda x: str(x) if x else ""
        ),
    }
    
    def __init__(self, strategy: FillStrategy = FillStrategy.STANDARD):
        self.strategy = strategy
        self.filled_fields: List[FilledField] = []
    
    async def fill_all(
        self,
        page: Page,
        profile: UserProfile,
        mappings: Optional[Dict[str, FieldMapping]] = None,
        resume: Optional[Resume] = None
    ) -> FillResult:
        """
        Fill all detectable form fields.
        
        Args:
            page: Playwright page
            profile: User profile with data to fill
            mappings: Platform-specific field mappings (uses STANDARD_MAPPINGS if None)
            resume: Optional resume for file uploads
            
        Returns:
            FillResult with details of what was filled
        """
        self.filled_fields = []
        mappings = mappings or self.STANDARD_MAPPINGS
        
        # 1. Detect all fields on the page
        detected_fields = await self._detect_all_fields(page)
        logger.info(f"Detected {len(detected_fields)} form fields")
        
        # 2. Match detected fields to profile data
        matched_fields = self._match_fields(detected_fields, mappings, profile)
        
        # 3. Fill each matched field
        for detected, mapping in matched_fields:
            await self._fill_single_field(page, detected, mapping, profile)
        
        # 4. Handle resume upload if provided
        if resume:
            await self._upload_resume(page, resume)
        
        # 5. Validate the form
        validation = await self._validate_form(page, detected_fields)
        
        return FillResult(
            filled=self.filled_fields,
            detected_count=len(detected_fields),
            filled_count=sum(1 for f in self.filled_fields if f.success),
            failed_count=sum(1 for f in self.filled_fields if not f.success),
            validation=validation
        )
    
    async def _detect_all_fields(self, page: Page) -> List[DetectedField]:
        """Automatically detect all form fields on the page."""
        fields_data = await page.evaluate("""
            () => {
                const fields = [];
                const inputs = document.querySelectorAll('input, select, textarea');
                
                inputs.forEach((el) => {
                    // Skip hidden fields
                    if (el.type === 'hidden') return;
                    if (el.offsetParent === null && el.type !== 'file') return;
                    
                    // Get label
                    let label = '';
                    if (el.id) {
                        const labelEl = document.querySelector(`label[for="${el.id}"]`);
                        if (labelEl) label = labelEl.innerText;
                    }
                    if (!label && el.labels && el.labels.length > 0) {
                        label = el.labels[0].innerText;
                    }
                    if (!label) {
                        // Try parent or previous sibling
                        const parent = el.closest('label, .form-group, .field');
                        if (parent) {
                            const labelEl = parent.querySelector('label, .label, .field-label');
                            if (labelEl) label = labelEl.innerText;
                        }
                    }
                    
                    // Get options for select
                    let options = [];
                    if (el.tagName === 'SELECT') {
                        options = Array.from(el.options).map(o => ({
                            value: o.value,
                            text: o.text
                        }));
                    }
                    
                    // Get bounding box
                    const rect = el.getBoundingClientRect();
                    
                    fields.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type,
                        name: el.name,
                        id: el.id,
                        label: label.trim(),
                        placeholder: el.placeholder || '',
                        required: el.required,
                        is_visible: el.offsetParent !== null || el.type === 'file',
                        options: options,
                        bounding_box: {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height
                        }
                    });
                });
                
                return fields;
            }
        """)
        
        fields = []
        for data in fields_data:
            selector = None
            if data.get('id'):
                selector = f"#{data['id']}"
            elif data.get('name'):
                selector = f"[name='{data['name']}']"
            
            fields.append(DetectedField(
                selector=selector,
                name=data.get('name'),
                id=data.get('id'),
                field_type=data.get('tag', 'input'),
                input_type=data.get('type'),
                label=data.get('label', ''),
                placeholder=data.get('placeholder', ''),
                required=data.get('required', False),
                is_visible=data.get('is_visible', True),
                options=[o['text'] for o in data.get('options', [])],
                bounding_box=data.get('bounding_box')
            ))
        
        return fields
    
    def _match_fields(
        self,
        detected: List[DetectedField],
        mappings: Dict[str, FieldMapping],
        profile: UserProfile
    ) -> List[Tuple[DetectedField, FieldMapping]]:
        """Match detected fields to profile field mappings."""
        matched = []
        
        for field in detected:
            best_match = None
            best_score = 0
            
            for profile_field, mapping in mappings.items():
                score = self._calculate_match_score(field, mapping, profile)
                if score > best_score and score > 0.5:  # Threshold
                    best_score = score
                    best_match = mapping
            
            if best_match:
                matched.append((field, best_match))
        
        return matched
    
    def _calculate_match_score(
        self,
        field: DetectedField,
        mapping: FieldMapping,
        profile: UserProfile
    ) -> float:
        """Calculate how well a detected field matches a mapping."""
        score = 0.0
        field_text = f"{field.label} {field.name or ''} {field.placeholder or ''}".lower()
        
        # Check if mapping selectors match
        for selector in mapping.selectors:
            selector_clean = selector.lower().replace('#', '').replace('[', '').replace(']', '').replace('"', '')
            
            if field.id and field.id.lower() in selector_clean:
                score += 0.4
            if field.name and field.name.lower() in selector_clean:
                score += 0.4
            if any(kw in field_text for kw in selector_clean.split()):
                score += 0.2
        
        # Check label text
        profile_keywords = mapping.profile_field.lower().split('_')
        for keyword in profile_keywords:
            if keyword in field_text:
                score += 0.3
        
        # Check if we have a value for this field
        value = getattr(profile, mapping.profile_field, None)
        if value:
            score += 0.1
        
        return min(score, 1.0)
    
    async def _fill_single_field(
        self,
        page: Page,
        detected: DetectedField,
        mapping: FieldMapping,
        profile: UserProfile
    ) -> bool:
        """Fill a single form field."""
        selector = detected.best_selector
        if not selector:
            self.filled_fields.append(FilledField(
                detected=detected,
                profile_field=mapping.profile_field,
                value="",
                success=False,
                error="No selector available"
            ))
            return False
        
        # Get value from profile
        value = getattr(profile, mapping.profile_field, None)
        if value is None or value == "":
            self.filled_fields.append(FilledField(
                detected=detected,
                profile_field=mapping.profile_field,
                value="",
                success=False,
                error="No value in profile"
            ))
            return False
        
        # Apply transform if provided
        if mapping.value_transform:
            value = mapping.value_transform(value)
        else:
            value = str(value)
        
        # Fill based on field type
        try:
            element = page.locator(selector).first
            
            if await element.count() == 0:
                raise Exception("Element not found")
            
            if not await element.is_visible():
                raise Exception("Element not visible")
            
            # Handle different input types
            if detected.input_type in ['text', 'email', 'tel', 'url', 'number']:
                await element.fill(value)
            elif detected.input_type == 'textarea':
                await element.fill(value)
            elif detected.input_type == 'select-one' or detected.field_type == 'select':
                # Try to select by value or text
                try:
                    await element.select_option(value=value)
                except:
                    # Try by label
                    await element.select_option(label=value)
            elif detected.input_type == 'checkbox':
                # Handle boolean values
                is_checked = await element.is_checked()
                should_check = value.lower() in ['yes', 'true', '1']
                if is_checked != should_check:
                    await element.click()
            elif detected.input_type == 'file':
                # Handle file upload separately
                pass
            else:
                await element.fill(value)
            
            self.filled_fields.append(FilledField(
                detected=detected,
                profile_field=mapping.profile_field,
                value=value[:50],  # Truncate for logging
                success=True
            ))
            
            logger.debug(f"Filled {mapping.profile_field}: {value[:30]}...")
            return True
            
        except Exception as e:
            self.filled_fields.append(FilledField(
                detected=detected,
                profile_field=mapping.profile_field,
                value=value[:50],
                success=False,
                error=str(e)
            ))
            
            logger.warning(f"Failed to fill {mapping.profile_field}: {e}")
            return False
    
    async def _upload_resume(self, page: Page, resume: Resume) -> bool:
        """Upload resume file."""
        file_selectors = [
            'input[type="file"]',
            'input[name*="resume"]',
            'input[name*="cv"]',
            'input[name*="attachment"]',
        ]
        
        for selector in file_selectors:
            try:
                file_input = page.locator(selector).first
                if await file_input.count() > 0 and await file_input.is_visible():
                    await file_input.set_input_files(resume.file_path)
                    logger.info(f"Resume uploaded: {resume.file_path}")
                    
                    # Wait for upload to complete
                    await asyncio.sleep(2)
                    return True
            except Exception as e:
                logger.debug(f"Resume upload failed for {selector}: {e}")
                continue
        
        return False
    
    async def _validate_form(self, page: Page, detected_fields: List[DetectedField]) -> Dict[str, Any]:
        """Validate that the form is properly filled."""
        required_fields = [f for f in detected_fields if f.required]
        
        validation = {
            "total_fields": len(detected_fields),
            "required_fields": len(required_fields),
            "filled_required": 0,
            "missing_required": [],
            "errors": []
        }
        
        for field in required_fields:
            # Check if this field was successfully filled
            filled = next(
                (f for f in self.filled_fields 
                 if f.detected.best_selector == field.best_selector and f.success),
                None
            )
            
            if filled:
                validation["filled_required"] += 1
            else:
                validation["missing_required"].append({
                    "label": field.label,
                    "selector": field.best_selector
                })
        
        # Check for validation errors on the page
        error_selectors = [
            '.error-message',
            '.validation-error',
            '[role="alert"]',
            '.field-error'
        ]
        
        for selector in error_selectors:
            try:
                errors = await page.locator(selector).all()
                for error in errors:
                    if await error.is_visible():
                        text = await error.inner_text()
                        if text:
                            validation["errors"].append(text.strip())
            except:
                pass
        
        return validation
    
    def get_fill_summary(self) -> str:
        """Get a summary of the fill operation."""
        successful = sum(1 for f in self.filled_fields if f.success)
        failed = sum(1 for f in self.filled_fields if not f.success)
        
        summary = f"Form Filling Summary: {successful} successful, {failed} failed\n"
        
        if failed > 0:
            summary += "\nFailed fields:\n"
            for field in self.filled_fields:
                if not field.success:
                    summary += f"  - {field.profile_field}: {field.error}\n"
        
        return summary
