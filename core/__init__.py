"""
Core services for the Job Applier platform.

Consolidated, reusable services that eliminate code duplication
across adapters and campaigns.
"""

from .screenshot_manager import ScreenshotManager, ScreenshotContext, Screenshot
from .form_filler import FormFiller, FieldMapping, FillResult, FillStrategy
from .adapter_base import UnifiedJobAdapter, AdapterConfig
from .campaign_runner import CampaignRunner, CampaignConfig

__all__ = [
    # Screenshot
    "ScreenshotManager",
    "ScreenshotContext",
    "Screenshot",
    
    # Form Filling
    "FormFiller",
    "FieldMapping",
    "FillResult",
    "FillStrategy",
    
    # Adapter Base
    "UnifiedJobAdapter",
    "AdapterConfig",
    
    # Campaign
    "CampaignRunner",
    "CampaignConfig",
]
