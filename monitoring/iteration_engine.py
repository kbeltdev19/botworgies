"""
Iteration Engine - Learn from Failures, Retry with Improvements

Analyzes failed applications, identifies patterns, and adjusts
strategies for subsequent attempts.
"""

import json
import re
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from monitoring.application_monitor import get_monitor, ApplicationEventType


class FailurePattern(Enum):
    """Types of failure patterns we can detect."""
    SELECTOR_NOT_FOUND = "selector_not_found"
    ELEMENT_NOT_CLICKABLE = "element_not_clickable"
    FORM_VALIDATION_ERROR = "form_validation_error"
    TIMEOUT = "timeout"
    CAPTCHA_DETECTED = "captcha_detected"
    SESSION_EXPIRED = "session_expired"
    CONFIRMATION_NOT_FOUND = "confirmation_not_found"
    UPLOAD_FAILED = "upload_failed"
    NAVIGATION_ERROR = "navigation_error"
    UNKNOWN = "unknown"


@dataclass
class FailureAnalysis:
    """Analysis of a failure."""
    application_id: str
    platform: str
    failure_pattern: FailurePattern
    root_cause: str
    suggested_fix: str
    confidence: float  # 0.0 to 1.0
    context: Dict[str, Any]


@dataclass
class StrategyAdjustment:
    """Adjustment to make for next attempt."""
    target_platform: str
    adjustment_type: str
    parameter: str
    new_value: Any
    reason: str


