#!/usr/bin/env python3
"""
Browser Manager - BrowserBase Stagehand Integration

Simple wrapper around BrowserBase Stagehand for backward compatibility.
New code should use Stagehand directly from the browser module.
"""

import os
from typing import Optional, Tuple
from playwright.async_api import BrowserContext, Page

try:
    from browser import Stagehand, StagehandConfig
    STAGEHAND_AVAILABLE = True
except ImportError:
    STAGEHAND_AVAILABLE = False


class BrowserManager:
    """
    Simple browser manager using Stagehand + BrowserBase.
    
    This is a compatibility wrapper. For new code, use Stagehand directly.
    
    Example:
        browser = BrowserManager()
        context, page = await browser.create_context()
        # ... use page ...
        await browser.close_all()
    """
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.stagehand: Optional[Stagehand] = None
        self._page: Optional[Page] = None
    
    async def create_context(self) -> Tuple[BrowserContext, Page]:
        """
        Create a browser context and page using Stagehand.
        
        Returns:
            Tuple of (BrowserContext, Page)
        """
        if not STAGEHAND_AVAILABLE:
            raise ImportError(
                "Stagehand is not available. "
                "Install with: pip install stagehand-py browserbase"
            )
        
        import os
        
        # Configure Stagehand using existing API keys
        config = StagehandConfig(
            env="BROWSERBASE",
            api_key=os.getenv("BROWSERBASE_API_KEY"),
            project_id=os.getenv("BROWSERBASE_PROJECT_ID"),
            model_name=os.getenv("MODEL_NAME", "moonshot-v1-8k-vision-preview"),
            model_client_options={"apiKey": os.getenv("MOONSHOT_API_KEY")}
        )
        
        # Initialize Stagehand
        self.stagehand = Stagehand(config=config)
        await self.stagehand.init()
        
        # Get page reference
        self._page = self.stagehand.page
        
        # Stagehand doesn't expose context directly, return None for context
        # and the Stagehand page wrapper for page
        return None, self._page
    
    async def close_all(self):
        """Close all browser resources."""
        if self.stagehand:
            await self.stagehand.close()
            self.stagehand = None
            self._page = None
