"""
Browser Automation Module - Powered by BrowserBase Stagehand

This module is now a thin wrapper around core.browser for backwards compatibility.
New code should import directly from core:
    from core import UnifiedBrowserManager, get_browser_manager

Environment Variables Used:
    BROWSERBASE_API_KEY - Your BrowserBase API key
    BROWSERBASE_PROJECT_ID - Your BrowserBase project ID  
    MOONSHOT_API_KEY - Your Moonshot API key (for AI actions)
"""

# Re-export from core for backwards compatibility
from core.browser import (
    UnifiedBrowserManager,
    BrowserSession,
    get_browser_manager,
    create_browser_session,
    close_browser_session,
    reset_browser_manager,
)

# Re-export from core.ai
from core.ai import (
    UnifiedAIService,
    AIResponse,
    get_ai_service,
    reset_ai_service,
)

# Stagehand SDK (if available)
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
    Stagehand = None
    StagehandConfig = None

# BrowserBase SDK (if available)
try:
    from browserbase import Browserbase
    BROWSERBASE_SDK_AVAILABLE = True
except ImportError:
    BROWSERBASE_SDK_AVAILABLE = False
    Browserbase = None


__all__ = [
    # Core browser components
    "UnifiedBrowserManager",
    "BrowserSession",
    "get_browser_manager",
    "create_browser_session",
    "close_browser_session",
    "reset_browser_manager",
    
    # Core AI components
    "UnifiedAIService",
    "AIResponse",
    "get_ai_service",
    "reset_ai_service",
    
    # Stagehand SDK (if available)
    "Stagehand",
    "StagehandConfig",
    "ActOptions",
    "ExtractOptions",
    "ObserveOptions",
    "AgentConfig",
    "AgentExecuteOptions",
    "AgentProvider",
    "STAGEHAND_AVAILABLE",
    
    # BrowserBase SDK
    "Browserbase",
    "BROWSERBASE_SDK_AVAILABLE",
]
