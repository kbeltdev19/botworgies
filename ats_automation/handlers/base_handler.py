"""
Base handler for all ATS platforms
"""

import asyncio
import random
from abc import ABC, abstractmethod
from typing import Optional, List
from ..models import ApplicationResult, ATSPlatform, UserProfile
from ..browserbase_manager import BrowserBaseManager
from ..generic_mapper import GenericFieldMapper


class BaseATSHandler(ABC):
    """Abstract base class for all ATS handlers"""
    
    # Override in subclasses
    IDENTIFIERS: List[str] = []
    PLATFORM: ATSPlatform = ATSPlatform.UNKNOWN
    
    def __init__(
        self, 
        browser_manager: BrowserBaseManager,
        user_profile: UserProfile,
        ai_client=None
    ):
        self.browser = browser_manager
        self.profile = user_profile
        self.ai_client = ai_client
    
    @abstractmethod
    async def can_handle(self, url: str) -> bool:
        """Check if this handler can process the given URL"""
        pass
    
    @abstractmethod
    async def apply(self, job_url: str) -> ApplicationResult:
        """Execute job application"""
        pass
    
    async def _human_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Add human-like delay"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    def _generate_temp_password(self) -> str:
        """Generate temporary password for account creation"""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(16))
    
    async def _fill_with_mapper(
        self, 
        page, 
        field_types: Optional[List[str]] = None
    ) -> int:
        """Fill fields using generic mapper"""
        mapper = GenericFieldMapper(page, self.profile, self.ai_client)
        mappings = await mapper.analyze_page()
        
        if field_types:
            mappings = [m for m in mappings if m.field_type in field_types]
        
        return await mapper.fill_all_fields(mappings)
    
    async def _find_and_click(
        self, 
        page, 
        selectors: List[str],
        timeout: int = 5000
    ) -> bool:
        """Try multiple selectors and click first match"""
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=timeout)
                if element:
                    await element.click()
                    return True
            except:
                continue
        return False
