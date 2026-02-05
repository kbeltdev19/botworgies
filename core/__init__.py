#!/usr/bin/env python3
"""
Core Module - Unified Foundation for Job Applier

This module provides the foundational components used throughout the application:
- models: Data models (JobPosting, UserProfile, etc.)
- config: Unified configuration
- browser: Browser automation (Stagehand)
- ai: AI service (Moonshot/Kimi)

Example:
    from core import UnifiedBrowserManager, UnifiedAIService, UserProfile, JobPosting
    from core.config import config
"""

# Data Models
from .models import (
    PlatformType,
    ApplicationStatus,
    ExperienceLevel,
    JobType,
    JobPosting,
    ApplicationResult,
    UserProfile,
    Resume,
    SearchConfig,
    CampaignConfig,
    JobPlatformAdapter,
    score_job_fit,
    detect_platform_from_url,
)

# Browser Automation
from .browser import (
    UnifiedBrowserManager,
    BrowserSession,
    get_browser_manager,
    create_browser_session,
    close_browser_session,
)

# AI Service
from .ai import (
    UnifiedAIService,
    AIResponse,
    get_ai_service,
)

# Configuration
from api.config import config

__all__ = [
    # Enums
    "PlatformType",
    "ApplicationStatus",
    "ExperienceLevel",
    "JobType",
    
    # Models
    "JobPosting",
    "ApplicationResult",
    "UserProfile",
    "Resume",
    "SearchConfig",
    "CampaignConfig",
    "JobPlatformAdapter",
    
    # Functions
    "score_job_fit",
    "detect_platform_from_url",
    
    # Browser
    "UnifiedBrowserManager",
    "BrowserSession",
    "get_browser_manager",
    "create_browser_session",
    "close_browser_session",
    
    # AI
    "UnifiedAIService",
    "AIResponse",
    "get_ai_service",
    
    # Config
    "config",
]
