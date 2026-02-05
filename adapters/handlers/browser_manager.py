#!/usr/bin/env python3
"""
Browser Manager - Simple wrapper for BrowserBase/Playwright.
"""

import os
from typing import Optional, Tuple
from playwright.async_api import async_playwright, BrowserContext, Page


class BrowserManager:
    """Simple browser manager for Playwright with BrowserBase support."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
    
    async def create_context(self) -> Tuple[BrowserContext, Page]:
        """Create a browser context and page."""
        self.playwright = await async_playwright().start()
        
        # Check for BrowserBase credentials
        api_key = os.getenv('BROWSERBASE_API_KEY')
        
        if api_key:
            # Use BrowserBase
            from browserbase import Browserbase
            
            project_id = os.getenv('BROWSERBASE_PROJECT_ID')
            bb = Browserbase(api_key=api_key)
            session = bb.sessions.create(project_id=project_id)
            
            self.browser = await self.playwright.chromium.connect_over_cdp(
                session.connect_url
            )
        else:
            # Use local browser
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless
            )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        
        page = await self.context.new_page()
        return self.context, page
    
    async def close_all(self):
        """Close all browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
