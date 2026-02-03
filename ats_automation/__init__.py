"""
Universal ATS Automation System

Supports: Workday, Taleo, iCIMS, SuccessFactors, ADP, AngelList, Wellfound, Dice

Usage:
    from ats_automation import ATSRouter, UserProfile
    
    profile = UserProfile(...)
    router = ATSRouter(profile)
    result = await router.apply("https://company.workday.com/job/123")
"""

from .models import (
    ATSPlatform, 
    UserProfile, 
    ApplicationResult, 
    FieldMapping,
    DiceJob
)
from .browserbase_manager import BrowserBaseManager
from .generic_mapper import GenericFieldMapper
from .ats_router import ATSRouter

__version__ = "1.0.0"
__all__ = [
    'ATSRouter',
    'BrowserBaseManager',
    'GenericFieldMapper',
    'UserProfile',
    'ApplicationResult',
    'FieldMapping',
    'DiceJob',
    'ATSPlatform'
]
