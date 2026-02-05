"""
Application Monitoring & Feedback System

Production-grade monitoring for real job applications with:
- Comprehensive logging of every action
- Real-time success/failure tracking
- Automatic retry with iteration
- Screenshot evidence collection
- Follow-up verification
- Performance metrics
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio


class ApplicationEventType(Enum):
    """Types of application events."""
    STARTED = "started"
    NAVIGATING = "navigating"
    FIELD_FILLED = "field_filled"
    FILE_UPLOADED = "file_uploaded"
    QUESTION_ANSWERED = "question_answered"
    SCREENSHOT_CAPTURED = "screenshot_captured"
    SUBMIT_ATTEMPTED = "submit_attempted"
    SUBMIT_SUCCESS = "submit_success"
    SUBMIT_FAILED = "submit_failed"
    CONFIRMATION_FOUND = "confirmation_found"
    ERROR_OCCURRED = "error_occurred"
    RETRY_ATTEMPT = "retry_attempt"
    FOLLOW_UP_CHECK = "follow_up_check"


@dataclass
class ApplicationEvent:
    """Single event in an application process."""
    timestamp: str
    event_type: str
    application_id: str
    job_id: str
    platform: str
    message: str
    details: Dict[str, Any]
    screenshot_path: Optional[str] = None
    success: Optional[bool] = None


@dataclass
class ApplicationMetrics:
    """Metrics for an application attempt."""
    application_id: str
    job_url: str
    platform: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: float = 0.0
    steps_completed: int = 0
    fields_filled: int = 0
    questions_answered: int = 0
    screenshots_count: int = 0
    retry_count: int = 0
    success: bool = False
    confirmation_id: Optional[str] = None
    error_message: Optional[str] = None
    final_status: str = "unknown"


class ApplicationMonitor:
    """
    Production monitoring for job applications.
    
    Tracks every action, captures evidence, and enables iteration.
    """
    
    def __init__(self, db_path: str = "./data/application_monitor.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True, parents=True)
        
        # Set up logging
        self.logger = logging.getLogger("ApplicationMonitor")
        self.logger.setLevel(logging.DEBUG)
        
        # File handler for detailed logs
        fh = logging.FileHandler("./logs/applications.log")
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        # Evidence directory
        self.evidence_dir = Path("./logs/evidence")
        self.evidence_dir.mkdir(exist_ok=True, parents=True)
        
        self._init_db()
        self.current_application: Optional[str] = None
        self.event_buffer: List[ApplicationEvent] = []
    
    def _init_db(self):
        """Initialize monitoring database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS application_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    event_type TEXT,
                    application_id TEXT,
                    job_id TEXT,
                    platform TEXT,
                    message TEXT,
                    details TEXT,
                    screenshot_path TEXT,
                    success BOOLEAN
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS application_metrics (
                    application_id TEXT PRIMARY KEY,
                    job_url TEXT,
                    platform TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds REAL,
                    steps_completed INTEGER,
                    fields_filled INTEGER,
                    questions_answered INTEGER,
                    screenshots_count INTEGER,
                    retry_count INTEGER,
                    success BOOLEAN,
                    confirmation_id TEXT,
                    error_message TEXT,
                    final_status TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS platform_stats (
                    platform TEXT PRIMARY KEY,
                    total_attempts INTEGER DEFAULT 0,
                    successful INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    avg_duration REAL DEFAULT 0,
                    last_updated TEXT
                )
            """)
            
            conn.commit()
    
    def start_application(self, application_id: str, job_url: str, platform: str) -> str:
        """Start monitoring a new application."""
        self.current_application = application_id
        self.event_buffer = []
        
        self.log_event(
            event_type=ApplicationEventType.STARTED,
            message=f"Starting application to {platform}",
            details={"job_url": job_url}
        )
        
        # Initialize metrics
        metrics = ApplicationMetrics(
            application_id=application_id,
            job_url=job_url,
            platform=platform,
            start_time=datetime.now().isoformat()
        )
        
        self._save_metrics(metrics)
        
        self.logger.info(f"[{application_id}] Application started: {job_url}")
        return application_id
    
    def log_event(self, event_type: ApplicationEventType, message: str, 
                  details: Dict[str, Any] = None, screenshot_path: str = None,
                  success: bool = None):
        """Log an application event."""
        if not self.current_application:
            return
        
        event = ApplicationEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type.value,
            application_id=self.current_application,
            job_id=self.current_application,
            platform="unknown",  # Will be updated from metrics
            message=message,
            details=details or {},
            screenshot_path=screenshot_path,
            success=success
        )
        
        self.event_buffer.append(event)
        
        # Log to file
        log_msg = f"[{self.current_application}] {event_type.value}: {message}"
        if details:
            log_msg += f" | Details: {json.dumps(details)}"
        
        if success is True:
            self.logger.info(log_msg)
        elif success is False:
            self.logger.error(log_msg)
        else:
            self.logger.debug(log_msg)
        
        # Persist to DB every 5 events
        if len(self.event_buffer) >= 5:
            self._flush_events()
    
    def log_field_filled(self, field_name: str, field_type: str, value_preview: str = None):
        """Log a field being filled."""
        self.log_event(
            event_type=ApplicationEventType.FIELD_FILLED,
            message=f"Filled field: {field_name}",
            details={
                "field_name": field_name,
                "field_type": field_type,
                "value_preview": value_preview or "[REDACTED]"
            }
        )
    
    def log_question_answered(self, question: str, answer_preview: str):
        """Log a question being answered."""
        self.log_event(
            event_type=ApplicationEventType.QUESTION_ANSWERED,
            message=f"Answered question: {question[:100]}...",
            details={
                "question": question,
                "answer_preview": answer_preview[:100]
            }
        )
    
    def log_screenshot(self, screenshot_path: str, step_name: str):
        """Log screenshot capture."""
        self.log_event(
            event_type=ApplicationEventType.SCREENSHOT_CAPTURED,
            message=f"Screenshot captured: {step_name}",
            screenshot_path=screenshot_path,
            details={"step_name": step_name}
        )
    
    def log_submit_attempt(self):
        """Log submission attempt."""
        self.log_event(
            event_type=ApplicationEventType.SUBMIT_ATTEMPTED,
            message="Submit button clicked"
        )
    
    def log_submit_success(self, confirmation_id: str = None):
        """Log successful submission."""
        self.log_event(
            event_type=ApplicationEventType.SUBMIT_SUCCESS,
            message="Application submitted successfully",
            success=True,
            details={"confirmation_id": confirmation_id}
        )
    
    def log_submit_failed(self, error_message: str):
        """Log failed submission."""
        self.log_event(
            event_type=ApplicationEventType.SUBMIT_FAILED,
            message=f"Submission failed: {error_message}",
            success=False,
            details={"error": error_message}
        )
    
    def log_error(self, error: Exception, context: str = None):
        """Log an error."""
        self.log_event(
            event_type=ApplicationEventType.ERROR_OCCURRED,
            message=f"Error: {str(error)}",
            success=False,
            details={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context
            }
        )
    
    def log_retry(self, attempt_number: int, reason: str):
        """Log retry attempt."""
        self.log_event(
            event_type=ApplicationEventType.RETRY_ATTEMPT,
            message=f"Retry attempt {attempt_number}: {reason}",
            details={"attempt": attempt_number, "reason": reason}
        )
    
    def finish_application(self, success: bool, confirmation_id: str = None, 
                          error_message: str = None, metrics: Dict[str, Any] = None):
        """Finish monitoring an application."""
        if not self.current_application:
            return
        
        end_time = datetime.now()
        
        # Calculate duration
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT start_time FROM application_metrics WHERE application_id = ?",
                (self.current_application,)
            ).fetchone()
            
            if row:
                start_time = datetime.fromisoformat(row[0])
                duration = (end_time - start_time).total_seconds()
            else:
                duration = 0
        
        # Update metrics
        final_metrics = {
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "success": success,
            "confirmation_id": confirmation_id,
            "error_message": error_message,
            "final_status": "submitted" if success else "failed"
        }
        
        if metrics:
            final_metrics.update(metrics)
        
        self._update_metrics(self.current_application, final_metrics)
        
        # Log final status
        if success:
            self.logger.info(
                f"[{self.current_application}] Application SUCCESS - "
                f"Confirmation: {confirmation_id}"
            )
        else:
            self.logger.error(
                f"[{self.current_application}] Application FAILED - "
                f"Error: {error_message}"
            )
        
        # Flush remaining events
        self._flush_events()
        
        # Update platform stats
        self._update_platform_stats(
            self._get_platform(self.current_application),
            success,
            duration
        )
        
        self.current_application = None
    
    def _flush_events(self):
        """Persist buffered events to database."""
        if not self.event_buffer:
            return
        
        with sqlite3.connect(self.db_path) as conn:
            for event in self.event_buffer:
                conn.execute("""
                    INSERT INTO application_events 
                    (timestamp, event_type, application_id, job_id, platform, 
                     message, details, screenshot_path, success)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.timestamp,
                    event.event_type,
                    event.application_id,
                    event.job_id,
                    event.platform,
                    event.message,
                    json.dumps(event.details),
                    event.screenshot_path,
                    event.success
                ))
            conn.commit()
        
        self.event_buffer = []
    
    def _save_metrics(self, metrics: ApplicationMetrics):
        """Save metrics to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO application_metrics
                (application_id, job_url, platform, start_time, end_time,
                 duration_seconds, steps_completed, fields_filled, 
                 questions_answered, screenshots_count, retry_count,
                 success, confirmation_id, error_message, final_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.application_id, metrics.job_url, metrics.platform,
                metrics.start_time, metrics.end_time, metrics.duration_seconds,
                metrics.steps_completed, metrics.fields_filled,
                metrics.questions_answered, metrics.screenshots_count,
                metrics.retry_count, metrics.success, metrics.confirmation_id,
                metrics.error_message, metrics.final_status
            ))
            conn.commit()
    
    def _update_metrics(self, application_id: str, updates: Dict[str, Any]):
        """Update metrics for an application."""
        with sqlite3.connect(self.db_path) as conn:
            for key, value in updates.items():
                conn.execute(
                    f"UPDATE application_metrics SET {key} = ? WHERE application_id = ?",
                    (value, application_id)
                )
            conn.commit()
    
    def _get_platform(self, application_id: str) -> str:
        """Get platform for an application."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT platform FROM application_metrics WHERE application_id = ?",
                (application_id,)
            ).fetchone()
            return row[0] if row else "unknown"
    
    def _update_platform_stats(self, platform: str, success: bool, duration: float):
        """Update platform statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Get current stats
            row = conn.execute(
                "SELECT * FROM platform_stats WHERE platform = ?",
                (platform,)
            ).fetchone()
            
            if row:
                total = row[1] + 1
                successful = row[2] + (1 if success else 0)
                failed = row[3] + (0 if success else 1)
                # Rolling average
                avg_duration = (row[4] * row[1] + duration) / total
                
                conn.execute("""
                    UPDATE platform_stats 
                    SET total_attempts = ?, successful = ?, failed = ?,
                        avg_duration = ?, last_updated = ?
                    WHERE platform = ?
                """, (total, successful, failed, avg_duration, 
                      datetime.now().isoformat(), platform))
            else:
                conn.execute("""
                    INSERT INTO platform_stats 
                    (platform, total_attempts, successful, failed, avg_duration, last_updated)
                    VALUES (?, 1, ?, ?, ?, ?)
                """, (platform, 1 if success else 0, 0 if success else 1,
                      duration, datetime.now().isoformat()))
            
            conn.commit()
    
    def get_application_report(self, application_id: str) -> Dict[str, Any]:
        """Get full report for an application."""
        with sqlite3.connect(self.db_path) as conn:
            # Get metrics
            metrics_row = conn.execute(
                "SELECT * FROM application_metrics WHERE application_id = ?",
                (application_id,)
            ).fetchone()
            
            if not metrics_row:
                return {"error": "Application not found"}
            
            # Get events
            events = conn.execute(
                """SELECT timestamp, event_type, message, details, screenshot_path, success
                   FROM application_events 
                   WHERE application_id = ? 
                   ORDER BY timestamp""",
                (application_id,)
            ).fetchall()
            
            return {
                "application_id": application_id,
                "metrics": {
                    "job_url": metrics_row[1],
                    "platform": metrics_row[2],
                    "start_time": metrics_row[3],
                    "end_time": metrics_row[4],
                    "duration_seconds": metrics_row[5],
                    "steps_completed": metrics_row[6],
                    "fields_filled": metrics_row[7],
                    "questions_answered": metrics_row[8],
                    "screenshots_count": metrics_row[9],
                    "retry_count": metrics_row[10],
                    "success": bool(metrics_row[11]),
                    "confirmation_id": metrics_row[12],
                    "error_message": metrics_row[14],
                    "final_status": metrics_row[15]
                },
                "events": [
                    {
                        "timestamp": e[0],
                        "type": e[1],
                        "message": e[2],
                        "details": json.loads(e[3]) if e[3] else {},
                        "screenshot": e[4],
                        "success": e[5]
                    }
                    for e in events
                ]
            }
    
    def get_platform_success_rates(self) -> Dict[str, Dict[str, Any]]:
        """Get success rates by platform."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM platform_stats").fetchall()
            
            return {
                row[0]: {
                    "total_attempts": row[1],
                    "successful": row[2],
                    "failed": row[3],
                    "success_rate": row[2] / row[1] if row[1] > 0 else 0,
                    "avg_duration_seconds": row[4],
                    "last_updated": row[5]
                }
                for row in rows
            }
    
    def get_recent_failures(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent failed applications for analysis."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT application_id, job_url, platform, error_message, start_time
                FROM application_metrics
                WHERE success = 0 AND start_time > ?
                ORDER BY start_time DESC
            """, (cutoff,)).fetchall()
            
            return [
                {
                    "application_id": r[0],
                    "job_url": r[1],
                    "platform": r[2],
                    "error_message": r[3],
                    "timestamp": r[4]
                }
                for r in rows
            ]
    
    def generate_daily_report(self) -> str:
        """Generate a daily summary report."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        with sqlite3.connect(self.db_path) as conn:
            # Today's stats
            today_start = f"{today}T00:00:00"
            today_end = f"{today}T23:59:59"
            
            row = conn.execute("""
                SELECT 
                    COUNT(*),
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END)
                FROM application_metrics
                WHERE start_time BETWEEN ? AND ?
            """, (today_start, today_end)).fetchone()
            
            total = row[0] or 0
            successful = row[1] or 0
            failed = row[2] or 0
        
        report = f"""
{'='*70}
DAILY APPLICATION REPORT - {today}
{'='*70}

Summary:
  Total Applications: {total}
  Successful: {successful} ({successful/total*100:.1f}% if total > 0 else 0%)
  Failed: {failed} ({failed/total*100:.1f}% if total > 0 else 0%)

Platform Success Rates:
"""
        
        for platform, stats in self.get_platform_success_rates().items():
            report += f"  {platform:15s}: {stats['success']}/{stats['total_attempts']} ({stats['success_rate']*100:.1f}%)\n"
        
        if failed > 0:
            report += "\nRecent Failures:\n"
            for failure in self.get_recent_failures(hours=24)[:5]:
                report += f"  • {failure['platform']}: {failure['error_message'][:60]}...\n"
        
        report += "="*70 + "\n"
        
        return report


# Global monitor instance
_monitor: Optional[ApplicationMonitor] = None


def get_monitor() -> ApplicationMonitor:
    """Get or create global monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = ApplicationMonitor()
    return _monitor
