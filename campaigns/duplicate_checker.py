#!/usr/bin/env python3
"""
Duplicate Job Application Checker & Verification System

Features:
1. Pre-application duplicate detection
2. Post-application verification
3. Campaign progress tracking
4. Resume-specific application history
"""

import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ApplicationRecord:
    """Represents an application record."""
    id: str
    user_id: str
    job_url: str
    job_title: str
    company: str
    platform: str
    status: str
    created_at: datetime
    
    @property
    def is_successful(self) -> bool:
        return self.status in ['completed', 'success', 'submitted', 'applied']
    
    @property
    def is_duplicate_check_needed(self) -> bool:
        return self.status not in ['error', 'failed', 'cancelled']


class DuplicateChecker:
    """Checks for and prevents duplicate job applications."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(__file__).parent.parent / "data" / "job_applier.db")
        self.db_path = db_path
        self._init_duplicate_tracking()
    
    def _init_duplicate_tracking(self):
        """Initialize duplicate tracking tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Create unique index to prevent duplicates at database level
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_applications_user_url 
                ON applications(user_id, job_url)
            """)
            
            # Create applied jobs cache table for fast lookup
            conn.execute("""
                CREATE TABLE IF NOT EXISTS applied_jobs_cache (
                    user_id TEXT NOT NULL,
                    job_url_hash TEXT NOT NULL,
                    job_url TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    campaign_id TEXT,
                    PRIMARY KEY (user_id, job_url_hash)
                )
            """)
            
            # Create verification log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verification_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    campaign_id TEXT,
                    job_url TEXT,
                    verification_type TEXT,
                    status TEXT,
                    details TEXT,
                    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def _hash_url(self, url: str) -> str:
        """Create hash of URL for fast comparison."""
        # Normalize URL before hashing
        normalized = url.lower().strip().rstrip('/')
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]
    
    def is_already_applied(self, user_id: str, job_url: str) -> bool:
        """Check if a job has already been applied to."""
        url_hash = self._hash_url(job_url)
        
        with sqlite3.connect(self.db_path) as conn:
            # Check cache first (fast)
            cursor = conn.execute(
                "SELECT 1 FROM applied_jobs_cache WHERE user_id = ? AND job_url_hash = ?",
                (user_id, url_hash)
            )
            if cursor.fetchone():
                return True
            
            # Check applications table
            cursor = conn.execute(
                """SELECT 1 FROM applications 
                   WHERE user_id = ? AND job_url = ? 
                   AND status NOT IN ('error', 'failed', 'cancelled')
                   LIMIT 1""",
                (user_id, job_url)
            )
            if cursor.fetchone():
                # Add to cache for future fast lookups
                self._add_to_cache(user_id, job_url)
                return True
        
        return False
    
    def _add_to_cache(self, user_id: str, job_url: str, campaign_id: str = None):
        """Add applied job to cache."""
        url_hash = self._hash_url(job_url)
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO applied_jobs_cache 
                       (user_id, job_url_hash, job_url, applied_at, campaign_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (user_id, url_hash, job_url, datetime.now().isoformat(), campaign_id)
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # Already exists
    
    def get_applied_urls(self, user_id: str) -> Set[str]:
        """Get all URLs that have been applied to."""
        applied = set()
        
        with sqlite3.connect(self.db_path) as conn:
            # From cache
            cursor = conn.execute(
                "SELECT job_url FROM applied_jobs_cache WHERE user_id = ?",
                (user_id,)
            )
            applied.update(row[0] for row in cursor.fetchall())
            
            # From applications table
            cursor = conn.execute(
                """SELECT job_url FROM applications 
                   WHERE user_id = ? AND status NOT IN ('error', 'failed', 'cancelled')""",
                (user_id,)
            )
            applied.update(row[0] for row in cursor.fetchall())
        
        return applied
    
    def filter_duplicates(self, user_id: str, job_urls: List[str]) -> Tuple[List[str], List[str]]:
        """
        Filter out duplicate URLs from a list.
        Returns: (new_urls, duplicate_urls)
        """
        applied = self.get_applied_urls(user_id)
        
        new_urls = []
        duplicate_urls = []
        
        for url in job_urls:
            if url in applied or self.is_already_applied(user_id, url):
                duplicate_urls.append(url)
            else:
                new_urls.append(url)
        
        return new_urls, duplicate_urls
    
    def record_application(self, user_id: str, job_url: str, campaign_id: str = None, 
                          status: str = "applied"):
        """Record a job application."""
        self._add_to_cache(user_id, job_url, campaign_id)
        
        # Log verification
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO verification_log 
                   (user_id, campaign_id, job_url, verification_type, status, details)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, campaign_id, job_url, "application", status, 
                 json.dumps({"timestamp": datetime.now().isoformat()}))
            )
            conn.commit()
    
    def verify_campaign(self, user_id: str, campaign_id: str, 
                       expected_urls: List[str]) -> Dict:
        """
        Verify a campaign's applications.
        Returns verification report.
        """
        applied = self.get_applied_urls(user_id)
        
        verified = []
        missing = []
        
        for url in expected_urls:
            if url in applied:
                verified.append(url)
            else:
                missing.append(url)
        
        report = {
            "campaign_id": campaign_id,
            "user_id": user_id,
            "total_expected": len(expected_urls),
            "verified_applied": len(verified),
            "missing": len(missing),
            "success_rate": (len(verified) / len(expected_urls) * 100) if expected_urls else 0,
            "verified_at": datetime.now().isoformat(),
            "missing_urls": missing[:10]  # First 10 missing
        }
        
        # Log verification
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO verification_log 
                   (user_id, campaign_id, verification_type, status, details)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, campaign_id, "campaign_verification", 
                 "complete" if not missing else "incomplete",
                 json.dumps(report))
            )
            conn.commit()
        
        return report
    
    def get_application_stats(self, user_id: str) -> Dict:
        """Get application statistics for a user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT status, COUNT(*) as count 
                   FROM applications 
                   WHERE user_id = ?
                   GROUP BY status""",
                (user_id,)
            )
            status_counts = dict(cursor.fetchall())
            
            cursor = conn.execute(
                """SELECT COUNT(DISTINCT job_url) as total 
                   FROM applied_jobs_cache WHERE user_id = ?""",
                (user_id,)
            )
            cache_count = cursor.fetchone()[0]
        
        return {
            "total_applications": sum(status_counts.values()),
            "by_status": status_counts,
            "cached_unique": cache_count,
            "last_updated": datetime.now().isoformat()
        }
    
    def deduplicate_job_list(self, job_urls: List[str]) -> List[str]:
        """Remove duplicates from a job URL list while preserving order."""
        seen = set()
        unique = []
        
        for url in job_urls:
            normalized = url.lower().strip().rstrip('/')
            if normalized not in seen:
                seen.add(normalized)
                unique.append(url)
        
        return unique


class CampaignTracker:
    """Tracks campaign progress and verifies applications."""
    
    def __init__(self, user_id: str, campaign_id: str, db_path: str = None):
        self.user_id = user_id
        self.campaign_id = campaign_id
        self.checker = DuplicateChecker(db_path)
        self.job_queue: List[str] = []
        self.applied_jobs: List[str] = []
        self.failed_jobs: List[str] = []
    
    def load_jobs(self, job_urls: List[str]):
        """Load jobs into the campaign, filtering duplicates."""
        # Deduplicate input
        unique_urls = self.checker.deduplicate_job_list(job_urls)
        
        # Filter already applied
        new_urls, duplicates = self.checker.filter_duplicates(self.user_id, unique_urls)
        
        self.job_queue = new_urls
        
        print(f"📋 Campaign {self.campaign_id}:")
        print(f"   Total input: {len(job_urls)}")
        print(f"   Unique: {len(unique_urls)}")
        print(f"   New (not yet applied): {len(new_urls)}")
        print(f"   Duplicates skipped: {len(duplicates)}")
        
        return new_urls, duplicates
    
    def record_success(self, job_url: str):
        """Record successful application."""
        self.applied_jobs.append(job_url)
        self.checker.record_application(
            self.user_id, job_url, self.campaign_id, "applied"
        )
    
    def record_failure(self, job_url: str):
        """Record failed application."""
        self.failed_jobs.append(job_url)
    
    def get_progress(self) -> Dict:
        """Get campaign progress."""
        total = len(self.job_queue) + len(self.applied_jobs) + len(self.failed_jobs)
        completed = len(self.applied_jobs) + len(self.failed_jobs)
        
        return {
            "campaign_id": self.campaign_id,
            "total_jobs": total,
            "completed": completed,
            "successful": len(self.applied_jobs),
            "failed": len(self.failed_jobs),
            "remaining": len(self.job_queue),
            "progress_percent": (completed / total * 100) if total > 0 else 0
        }
    
    def verify(self) -> Dict:
        """Verify all applications in this campaign."""
        all_expected = self.applied_jobs + self.failed_jobs + self.job_queue
        return self.checker.verify_campaign(
            self.user_id, self.campaign_id, all_expected
        )


def main():
    """Test duplicate checker."""
    print("🔍 Testing Duplicate Checker\n")
    
    checker = DuplicateChecker()
    
    # Test user
    test_user = "test_user_123"
    
    # Test URLs
    test_urls = [
        "https://indeed.com/job/123",
        "https://indeed.com/job/456",
        "https://linkedin.com/job/789",
    ]
    
    # Check if applied
    print("Checking application status:")
    for url in test_urls:
        status = "✅ Already applied" if checker.is_already_applied(test_user, url) else "❌ Not applied"
        print(f"   {url[:40]}... {status}")
    
    # Record applications
    print("\nRecording test applications...")
    for url in test_urls[:2]:
        checker.record_application(test_user, url, "test_campaign")
        print(f"   Recorded: {url[:40]}...")
    
    # Check again
    print("\nChecking after recording:")
    for url in test_urls:
        status = "✅ Already applied" if checker.is_already_applied(test_user, url) else "❌ Not applied"
        print(f"   {url[:40]}... {status}")
    
    # Filter duplicates
    print("\nFiltering duplicates from list:")
    new_urls, dups = checker.filter_duplicates(test_user, test_urls)
    print(f"   New: {len(new_urls)}, Duplicates: {len(dups)}")
    
    # Stats
    print("\nApplication stats:")
    stats = checker.get_application_stats(test_user)
    print(f"   {json.dumps(stats, indent=2)}")
    
    print("\n✅ Duplicate checker test complete!")


if __name__ == "__main__":
    main()
