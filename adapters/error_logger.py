"""
Comprehensive Error Logging System for Job Applications
Tracks all errors with categorization, context, and recommendations
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import traceback


class ErrorCategory(Enum):
    """Categories of application errors."""
    CAPTCHA = "captcha"                    # CAPTCHA/verification blocks
    TIMEOUT = "timeout"                    # Page load/submission timeouts
    FORM_ERROR = "form_error"              # Form filling/validation errors
    NAVIGATION = "navigation"              # Page navigation issues
    BROWSER = "browser"                    # Browser/session errors
    NETWORK = "network"                    # Connection issues
    EXTERNAL_REDIRECT = "external"         # External application redirect
    RATE_LIMIT = "rate_limit"              # IP/account rate limiting
    VALIDATION = "validation"              # Post-submission validation failure
    UNKNOWN = "unknown"                    # Uncategorized errors


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    CRITICAL = "critical"      # Blocks entire campaign
    HIGH = "high"              # Affects many applications
    MEDIUM = "medium"          # Affects some applications
    LOW = "low"                # Minor issue, auto-recoverable
    INFO = "info"              # Informational only


@dataclass
class ErrorRecord:
    """Detailed error record."""
    timestamp: str
    job_id: str
    company: str
    job_title: str
    job_url: str
    category: str
    severity: str
    error_message: str
    error_type: str
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    resolved: bool = False
    resolution_notes: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ApplicationErrorLogger:
    """
    Centralized error logging for job application campaigns.
    
    Features:
    - Categorizes all errors automatically
    - Tracks retry attempts
    - Saves screenshots on error
    - Generates error reports
    - Provides recommendations
    """
    
    def __init__(self, output_dir: str = "campaigns/output/error_logs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.errors: List[ErrorRecord] = []
        self.error_counts: Dict[str, int] = {cat.value: 0 for cat in ErrorCategory}
        
        # Setup file logging
        self.logger = logging.getLogger("ApplicationErrors")
        self.logger.setLevel(logging.DEBUG)
        
        log_file = self.output_dir / f"error_log_{datetime.now().strftime('%Y%m%d_%H%M')}.log"
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(handler)
        
    def categorize_error(self, error_message: str, exception: Optional[Exception] = None) -> tuple:
        """Automatically categorize an error."""
        message_lower = error_message.lower()
        error_type = type(exception).__name__ if exception else "Unknown"
        
        # CAPTCHA patterns
        if any(x in message_lower for x in ['captcha', 'verification', 'cloudflare', 'ray id', 'are you human']):
            return ErrorCategory.CAPTCHA, ErrorSeverity.HIGH
        
        # Timeout patterns
        if any(x in message_lower for x in ['timeout', 'timed out', 'took too long']):
            return ErrorCategory.TIMEOUT, ErrorSeverity.MEDIUM
        
        # Form error patterns
        if any(x in message_lower for x in ['form', 'field', 'validation', 'required', 'invalid input']):
            return ErrorCategory.FORM_ERROR, ErrorSeverity.MEDIUM
        
        # Navigation patterns
        if any(x in message_lower for x in ['navigation', 'page.goto', 'net::', 'could not navigate']):
            return ErrorCategory.NAVIGATION, ErrorSeverity.MEDIUM
        
        # Network patterns
        if any(x in message_lower for x in ['network', 'connection', 'refused', 'dns', 'proxy']):
            return ErrorCategory.NETWORK, ErrorSeverity.HIGH
        
        # Rate limit patterns
        if any(x in message_lower for x in ['rate limit', '429', 'too many requests', 'blocked']):
            return ErrorCategory.RATE_LIMIT, ErrorSeverity.CRITICAL
        
        # External redirect patterns
        if any(x in message_lower for x in ['external', 'apply on company', 'redirect', 'company site']):
            return ErrorCategory.EXTERNAL_REDIRECT, ErrorSeverity.INFO
        
        # Browser patterns
        if any(x in message_lower for x in ['browser', 'session', 'page closed', 'context destroyed']):
            return ErrorCategory.BROWSER, ErrorSeverity.HIGH
        
        # Validation patterns
        if any(x in message_lower for x in ['validation', 'submit button not found', 'form still present']):
            return ErrorCategory.VALIDATION, ErrorSeverity.MEDIUM
        
        return ErrorCategory.UNKNOWN, ErrorSeverity.LOW
    
    def log_error(
        self,
        job_id: str,
        company: str,
        job_title: str,
        job_url: str,
        error_message: str,
        exception: Optional[Exception] = None,
        screenshot_path: Optional[str] = None,
        context: Optional[Dict] = None,
        retry_count: int = 0
    ) -> ErrorRecord:
        """Log an application error."""
        
        # Categorize the error
        category, severity = self.categorize_error(error_message, exception)
        
        # Get stack trace if exception provided
        stack_trace = None
        if exception:
            stack_trace = traceback.format_exc()
        
        # Create error record
        record = ErrorRecord(
            timestamp=datetime.now().isoformat(),
            job_id=job_id,
            company=company,
            job_title=job_title,
            job_url=job_url,
            category=category.value,
            severity=severity.value,
            error_message=error_message,
            error_type=type(exception).__name__ if exception else "Unknown",
            stack_trace=stack_trace,
            screenshot_path=screenshot_path,
            context=context or {},
            retry_count=retry_count,
            resolved=False
        )
        
        # Store and count
        self.errors.append(record)
        self.error_counts[category.value] += 1
        
        # Log to file
        self.logger.error(
            f"[{category.value.upper()}] {company} - {job_title}: {error_message}"
        )
        
        return record
    
    def get_error_summary(self) -> Dict:
        """Get summary of all errors."""
        total = len(self.errors)
        by_category = {}
        by_severity = {}
        
        for error in self.errors:
            cat = error.category
            sev = error.severity
            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1
        
        return {
            "total_errors": total,
            "by_category": by_category,
            "by_severity": by_severity,
            "top_errors": self._get_top_errors(10)
        }
    
    def _get_top_errors(self, n: int = 10) -> List[Dict]:
        """Get most common error messages."""
        message_counts = {}
        for error in self.errors:
            msg = error.error_message[:100]  # Truncate
            message_counts[msg] = message_counts.get(msg, 0) + 1
        
        sorted_msgs = sorted(message_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"message": msg, "count": count} for msg, count in sorted_msgs[:n]]
    
    def get_recommendations(self) -> List[str]:
        """Generate recommendations based on error patterns."""
        recommendations = []
        summary = self.get_error_summary()
        
        # CAPTCHA recommendations
        captcha_count = summary["by_category"].get(ErrorCategory.CAPTCHA.value, 0)
        if captcha_count > 10:
            pct = (captcha_count / summary["total_errors"]) * 100
            recommendations.append(
                f"🤖 CAPTCHA Blockage: {captcha_count} errors ({pct:.1f}%). "
                "Recommend: Enable CAPTCHA solving service (2Captcha/CapSolver)"
            )
        
        # Timeout recommendations
        timeout_count = summary["by_category"].get(ErrorCategory.TIMEOUT.value, 0)
        if timeout_count > 20:
            recommendations.append(
                f"⏱️  Timeouts: {timeout_count} errors. "
                "Recommend: Increase page load timeout, check network stability"
            )
        
        # Rate limit recommendations
        rate_limit_count = summary["by_category"].get(ErrorCategory.RATE_LIMIT.value, 0)
        if rate_limit_count > 0:
            recommendations.append(
                f"🚫 Rate Limiting: {rate_limit_count} errors. "
                "Recommend: Add delays between requests, use proxy rotation"
            )
        
        # Form error recommendations
        form_error_count = summary["by_category"].get(ErrorCategory.FORM_ERROR.value, 0)
        if form_error_count > 30:
            recommendations.append(
                f"📝 Form Errors: {form_error_count} errors. "
                "Recommend: Improve form field detection, add AI form filling"
            )
        
        # External redirect recommendations
        external_count = summary["by_category"].get(ErrorCategory.EXTERNAL_REDIRECT.value, 0)
        if external_count > 100:
            recommendations.append(
                f"🔗 External Redirects: {external_count} errors. "
                "Recommend: Implement external ATS handlers (Greenhouse, Lever, Workday)"
            )
        
        return recommendations
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate comprehensive error report."""
        summary = self.get_error_summary()
        recommendations = self.get_recommendations()
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "recommendations": recommendations,
            "error_counts": self.error_counts,
            "total_logged": len(self.errors),
            "recent_errors": [e.to_dict() for e in self.errors[-20:]]
        }
        
        # Save to file
        if not output_file:
            output_file = self.output_dir / f"error_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        else:
            output_file = Path(output_file)
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return str(output_file)
    
    def save_checkpoint(self, filename: Optional[str] = None):
        """Save all errors to checkpoint file."""
        if not filename:
            filename = self.output_dir / f"error_checkpoint_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "errors": [e.to_dict() for e in self.errors],
            "error_counts": self.error_counts
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        return str(filename)
    
    def load_checkpoint(self, filename: str):
        """Load errors from checkpoint."""
        with open(filename) as f:
            data = json.load(f)
        
        self.errors = [ErrorRecord(**e) for e in data.get('errors', [])]
        self.error_counts = data.get('error_counts', {})


# Global error logger instance
_error_logger: Optional[ApplicationErrorLogger] = None


def get_error_logger(output_dir: str = "campaigns/output/error_logs") -> ApplicationErrorLogger:
    """Get or create global error logger."""
    global _error_logger
    if _error_logger is None:
        _error_logger = ApplicationErrorLogger(output_dir)
    return _error_logger
