"""
Generic Field Mapper - Universal field detector for all ATS platforms
Uses DOM analysis and heuristic scoring
"""

import re
import os
import random
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from .models import FieldMapping, UserProfile


class GenericFieldMapper:
    """
    Universal field detector that works across all ATS platforms
    Uses DOM analysis + heuristic scoring
    """
    
    # Field detection patterns (field_type: [regex_patterns])
    FIELD_PATTERNS = {
        'first_name': [
            r'first\s*name', r'fname', r'first-name', r'given\s*name',
            r'legal\s*first', r'preferred\s*first', r'first\s*name',
            r'^first$', r'first_name'
        ],
        'last_name': [
            r'last\s*name', r'lname', r'last-name', r'surname', r'family\s*name',
            r'legal\s*last', r'preferred\s*last', r'^last$', r'last_name'
        ],
        'email': [
            r'e[-]?mail', r'email\s*address', r'contact\s*email', r'^email$',
            r'email', r'correo'
        ],
        'phone': [
            r'phone', r'mobile', r'cell', r'telephone', r'contact\s*number',
            r'primary\s*phone', r'phone\s*number', r'^phone$'
        ],
        'resume': [
            r'resume', r'cv', r'curriculum\s*vitae', r'upload\s*resume',
            r'attach\s*resume', r'upload\s*cv', r'resume\s*upload',
            r'file.*resume', r'resume.*file'
        ],
        'cover_letter': [
            r'cover\s*letter', r'coverletter', r'cover\s*note',
            r'message\s*to\s*hiring', r'introduction', r'cover',
            r'letter.*interest'
        ],
        'linkedin': [
            r'linkedin', r'linked\s*in', r'linkedin\s*profile', r'linkedin\s*url',
            r'linkedin.*profile', r'profile.*linkedin'
        ],
        'website': [
            r'website', r'portfolio', r'personal\s*site', r'personal\s*website',
            r'github', r'blog', r'^website$', r'^url$'
        ],
        'salary_expectation': [
            r'salary', r'compensation', r'pay\s*expectation', r'desired\s*pay',
            r'expected\s*salary', r'pay\s*range', r'salary\s*expectation',
            r'desired\s*salary', r'pay\s*requirement'
        ],
        'start_date': [
            r'start\s*date', r'availability', r'when\s*can\s*you\s*start',
            r'notice\s*period', r'earliest\s*start', r'available\s*to\s*start'
        ],
        'referral_source': [
            r'how\s*did\s*you\s*hear', r'source', r'referral', r'referred\s*by',
            r'how\s*did\s*you\s*find', r'hear\s*about', r'learned\s*about'
        ],
        'work_authorization': [
            r'work\s*authorization', r'authorized\s*to\s*work', r'sponsorship',
            r'visa', r'work\s*status', r'legally\s*authorized', r'work\s*permit'
        ],
        'gender': [
            r'gender', r'sex', r'male\s*female', r'^gender$'
        ],
        'race': [
            r'race', r'ethnicity', r'demographic', r'eeo', r'racial'
        ],
        'veteran_status': [
            r'veteran', r'military\s*status', r'armed\s*forces'
        ],
        'disability': [
            r'disability', r'accommodation', r'disabled'
        ],
        'address': [
            r'address', r'street', r'city', r'state', r'zip', r'postal',
            r'location', r'country'
        ],
        'github': [
            r'github', r'git\s*hub', r'^github$', r'github.*profile'
        ]
    }
    
    def __init__(self, page, user_profile: UserProfile, ai_client=None):
        self.page = page
        self.profile = user_profile
        self.ai_client = ai_client
    
    async def analyze_page(self) -> List[FieldMapping]:
        """
        Main entry point: scan entire page and return fillable fields
        """
        mappings = []
        
        # Find all interactive elements
        try:
            elements = await self.page.query_selector_all(
                'input:not([type="hidden"]), select, textarea, '
                '[role="combobox"], [role="listbox"], '
                '[contenteditable="true"]'
            )
        except Exception as e:
            print(f"Error finding elements: {e}")
            return mappings
        
        for element in elements:
            try:
                mapping = await self._analyze_element(element)
                if mapping:
                    mappings.append(mapping)
            except Exception as e:
                print(f"Error analyzing element: {e}")
                continue
        
        return self._prioritize_mappings(mappings)
    
    async def _analyze_element(self, element) -> Optional[FieldMapping]:
        """Analyze single form element"""
        try:
            # Extract all possible identifiers using JavaScript
            info = await self.page.evaluate("""(el) => {
                const getLabelText = (input) => {
                    // Check for explicit label
                    if (input.labels && input.labels.length > 0) {
                        return input.labels[0].innerText.trim();
                    }
                    
                    // Check aria-labelledby
                    const labelledBy = input.getAttribute('aria-labelledby');
                    if (labelledBy) {
                        const labelEl = document.getElementById(labelledBy);
                        if (labelEl) return labelEl.innerText.trim();
                    }
                    
                    // Check aria-label
                    const ariaLabel = input.getAttribute('aria-label');
                    if (ariaLabel) return ariaLabel.trim();
                    
                    // Check parent label
                    let parent = input.parentElement;
                    for (let i = 0; i < 3 && parent; i++) {
                        if (parent.tagName === 'LABEL') {
                            return parent.innerText.trim();
                        }
                        parent = parent.parentElement;
                    }
                    
                    return '';
                };
                
                // Get surrounding text context
                const getContext = (el) => {
                    let context = '';
                    let parent = el.parentElement;
                    for (let i = 0; i < 2 && parent; i++) {
                        context += ' ' + parent.innerText;
                        parent = parent.parentElement;
                    }
                    return context.substring(0, 500).trim();
                };
                
                return {
                    tag: el.tagName.toLowerCase(),
                    type: el.type || 'text',
                    name: el.name || '',
                    id: el.id || '',
                    placeholder: el.placeholder || '',
                    ariaLabel: el.getAttribute('aria-label') || '',
                    ariaLabelledBy: el.getAttribute('aria-labelledby') || '',
                    autoComplete: el.getAttribute('autocomplete') || '',
                    required: el.required || false,
                    classList: Array.from(el.classList).join(' '),
                    labelText: getLabelText(el),
                    surroundingText: getContext(el),
                    dataAutomationId: el.getAttribute('data-automation-id') || '',
                    dataTestId: el.getAttribute('data-testid') || '',
                    dataField: el.getAttribute('data-field') || '',
                    dataQa: el.getAttribute('data-qa') || ''
                };
            }""", element)
            
            # Combine all text for pattern matching
            search_text = ' '.join([
                info['name'], info['id'], info['placeholder'], 
                info['ariaLabel'], info['labelText'], info['surroundingText'],
                info['dataAutomationId'], info['dataTestId'], info['dataField'],
                info['dataQa'], info['classList']
            ]).lower()
            
            # Determine field type
            field_type = self._classify_field(search_text, info)
            if not field_type:
                return None
            
            # Determine fill strategy
            strategy = self._determine_strategy(info, field_type)
            
            # Get value from profile
            value = self._get_profile_value(field_type)
            
            # Calculate confidence
            confidence = self._calculate_confidence(info, field_type)
            
            # Build selector
            selector = self._build_selector(info)
            
            return FieldMapping(
                field_type=field_type,
                selector=selector,
                fill_strategy=strategy,
                value=value,
                confidence=confidence,
                required=info['required'],
                question_text=info['labelText'] or info['placeholder']
            )
            
        except Exception as e:
            print(f"Error in _analyze_element: {e}")
            return None
    
    def _classify_field(self, search_text: str, info: Dict) -> Optional[str]:
        """Classify field using patterns"""
        # Check each field type patterns
        for field_type, patterns in self.FIELD_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, search_text, re.IGNORECASE):
                    return field_type
        
        # Special handling for custom questions
        if info['tag'] == 'textarea':
            return 'custom_text_long'
        elif info['tag'] == 'input' and info['type'] in ['text', 'email', 'tel', 'url']:
            # Check if it's a long field
            if 'message' in search_text or 'description' in search_text or 'essay' in search_text:
                return 'custom_text_long'
            return 'custom_text_short'
        elif info['tag'] == 'select':
            return 'custom_select'
        
        return None
    
    def _determine_strategy(self, info: Dict, field_type: str) -> str:
        """Determine how to fill this field"""
        tag = info['tag']
        input_type = info['type']
        
        if tag == 'select' or info.get('role') == 'combobox':
            return 'select'
        elif input_type == 'checkbox':
            return 'checkbox'
        elif input_type == 'radio':
            return 'radio'
        elif input_type == 'file':
            return 'upload'
        elif field_type == 'cover_letter':
            return 'ai_generate'
        elif field_type in ['custom_text_long']:
            return 'ai_generate'
        elif field_type in ['custom_text_short', 'custom_select']:
            return 'type'
        else:
            return 'type'
    
    def _get_profile_value(self, field_type: str) -> Any:
        """Extract value from user profile"""
        mapping = {
            'first_name': self.profile.first_name,
            'last_name': self.profile.last_name,
            'email': self.profile.email,
            'phone': self.profile.phone,
            'resume': self.profile.resume_path,
            'linkedin': self.profile.linkedin_url or '',
            'website': self.profile.portfolio_url or self.profile.github_url or '',
            'github': self.profile.github_url or '',
            'salary_expectation': self.profile.salary_expectation or 'Negotiable',
            'start_date': 'Immediately',
            'referral_source': 'Company Website',
            'work_authorization': 'Authorized to work in US',
            'cover_letter': None,
            'gender': 'Prefer not to say',
            'race': 'Prefer not to say',
            'veteran_status': 'Prefer not to say',
            'disability': 'Prefer not to say',
            'address': '',
            'custom_text_short': '',
            'custom_text_long': '',
            'custom_select': ''
        }
        
        return mapping.get(field_type)
    
    def _calculate_confidence(self, info: Dict, field_type: str) -> float:
        """Calculate confidence score 0.0-1.0"""
        score = 0.5
        
        # Boost if has label
        if info['labelText']:
            score += 0.25
        
        # Boost if required field (usually more clearly marked)
        if info['required']:
            score += 0.1
        
        # Boost if has autocomplete attribute
        if info['autoComplete']:
            score += 0.15
        
        # Boost if has data attributes (modern ATS)
        if info['dataAutomationId'] or info['dataTestId']:
            score += 0.1
        
        # Reduce if conflicting indicators
        if field_type.startswith('custom_') and info['required']:
            score -= 0.15
        
        return min(max(score, 0.0), 1.0)
    
    def _build_selector(self, info: Dict) -> str:
        """Build robust CSS selector for element"""
        # Priority order for selector building
        if info['id']:
            return f"#{info['id']}"
        
        if info['dataAutomationId']:
            return f"[data-automation-id='{info['dataAutomationId']}']"
        
        if info['dataTestId']:
            return f"[data-testid='{info['dataTestId']}']"
        
        if info['dataQa']:
            return f"[data-qa='{info['dataQa']}']"
        
        if info['dataField']:
            return f"[data-field='{info['dataField']}']"
        
        if info['name']:
            return f"{info['tag']}[name='{info['name']}']"
        
        if info['placeholder']:
            return f"{info['tag']}[placeholder='{info['placeholder']}']"
        
        if info['ariaLabel']:
            return f"{info['tag']}[aria-label='{info['ariaLabel']}']"
        
        # Fallback to xpath-like selector using attributes
        classes = info['classList'].replace(' ', '.')
        if classes:
            return f"{info['tag']}.{classes}"
        
        return info['tag']
    
    def _prioritize_mappings(self, mappings: List[FieldMapping]) -> List[FieldMapping]:
        """Sort by confidence and required status"""
        return sorted(mappings, key=lambda x: (x.required, x.confidence), reverse=True)
    
    async def fill_all_fields(
        self, 
        mappings: List[FieldMapping], 
        min_confidence: float = 0.4
    ) -> int:
        """
        Execute filling on all mapped fields
        
        Returns number of fields successfully filled
        """
        filled_count = 0
        
        for mapping in mappings:
            if mapping.confidence < min_confidence:
                print(f"Skipping low confidence field: {mapping.field_type} ({mapping.confidence:.2f})")
                continue
            
            try:
                success = await self._execute_fill(mapping)
                if success:
                    filled_count += 1
                
                # Random delay between fields (human-like)
                await asyncio.sleep(random.uniform(0.8, 2.5))
                
            except Exception as e:
                print(f"Failed to fill {mapping.field_type}: {e}")
                continue
        
        return filled_count
    
    async def _execute_fill(self, mapping: FieldMapping) -> bool:
        """Execute single field fill based on strategy"""
        try:
            element = await self.page.query_selector(mapping.selector)
            if not element:
                print(f"Element not found: {mapping.selector}")
                return False
            
            # Check if visible and enabled
            if not await element.is_visible():
                return False
            
            if mapping.fill_strategy == 'type':
                await element.fill(str(mapping.value or ''))
                
            elif mapping.fill_strategy == 'select':
                # Try by label first, then by value
                try:
                    await element.select_option(label=str(mapping.value))
                except:
                    await element.select_option(value=str(mapping.value))
                
            elif mapping.fill_strategy == 'upload':
                if mapping.value and os.path.exists(str(mapping.value)):
                    await element.set_input_files(str(mapping.value))
                    await asyncio.sleep(2)  # Wait for upload
                
            elif mapping.fill_strategy == 'checkbox':
                is_checked = await element.is_checked()
                should_check = str(mapping.value).lower() in ['yes', 'true', '1', 'on']
                
                if should_check and not is_checked:
                    await element.check()
                elif not should_check and is_checked:
                    await element.uncheck()
                
            elif mapping.fill_strategy == 'radio':
                await element.click()
            
            elif mapping.fill_strategy == 'ai_generate':
                if mapping.field_type == 'cover_letter':
                    text = await self._generate_cover_letter()
                else:
                    text = await self._answer_question(mapping.question_text)
                
                if text:
                    await element.fill(text)
            
            return True
            
        except Exception as e:
            print(f"Error filling {mapping.field_type}: {e}")
            return False
    
    async def _generate_cover_letter(self) -> str:
        """Generate cover letter using AI"""
        if not self.ai_client:
            return "I am excited about this opportunity and believe my skills are a great match for this position."
        
        try:
            # This would integrate with your existing Kimi service
            # For now, return a generic template
            skills_str = ', '.join(self.profile.skills[:5]) if self.profile.skills else 'my technical skills'
            
            return f"""Dear Hiring Manager,

I am writing to express my strong interest in this position. With {self.profile.years_experience or 'several'} years of experience and expertise in {skills_str}, I am confident I can make a valuable contribution to your team.

My background includes relevant work experience that has prepared me for this role. I am particularly drawn to this opportunity because of the company's innovative approach and commitment to excellence.

Thank you for considering my application. I look forward to discussing how I can contribute to your team.

Sincerely,
{self.profile.first_name} {self.profile.last_name}"""
            
        except Exception as e:
            print(f"Error generating cover letter: {e}")
            return ""
    
    async def _answer_question(self, question: str) -> str:
        """Generate answer for custom question"""
        q_lower = question.lower()
        
        # Simple heuristic matching
        if any(word in q_lower for word in ['salary', 'compensation', 'pay', 'expectation']):
            return self.profile.salary_expectation or 'Negotiable'
        
        if any(word in q_lower for word in ['start', 'notice', 'availability', 'when can you']):
            return 'Immediately' if not self.profile.work_history else '2 weeks'
        
        if 'experience' in q_lower and any(word in q_lower for word in ['years', 'how many', 'how much']):
            return str(self.profile.years_experience) if self.profile.years_experience else '3'
        
        if any(word in q_lower for word in ['relocation', 'relocate', 'willing to move']):
            return 'Open to relocation' if 'remote' in str(self.profile.custom_answers) else 'Prefer remote/local'
        
        if any(word in q_lower for word in ['remote', 'work from home', 'wfh']):
            return 'Yes, experienced with remote work'
        
        if 'why' in q_lower and any(word in q_lower for word in ['interested', 'position', 'role', 'company']):
            return f"I am excited about this opportunity and believe my background aligns well with the requirements. I'm particularly interested in contributing to a forward-thinking team."
        
        # Generic response
        return "I look forward to discussing this further."
