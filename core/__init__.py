"""
Core components for high-volume job application automation.

Modules:
- browser_pool: Manage concurrent Playwright browsers
- job_discovery: Continuous job scraping and queue
- captcha_solver: 2Captcha/Anti-Captcha integration
- proxy_manager: Rotating residential proxies
- platform_balancer: Distribute apps across platforms
- session_manager: Multi-account session handling
- error_handler: Retry logic and circuit breakers
- orchestrator: Ties everything together
"""

from .browser_pool import BrowserPool
from .browserbase_pool import BrowserBasePool, create_browserbase_pool
from .job_discovery import JobDiscoveryService, JobQueue
from .captcha_solver import CaptchaSolver
from .proxy_manager import ProxyManager
from .platform_balancer import PlatformBalancer
from .session_manager import SessionManager
from .error_handler import ErrorHandler, ErrorCategory
from .orchestrator import JobOrchestrator, OrchestratorConfig
from .job_pipeline import JobPipeline, PipelineConfig

__all__ = [
    "BrowserPool",
    "JobDiscoveryService",
    "JobQueue", 
    "CaptchaSolver",
    "ProxyManager",
    "PlatformBalancer",
    "SessionManager",
    "ErrorHandler",
    "ErrorCategory",
    "JobOrchestrator",
    "OrchestratorConfig",
    "JobPipeline",
    "PipelineConfig",
]
