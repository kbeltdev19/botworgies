#!/usr/bin/env python3
"""
Unified Browser Automation Module

Uses BrowserBase for cloud browser automation.
Optionally uses Stagehand for AI-powered browser automation when STAGEHAND_API_URL is set.

This replaces the old browser/stealth_manager.py, browser/enhanced_manager.py,
and core/browserbase_pool.py modules.
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# BrowserBase SDK
try:
    from browserbase import Browserbase
    BROWSERBASE_SDK_AVAILABLE = True
except ImportError:
    BROWSERBASE_SDK_AVAILABLE = False
    logging.warning("browserbase SDK not installed.")

# Stagehand SDK (optional - for AI features)
try:
    from stagehand import Stagehand, StagehandConfig
    from stagehand.schemas import (
        ActOptions,
        ExtractOptions,
        ObserveOptions,
        AgentConfig,
        AgentExecuteOptions,
        AgentProvider,
    )
    STAGEHAND_AVAILABLE = True
except ImportError:
    STAGEHAND_AVAILABLE = False

# Playwright (for basic browser automation)
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class BrowserSession:
    """Represents an active browser session."""
    session_id: str
    page: Any  # Playwright page
    stagehand: Optional[Any] = None  # Stagehand instance (if using AI features)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedBrowserManager:
    """
    Unified browser manager using BrowserBase.
    
    Supports two modes:
    1. Basic mode: Uses BrowserBase + Playwright (always available)
    2. AI mode: Uses Stagehand for AI-powered automation (requires STAGEHAND_API_URL)
    
    This is the single entry point for all browser automation in the application.
    It replaces multiple legacy browser managers.
    
    Example:
        from core.browser import UnifiedBrowserManager
        
        browser = UnifiedBrowserManager()
        await browser.init()
        
        session = await browser.create_session()
        page = session.page
        
        # Navigate
        await page.goto("https://example.com")
        
        # AI-powered actions (requires STAGEHAND_API_URL)
        if session.stagehand:
            await page.act("click the apply button")
        
        await browser.close_session(session.session_id)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        model_api_key: Optional[str] = None,
        model_name: str = "gpt-4o",
        env: str = "BROWSERBASE"
    ):
        """
        Initialize the unified browser manager.
        
        Args:
            api_key: BrowserBase API key (or from BROWSERBASE_API_KEY env)
            project_id: BrowserBase project ID (or from BROWSERBASE_PROJECT_ID env)
            model_api_key: OpenAI API key for AI features (or from OPENAI_API_KEY env)
            model_name: Model name to use for AI features
            env: "BROWSERBASE" or "LOCAL"
        """
        if not BROWSERBASE_SDK_AVAILABLE:
            raise ImportError(
                "browserbase SDK is required. Install: pip install browserbase"
            )
        
        self.api_key = api_key or os.getenv("BROWSERBASE_API_KEY")
        self.project_id = project_id or os.getenv("BROWSERBASE_PROJECT_ID")
        self.model_api_key = model_api_key or os.getenv("OPENAI_API_KEY") or os.getenv("MOONSHOT_API_KEY")
        self.model_name = model_name
        self.env = env
        
        # Check if Stagehand server is available for AI features
        self.stagehand_server_url = os.getenv("STAGEHAND_API_URL")
        self.use_stagehand = STAGEHAND_AVAILABLE and bool(self.stagehand_server_url) and bool(self.model_api_key)
        
        self._sessions: Dict[str, BrowserSession] = {}
        self._config = None
        self._bb = None  # Browserbase instance
        
        if not self.api_key:
            logger.warning("BROWSERBASE_API_KEY not set")
        if not self.project_id:
            logger.warning("BROWSERBASE_PROJECT_ID not set")
        if STAGEHAND_AVAILABLE and not self.stagehand_server_url:
            logger.debug("STAGEHAND_API_URL not set - AI browser automation disabled")
    
    async def init(self):
        """Initialize the browser manager."""
        if self.use_stagehand:
            # Build Stagehand config for AI features
            config_args = {
                "env": self.env,
                "api_key": self.api_key,
                "project_id": self.project_id,
                "model_name": self.model_name,
                "model_client_options": {"apiKey": self.model_api_key}
            }
            self._config = StagehandConfig(**config_args)
            logger.info(f"Browser manager initialized ({self.env} mode, AI features enabled)")
        else:
            # Basic BrowserBase mode
            self._bb = Browserbase(api_key=self.api_key)
            mode = "AI" if self.use_stagehand else "basic"
            logger.info(f"Browser manager initialized ({self.env} mode, {mode} mode)")
        
        return self
    
    async def create_session(self, platform: str = "generic") -> BrowserSession:
        """
        Create a new browser session.
        
        Args:
            platform: Platform identifier for metadata
            
        Returns:
            BrowserSession instance
        """
        if not self._bb and not self._config:
            await self.init()
        
        try:
            if self.use_stagehand:
                # Use Stagehand for AI-powered automation
                stagehand = Stagehand(
                    config=self._config,
                    server_url=self.stagehand_server_url,
                    model_api_key=self.model_api_key
                )
                await stagehand.init()
                
                session = BrowserSession(
                    session_id=stagehand.session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    stagehand=stagehand,
                    page=stagehand.page,
                    metadata={"platform": platform, "mode": "ai"}
                )
            else:
                # Use basic BrowserBase + Playwright
                session_id = await self._create_basic_session(platform)
                return session_id
            
            self._sessions[session.session_id] = session
            logger.info(f"Created browser session: {session.session_id} ({session.metadata.get('mode', 'basic')} mode)")
            
            return session
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    async def _create_basic_session(self, platform: str = "generic") -> BrowserSession:
        """Create a basic BrowserBase session without AI features."""
        # Create a BrowserBase session
        bb_session = self._bb.sessions.create(project_id=self.project_id)
        connect_url = bb_session.connect_url
        session_id = bb_session.id
        
        # Launch Playwright and connect to BrowserBase
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        
        session = BrowserSession(
            session_id=session_id,
            page=page,
            stagehand=None,
            metadata={
                "platform": platform,
                "mode": "basic",
                "playwright": playwright,
                "browser": browser,
                "context": context
            }
        )
        
        self._sessions[session_id] = session
        logger.info(f"Created basic browser session: {session_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[BrowserSession]:
        """Get an existing session by ID."""
        return self._sessions.get(session_id)
    
    async def close_session(self, session_id: str):
        """Close a specific session."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            try:
                if session.stagehand:
                    # Close Stagehand session
                    await session.stagehand.close()
                else:
                    # Close basic session
                    metadata = session.metadata
                    if "browser" in metadata:
                        await metadata["browser"].close()
                    if "playwright" in metadata:
                        await metadata["playwright"].stop()
                
                logger.info(f"Closed browser session: {session_id}")
            except Exception as e:
                logger.error(f"Error closing session {session_id}: {e}")
            finally:
                del self._sessions[session_id]
    
    async def close_all(self):
        """Close all active sessions."""
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)
        logger.info("All browser sessions closed")
    
    async def human_like_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """
        Wait for a random duration to simulate human-like behavior.
        
        Args:
            min_seconds: Minimum delay in seconds
            max_seconds: Maximum delay in seconds
        """
        import random
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get browser manager statistics."""
        return {
            "active_sessions": len(self._sessions),
            "session_ids": list(self._sessions.keys()),
            "env": self.env,
            "has_api_key": bool(self.api_key),
            "ai_mode": self.use_stagehand
        }
    
    async def __aenter__(self):
        await self.init()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_all()


# Singleton instance
_browser_manager: Optional[UnifiedBrowserManager] = None


def get_browser_manager() -> UnifiedBrowserManager:
    """Get or create singleton browser manager instance."""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = UnifiedBrowserManager()
    return _browser_manager


def reset_browser_manager():
    """Reset the singleton instance (for testing)."""
    global _browser_manager
    _browser_manager = None


# Convenience functions for direct use
async def create_browser_session(platform: str = "generic") -> BrowserSession:
    """Quick function to create a browser session."""
    manager = get_browser_manager()
    return await manager.create_session(platform)


async def close_browser_session(session_id: str):
    """Quick function to close a browser session."""
    manager = get_browser_manager()
    await manager.close_session(session_id)
