#!/usr/bin/env python3
"""
Unified Browser Automation Module

Uses BrowserBase Stagehand as the primary browser automation framework.
This replaces the old browser/stealth_manager.py, browser/enhanced_manager.py,
and core/browserbase_pool.py modules.
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

# Stagehand SDK
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
    logging.warning("stagehand-py not installed. Browser automation unavailable.")

# BrowserBase SDK
try:
    from browserbase import Browserbase
    BROWSERBASE_SDK_AVAILABLE = True
except ImportError:
    BROWSERBASE_SDK_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class BrowserSession:
    """Represents an active browser session."""
    session_id: str
    stagehand: Any  # Stagehand instance
    page: Any  # Stagehand page
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedBrowserManager:
    """
    Unified browser manager using BrowserBase Stagehand.
    
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
        
        # AI-powered actions
        await page.act("click the apply button")
        
        # Extract data
        data = await page.extract('{"job_title": "string"}')
        
        await browser.close_session(session.session_id)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        model_api_key: Optional[str] = None,
        model_name: str = "moonshot-v1-8k-vision-preview",
        env: str = "BROWSERBASE"
    ):
        """
        Initialize the unified browser manager.
        
        Args:
            api_key: BrowserBase API key (or from BROWSERBASE_API_KEY env)
            project_id: BrowserBase project ID (or from BROWSERBASE_PROJECT_ID env)
            model_api_key: Model API key (or from MOONSHOT_API_KEY env)
            model_name: Model name to use
            env: "BROWSERBASE" or "LOCAL"
        """
        if not STAGEHAND_AVAILABLE:
            raise ImportError(
                "stagehand-py is required. Install: pip install stagehand-py"
            )
        
        self.api_key = api_key or os.getenv("BROWSERBASE_API_KEY")
        self.project_id = project_id or os.getenv("BROWSERBASE_PROJECT_ID")
        self.model_api_key = model_api_key or os.getenv("MOONSHOT_API_KEY")
        self.model_name = model_name
        self.env = env
        
        self._sessions: Dict[str, BrowserSession] = {}
        self._config = None
        
        if not self.api_key:
            logger.warning("BROWSERBASE_API_KEY not set")
        if not self.project_id:
            logger.warning("BROWSERBASE_PROJECT_ID not set")
        if not self.model_api_key:
            logger.warning("MOONSHOT_API_KEY not set")
    
    async def init(self):
        """Initialize the browser manager."""
        self._config = StagehandConfig(
            env=self.env,
            api_key=self.api_key,
            project_id=self.project_id,
            model_name=self.model_name,
            model_client_options={"apiKey": self.model_api_key}
        )
        logger.info(f"UnifiedBrowserManager initialized ({self.env} mode)")
        return self
    
    async def create_session(self, platform: str = "generic") -> BrowserSession:
        """
        Create a new browser session.
        
        Args:
            platform: Platform identifier for metadata
            
        Returns:
            BrowserSession instance
        """
        if not self._config:
            await self.init()
        
        stagehand = Stagehand(config=self._config)
        await stagehand.init()
        
        session = BrowserSession(
            session_id=stagehand.session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            stagehand=stagehand,
            page=stagehand.page,
            metadata={"platform": platform}
        )
        
        self._sessions[session.session_id] = session
        logger.info(f"Created browser session: {session.session_id}")
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[BrowserSession]:
        """Get an existing session by ID."""
        return self._sessions.get(session_id)
    
    async def close_session(self, session_id: str):
        """Close a specific session."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            try:
                await session.stagehand.close()
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Get browser manager statistics."""
        return {
            "active_sessions": len(self._sessions),
            "session_ids": list(self._sessions.keys()),
            "env": self.env,
            "has_api_key": bool(self.api_key),
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