class IterationEngine:
    """
    Analyzes application failures and suggests improvements.
    
    Uses pattern matching on error messages and screenshots
    to identify root causes and suggest fixes.
    """
    
    def __init__(self):
        self.monitor = get_monitor()
        
        # Pattern matchers for different failure types
        self.patterns = {
            FailurePattern.SELECTOR_NOT_FOUND: [
                r"element not found",
                r"locator.*count.*0",
                r"timeout.*waiting for selector",
                r"unable to locate",
                r"selector.*failed",
            ],
            FailurePattern.ELEMENT_NOT_CLICKABLE: [
                r"element not interactable",
                r"element not visible",
                r"element not enabled",
                r"click.*failed",
                r"intercepted",
            ],
            FailurePattern.FORM_VALIDATION_ERROR: [
                r"validation.*error",
                r"required.*field",
                r"invalid.*input",
                r"please fill",
                r"error message",
            ],
            FailurePattern.TIMEOUT: [
                r"timeout",
                r"timed out",
                r"page.*load.*timeout",
            ],
            FailurePattern.CAPTCHA_DETECTED: [
                r"captcha",
                r"recaptcha",
                r"hcaptcha",
                r"verify you are human",
                r"i'm not a robot",
            ],
            FailurePattern.SESSION_EXPIRED: [
                r"session.*expired",
                r"please.*login",
                r"authentication.*failed",
                r"unauthorized",
            ],
            FailurePattern.CONFIRMATION_NOT_FOUND: [
                r"confirmation.*not found",
                r"success.*indicator.*not found",
                r"could not.*confirm",
            ],
            FailurePattern.UPLOAD_FAILED: [
                r"upload.*failed",
                r"file.*too.*large",
                r"invalid.*file.*type",
            ],
            FailurePattern.NAVIGATION_ERROR: [
                r"navigation.*failed",
                r"net::",
                r"err_",
            ],
        }
        
        # Strategy adjustments for each pattern
        self.fixes = {
            FailurePattern.SELECTOR_NOT_FOUND: self._fix_selector_not_found,
            FailurePattern.ELEMENT_NOT_CLICKABLE: self._fix_element_not_clickable,
            FailurePattern.FORM_VALIDATION_ERROR: self._fix_form_validation,
            FailurePattern.TIMEOUT: self._fix_timeout,
            FailurePattern.CAPTCHA_DETECTED: self._fix_captcha,
            FailurePattern.SESSION_EXPIRED: self._fix_session_expired,
            FailurePattern.CONFIRMATION_NOT_FOUND: self._fix_confirmation_not_found,
            FailurePattern.UPLOAD_FAILED: self._fix_upload_failed,
            FailurePattern.NAVIGATION_ERROR: self._fix_navigation_error,
        }
        
        # Learned adjustments per platform
        self.platform_adjustments: Dict[str, List[StrategyAdjustment]] = {}
    
    def analyze_failure(self, application_id: str) -> Optional[FailureAnalysis]:
        """
        Analyze a failed application and identify root cause.
        
        Args:
            application_id: ID of the failed application
            
        Returns:
            FailureAnalysis with pattern and suggested fix
        """
        report = self.monitor.get_application_report(application_id)
        
        if "error" in report:
            return None
        
        metrics = report.get("metrics", {})
        events = report.get("events", [])
        platform = metrics.get("platform", "unknown")
        error_message = metrics.get("error_message", "")
        
        # Try to match error message to known patterns
        failure_pattern = self._match_pattern(error_message)
        
        # If no match, look at last events for clues
        if failure_pattern == FailurePattern.UNKNOWN and events:
            for event in reversed(events[-5:]):  # Check last 5 events
                event_msg = event.get("message", "")
                failure_pattern = self._match_pattern(event_msg)
                if failure_pattern != FailurePattern.UNKNOWN:
                    break
        
        # Get the fix function
        fix_func = self.fixes.get(failure_pattern, self._fix_unknown)
        suggested_fix, context = fix_func(platform, error_message, events)
        
        return FailureAnalysis(
            application_id=application_id,
            platform=platform,
            failure_pattern=failure_pattern,
            root_cause=failure_pattern.value,
            suggested_fix=suggested_fix,
            confidence=context.get("confidence", 0.5),
            context=context
        )
    
    def _match_pattern(self, text: str) -> FailurePattern:
        """Match error text to known failure patterns."""
        if not text:
            return FailurePattern.UNKNOWN
        
        text_lower = text.lower()
        
        for pattern, regexes in self.patterns.items():
            for regex in regexes:
                if re.search(regex, text_lower, re.IGNORECASE):
                    return pattern
        
        return FailurePattern.UNKNOWN
    
    def _fix_selector_not_found(self, platform: str, error: str, events: List[Dict]) -> tuple:
        """Suggest fix for selector not found."""
        context = {"confidence": 0.7}
        
        # Check if it's a specific known element
        if "submit" in error.lower():
            context["element"] = "submit_button"
            return (
                "Use alternative submit selectors and add wait before click",
                context
            )
        elif "next" in error.lower():
            context["element"] = "next_button"
            return (
                "Add multiple next button selectors and check visibility",
                context
            )
        
        return (
            "Add more selector fallbacks and increase wait time",
            context
        )
    
    def _fix_element_not_clickable(self, platform: str, error: str, events: List[Dict]) -> tuple:
        """Suggest fix for element not clickable."""
        context = {"confidence": 0.8}
        
        return (
            "Add scroll into view, wait for animation, check for overlays",
            context
        )
    
    def _fix_form_validation(self, platform: str, error: str, events: List[Dict]) -> tuple:
        """Suggest fix for form validation errors."""
        context = {"confidence": 0.9}
        
        # Extract field name if possible
        field_match = re.search(r'["\']([\w_]+)["\']', error)
        if field_match:
            context["field"] = field_match.group(1)
        
        return (
            "Fill all required fields, check validation rules, add better field detection",
            context
        )
    
    def _fix_timeout(self, platform: str, error: str, events: List[Dict]) -> tuple:
        """Suggest fix for timeouts."""
        context = {"confidence": 0.8}
        
        return (
            "Increase timeout, check for slow network, add progress indicators",
            context
        )
    
    def _fix_captcha(self, platform: str, error: str, events: List[Dict]) -> tuple:
        """Suggest fix for CAPTCHA detection."""
        context = {"confidence": 0.95}
        
        return (
            "Switch to manual review mode for CAPTCHA, use CapSolver if available",
            context
        )
    
    def _fix_session_expired(self, platform: str, error: str, events: List[Dict]) -> tuple:
        """Suggest fix for session expired."""
        context = {"confidence": 0.9}
        
        return (
            "Refresh session cookie, re-authenticate, use fresh browser session",
            context
        )
    
    def _fix_confirmation_not_found(self, platform: str, error: str, events: List[Dict]) -> tuple:
        """Suggest fix for confirmation not found."""
        context = {"confidence": 0.6}
        
        return (
            "Wait longer after submit, check for redirect, verify success indicators",
            context
        )
    
    def _fix_upload_failed(self, platform: str, error: str, events: List[Dict]) -> tuple:
        """Suggest fix for upload failures."""
        context = {"confidence": 0.85}
        
        return (
            "Check file size, verify file exists, try different file type",
            context
        )
    
    def _fix_navigation_error(self, platform: str, error: str, events: List[Dict]) -> tuple:
        """Suggest fix for navigation errors."""
        context = {"confidence": 0.75}
        
        return (
            "Check URL, retry navigation, verify network connectivity",
            context
        )
    
    def _fix_unknown(self, platform: str, error: str, events: List[Dict]) -> tuple:
        """Handle unknown failures."""
        context = {"confidence": 0.3}
        
        return (
            "Add more logging, capture additional screenshots, review manually",
            context
        )
    
    def generate_adjustments(self, analysis: FailureAnalysis) -> List[StrategyAdjustment]:
        """
        Generate specific strategy adjustments based on failure analysis.
        
        Args:
            analysis: FailureAnalysis from analyze_failure()
            
        Returns:
            List of StrategyAdjustment to apply
        """
        adjustments = []
        
        if analysis.failure_pattern == FailurePattern.SELECTOR_NOT_FOUND:
            adjustments.append(StrategyAdjustment(
                target_platform=analysis.platform,
                adjustment_type="wait_time",
                parameter="pre_selector_wait",
                new_value=3.0,  # Increase to 3 seconds
                reason="Element may need more time to appear"
            ))
            adjustments.append(StrategyAdjustment(
                target_platform=analysis.platform,
                adjustment_type="selector_strategy",
                parameter="fallback_count",
                new_value=5,  # Try 5 selectors
                reason="Primary selector may have changed"
            ))
        
        elif analysis.failure_pattern == FailurePattern.ELEMENT_NOT_CLICKABLE:
            adjustments.append(StrategyAdjustment(
                target_platform=analysis.platform,
                adjustment_type="interaction",
                parameter="scroll_before_click",
                new_value=True,
                reason="Element may be off-screen or obscured"
            ))
            adjustments.append(StrategyAdjustment(
                target_platform=analysis.platform,
                adjustment_type="wait_time",
                parameter="post_animation_wait",
                new_value=1.0,
                reason="Wait for animations to complete"
            ))
        
        elif analysis.failure_pattern == FailurePattern.FORM_VALIDATION_ERROR:
            adjustments.append(StrategyAdjustment(
                target_platform=analysis.platform,
                adjustment_type="field_detection",
                parameter="required_field_check",
                new_value=True,
                reason="Ensure all required fields are filled"
            ))
        
        elif analysis.failure_pattern == FailurePattern.TIMEOUT:
            adjustments.append(StrategyAdjustment(
                target_platform=analysis.platform,
                adjustment_type="timeout",
                parameter="page_load_timeout",
                new_value=120,  # 2 minutes
                reason="Page loads slowly"
            ))
        
        elif analysis.failure_pattern == FailurePattern.CAPTCHA_DETECTED:
            adjustments.append(StrategyAdjustment(
                target_platform=analysis.platform,
                adjustment_type="strategy",
                parameter="captcha_handling",
                new_value="manual_review",
                reason="Cannot auto-solve CAPTCHA"
            ))
        
        elif analysis.failure_pattern == FailurePattern.CONFIRMATION_NOT_FOUND:
            adjustments.append(StrategyAdjustment(
                target_platform=analysis.platform,
                adjustment_type="wait_time",
                parameter="post_submit_wait",
                new_value=10.0,  # 10 seconds
                reason="Confirmation may take longer to appear"
            ))
        
        # Store adjustments for this platform
        if analysis.platform not in self.platform_adjustments:
            self.platform_adjustments[analysis.platform] = []
        self.platform_adjustments[analysis.platform].extend(adjustments)
        
        return adjustments
    
    def get_platform_strategy(self, platform: str) -> Dict[str, Any]:
        """
        Get accumulated strategy adjustments for a platform.
        
        Args:
            platform: Platform name
            
        Returns:
            Dict of strategy parameters
        """
        strategy = {
            "wait_times": {
                "pre_selector": 2.0,
                "post_action": 1.0,
                "post_submit": 5.0,
            },
            "selector_strategy": {
                "fallback_count": 3,
                "retry_attempts": 3,
            },
            "interaction": {
                "scroll_before_click": False,
                "human_like_delays": True,
            },
            "captcha_handling": "auto",
        }
        
        # Apply learned adjustments
        adjustments = self.platform_adjustments.get(platform, [])
        for adj in adjustments:
            if adj.adjustment_type == "wait_time":
                strategy["wait_times"][adj.parameter] = adj.new_value
            elif adj.adjustment_type == "selector_strategy":
                strategy["selector_strategy"][adj.parameter] = adj.new_value
            elif adj.adjustment_type == "interaction":
                strategy["interaction"][adj.parameter] = adj.new_value
            elif adj.adjustment_type == "timeout":
                strategy["wait_times"][adj.parameter] = adj.new_value
            elif adj.adjustment_type == "strategy":
                strategy[adj.parameter] = adj.new_value
        
        return strategy
    
    def get_iteration_report(self, hours: int = 24) -> str:
        """Generate report of failures and suggested improvements."""
        failures = self.monitor.get_recent_failures(hours=hours)
        
        if not failures:
            return "No failures in the last 24 hours. All systems operating normally."
        
        report = f"""
{'='*70}
ITERATION REPORT - Last {hours} hours
{'='*70}

Failures Analyzed: {len(failures)}

Detailed Analysis:
"""
        
        for failure in failures:
            analysis = self.analyze_failure(failure["application_id"])
            if analysis:
                report += f"""
  Application: {failure['application_id'][:20]}...
  Platform: {failure['platform']}
  Pattern: {analysis.failure_pattern.value}
  Confidence: {analysis.confidence*100:.0f}%
  Suggested Fix: {analysis.suggested_fix}
  ---
"""
        
        # Platform strategies
        report += "\nLearned Platform Strategies:\n"
        for platform in set(f["platform"] for f in failures):
            strategy = self.get_platform_strategy(platform)
            report += f"\n  {platform}:\n"
            report += f"    Wait times: {strategy['wait_times']}\n"
            report += f"    Fallback selectors: {strategy['selector_strategy']['fallback_count']}\n"
        
        report += "="*70 + "\n"
        
        return report


# Global instance
_iteration_engine: Optional[IterationEngine] = None


def get_iteration_engine() -> IterationEngine:
    """Get or create global iteration engine."""
    global _iteration_engine
    if _iteration_engine is None:
        _iteration_engine = IterationEngine()
    return _iteration_engine
