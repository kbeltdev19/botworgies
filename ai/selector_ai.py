"""
AI-Powered Form Selector Detection

Uses Moonshot AI to analyze job application forms and suggest field selectors.
This is especially useful for Workday and other complex ATS systems where
selectors vary between companies.
"""

import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

import os

logger = logging.getLogger(__name__)


@dataclass
class SelectorSuggestion:
    """AI-suggested selector for a form field."""
    field_name: str
    selector: str
    confidence: float
    alternatives: List[str]
    reasoning: str


class SelectorAI:
    """
    AI service for detecting form field selectors.
    
    Usage:
        ai = SelectorAI()
        suggestions = await ai.analyze_form(page_html, page_url)
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        self.model = "moonshot-v1-8k"
        
    async def analyze_form(self, page_html: str, page_url: str) -> Dict[str, SelectorSuggestion]:
        """
        Analyze a form and suggest selectors for common fields.
        
        Args:
            page_html: HTML content of the page
            page_url: URL of the page
            
        Returns:
            Dictionary mapping field names to selector suggestions
        """
        # Truncate HTML if too long
        max_html = 50000
        if len(page_html) > max_html:
            page_html = page_html[:max_html] + "..."
        
        prompt = f"""Analyze this job application form and suggest CSS selectors for each field.

URL: {page_url}

HTML:
```html
{page_html}
```

Identify selectors for these fields:
1. First name input
2. Last name input  
3. Email input
4. Phone input
5. Resume upload file input
6. Apply/Submit button
7. Next/Continue button (for multi-step forms)
8. Success confirmation message (after submission)

For each field, provide:
- Primary selector (most specific)
- Alternative selectors (fallback options)
- Confidence score (0-1)
- Brief reasoning

Respond in JSON format:
{{
    "first_name": {{
        "selector": "input[name='firstName']",
        "alternatives": ["#first_name", "input[placeholder*='First']"],
        "confidence": 0.95,
        "reasoning": "name attribute matches standard pattern"
    }},
    ...
}}
"""
        
        try:
            # Call Moonshot API
            result = await self._call_api(prompt)
            
            # Parse suggestions
            suggestions = {}
            for field_name, data in result.items():
                suggestions[field_name] = SelectorSuggestion(
                    field_name=field_name,
                    selector=data.get("selector", ""),
                    confidence=data.get("confidence", 0.5),
                    alternatives=data.get("alternatives", []),
                    reasoning=data.get("reasoning", "")
                )
            
            return suggestions
            
        except Exception as e:
            logger.error(f"AI selector analysis failed: {e}")
            return {}
    
    async def suggest_field_mapping(
        self,
        page_html: str,
        profile_fields: List[str]
    ) -> Dict[str, str]:
        """
        Suggest which profile fields map to which form fields.
        
        Args:
            page_html: HTML content
            profile_fields: Available profile fields (e.g., ['first_name', 'email'])
            
        Returns:
            Dictionary mapping profile fields to form selectors
        """
        prompt = f"""Map these profile fields to form field selectors.

Available profile fields: {', '.join(profile_fields)}

HTML:
```html
{page_html[:30000]}
```

Create a mapping in JSON format:
{{
    "first_name": "input[name='firstName']",
    "last_name": "input[name='lastName']",
    ...
}}

Only include fields that are present in the form.
"""
        
        try:
            result = await self._call_api(prompt)
            return result
        except Exception as e:
            logger.error(f"Field mapping failed: {e}")
            return {}
    
    async def analyze_workday_specific(
        self,
        page_html: str,
        company_name: str
    ) -> Dict[str, str]:
        """
        Analyze Workday-specific selectors for a company.
        
        Workday uses data-automation-id attributes that vary by company.
        """
        prompt = f"""Analyze this Workday application form for {company_name}.

Workday forms typically use selectors like:
- data-automation-id="legalNameSection_firstName"
- data-automation-id="legalNameSection_lastName"
- data-automation-id="email"
- data-automation-id="phone"
- data-automation-id="resumeUpload"
- data-automation-id="applyButton"
- data-automation-id="submitButton"
- data-automation-id="bottom-navigation-next-button"

HTML:
```html
{page_html[:30000]}
```

Extract the actual selectors used in this form. Return JSON:
{{
    "first_name": "input[data-automation-id='...']",
    "last_name": "input[data-automation-id='...']",
    ...
}}
"""
        
        try:
            return await self._call_api(prompt)
        except Exception as e:
            logger.error(f"Workday analysis failed: {e}")
            return {}
    
    async def _call_api(self, prompt: str) -> dict:
        """Call Moonshot API."""
        import aiohttp
        
        url = "https://api.moonshot.cn/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a web scraping expert. Analyze HTML forms and suggest CSS selectors. Respond only in JSON format."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"API error {resp.status}: {text}")
                
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                
                # Extract JSON from markdown code block if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                return json.loads(content.strip())


class SelectorLearningDB:
    """
    Database for learning and storing successful selectors.
    
    Over time, this builds a knowledge base of selectors for different companies.
    """
    
    def __init__(self, db_path: str = ".data/selector_learning.json"):
        self.db_path = db_path
        self.selectors = self._load()
    
    def _load(self) -> dict:
        """Load learned selectors from disk."""
        import json
        from pathlib import Path
        
        path = Path(self.db_path)
        if path.exists():
            return json.loads(path.read_text())
        return {}
    
    def save(self):
        """Save learned selectors to disk."""
        import json
        from pathlib import Path
        
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.selectors, indent=2))
    
    def get_selectors(self, company: str, platform: str) -> Optional[Dict[str, str]]:
        """Get learned selectors for a company."""
        key = f"{company.lower()}_{platform.lower()}"
        return self.selectors.get(key)
    
    def record_success(self, company: str, platform: str, selectors: Dict[str, str]):
        """Record successful selectors for a company."""
        key = f"{company.lower()}_{platform.lower()}"
        self.selectors[key] = {
            "selectors": selectors,
            "success_count": self.selectors.get(key, {}).get("success_count", 0) + 1
        }
        self.save()
    
    def get_most_common_selector(self, field: str, platform: str) -> Optional[str]:
        """Get the most commonly successful selector for a field on a platform."""
        from collections import Counter
        
        selectors = []
        for entry in self.selectors.values():
            if field in entry.get("selectors", {}):
                selectors.append(entry["selectors"][field])
        
        if selectors:
            return Counter(selectors).most_common(1)[0][0]
        return None


# Usage example
async def test_selector_ai():
    """Test the selector AI."""
    ai = SelectorAI()
    
    # Example HTML
    html = """
    <form>
        <input name="firstName" placeholder="First Name" />
        <input name="lastName" placeholder="Last Name" />
        <input type="email" name="email" />
        <input type="file" name="resume" />
        <button type="submit">Apply</button>
    </form>
    """
    
    suggestions = await ai.analyze_form(html, "https://example.com/apply")
    
    for field, suggestion in suggestions.items():
        print(f"{field}: {suggestion.selector} (confidence: {suggestion.confidence})")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_selector_ai())
