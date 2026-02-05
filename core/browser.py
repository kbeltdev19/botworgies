#!/usr/bin/env python3
"""
Unified Browser Automation Module

Uses Stagehand as the default AI-powered browser automation framework.
Falls back to basic BrowserBase + Playwright when Stagehand is unavailable.

Stagehand supports two environments:
  - LOCAL: Runs a local Chromium browser via Playwright (no BrowserBase needed)
  - BROWSERBASE: Uses BrowserBase cloud browsers with residential proxies

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

# Stagehand SDK (default - AI-powered browser automation)
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
    logging.info("stagehand-py SDK not installed. Install: pip install stagehand-py")

# BrowserBase SDK (for fallback basic mode)
try:
    from browserbase import Browserbase
    BROWSERBASE_SDK_AVAILABLE = True
except ImportError:
    BROWSERBASE_SDK_AVAILABLE = False

# Playwright (for fallback basic mode)
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class BrowserSession:
    """Represents an active browser session."""
    session_id: str
    page: Any  # Stagehand page or Playwright page
    stagehand: Optional[Any] = None  # Stagehand instance (if using AI features)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedBrowserManager:
    """
    Unified browser manager with Stagehand as the default automation framework.

    Supports two modes (in priority order):
    1. Stagehand mode (default): AI-powered browser automation with act/extract/observe
    2. Basic mode (fallback): BrowserBase + Playwright when Stagehand is unavailable

    And two environments:
    - LOCAL: Local Chromium via Playwright (default, no BrowserBase account needed)
    - BROWSERBASE: Cloud browsers via BrowserBase (requires API key + project ID)

    Example:
        from core.browser import UnifiedBrowserManager

        async with UnifiedBrowserManager() as browser:
            session = await browser.create_session()
            page = session.page

            # Navigate
            await page.goto("https://example.com")

            # AI-powered actions (Stagehand)
            await page.act("click the apply button")
            data = await page.extract(instruction="Extract job title", schema={...})

            await browser.close_session(session.session_id)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        model_api_key: Optional[str] = None,
        model_name: str = "gpt-4o",
        env: str = "LOCAL",
        stagehand_enabled: bool = True,
    ):
        """
        Initialize the unified browser manager.

        Args:
            api_key: BrowserBase API key (or from BROWSERBASE_API_KEY env)
            project_id: BrowserBase project ID (or from BROWSERBASE_PROJECT_ID env)
            model_api_key: OpenAI API key for Stagehand AI features (or from OPENAI_API_KEY env)
            model_name: Model to use for Stagehand AI features (default: gpt-4o)
            env: "LOCAL" or "BROWSERBASE"
            stagehand_enabled: Whether to use Stagehand (default True)
        """
        self.api_key = api_key or os.getenv("BROWSERBASE_API_KEY")
        self.project_id = project_id or os.getenv("BROWSERBASE_PROJECT_ID")
        self.model_api_key = (
            model_api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("MOONSHOT_API_KEY")
        )
        self.model_name = model_name
        self.env = os.getenv("BROWSER_ENV", env)

        # Determine whether to use Stagehand
        stagehand_env = os.getenv("STAGEHAND_ENABLED", "true").lower() == "true"
        self.use_stagehand = (
            stagehand_enabled
            and stagehand_env
            and STAGEHAND_AVAILABLE
            and bool(self.model_api_key)
        )

        self._sessions: Dict[str, BrowserSession] = {}
        self._config = None
        self._bb = None  # Browserbase instance (fallback only)

        if not self.use_stagehand and not self.model_api_key:
            logger.warning(
                "No AI model API key found. Set OPENAI_API_KEY for Stagehand AI features."
            )
        if self.env == "BROWSERBASE" and not self.api_key:
            logger.warning("BROWSERBASE_API_KEY not set - using LOCAL environment")
            self.env = "LOCAL"

    async def init(self):
        """Initialize the browser manager."""
        if self.use_stagehand:
            config_args = {
                "env": self.env,
                "model_name": self.model_name,
                "model_client_options": {"apiKey": self.model_api_key},
            }
            # Only include BrowserBase credentials in BROWSERBASE mode
            if self.env == "BROWSERBASE":
                config_args["api_key"] = self.api_key
                config_args["project_id"] = self.project_id

            self._config = StagehandConfig(**config_args)
            logger.info(
                f"Browser manager initialized (Stagehand, env={self.env}, model={self.model_name})"
            )
        else:
            # Fallback: basic BrowserBase + Playwright
            if BROWSERBASE_SDK_AVAILABLE and self.api_key:
                self._bb = Browserbase(api_key=self.api_key)
                logger.info(f"Browser manager initialized (basic Playwright, env={self.env})")
            elif PLAYWRIGHT_AVAILABLE:
                logger.info("Browser manager initialized (local Playwright, no BrowserBase)")
            else:
                raise ImportError(
                    "No browser automation available. Install stagehand-py or playwright."
                )

        return self

    async def create_session(self, platform: str = "generic") -> BrowserSession:
        """
        Create a new browser session.

        Args:
            platform: Platform identifier for metadata

        Returns:
            BrowserSession instance
        """
        if not self._bb and not self._config and not PLAYWRIGHT_AVAILABLE:
            await self.init()

        try:
            if self.use_stagehand:
                return await self._create_stagehand_session(platform)
            elif self._bb:
                return await self._create_basic_session(platform)
            else:
                return await self._create_local_playwright_session(platform)
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise

    async def _create_stagehand_session(self, platform: str = "generic") -> BrowserSession:
        """Create a Stagehand-powered browser session."""
        if not self._config:
            await self.init()

        stagehand = Stagehand(config=self._config)
        await stagehand.init()

        session = BrowserSession(
            session_id=getattr(stagehand, "session_id", None)
            or f"stagehand_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            stagehand=stagehand,
            page=stagehand.page,
            metadata={"platform": platform, "mode": "stagehand", "env": self.env},
        )

        self._sessions[session.session_id] = session
        logger.info(
            f"Created Stagehand session: {session.session_id} (env={self.env}, platform={platform})"
        )
        return session

    async def _create_basic_session(self, platform: str = "generic") -> BrowserSession:
        """Create a basic BrowserBase session without AI features."""
        bb_session = self._bb.sessions.create(project_id=self.project_id)
        connect_url = bb_session.connect_url
        session_id = bb_session.id

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
                "env": "BROWSERBASE",
                "playwright": playwright,
                "browser": browser,
                "context": context,
            },
        )

        self._sessions[session_id] = session
        logger.info(f"Created basic BrowserBase session: {session_id}")
        return session

    async def _create_local_playwright_session(self, platform: str = "generic") -> BrowserSession:
        """Create a local Playwright session (no BrowserBase, no Stagehand)."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        session_id = f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        session = BrowserSession(
            session_id=session_id,
            page=page,
            stagehand=None,
            metadata={
                "platform": platform,
                "mode": "local",
                "env": "LOCAL",
                "playwright": playwright,
                "browser": browser,
                "context": context,
            },
        )

        self._sessions[session_id] = session
        logger.info(f"Created local Playwright session: {session_id}")
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
                    await session.stagehand.close()
                else:
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
            "has_model_api_key": bool(self.model_api_key),
            "stagehand_enabled": self.use_stagehand,
            "stagehand_sdk_available": STAGEHAND_AVAILABLE,
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
