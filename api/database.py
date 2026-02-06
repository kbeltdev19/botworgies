"""
Database module for Job Applier API.
Implements SQLite persistence with async support.
"""

import os
import json
import asyncio
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager
import uuid

# Database configuration
DB_PATH = Path(os.getenv("DATABASE_PATH", Path(__file__).parent.parent / "data" / "job_applier.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


async def init_database():
    """Initialize the database schema."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)

        # User profiles table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                phone TEXT,
                linkedin_url TEXT,
                years_experience INTEGER,
                work_authorization TEXT DEFAULT 'Yes',
                sponsorship_required TEXT DEFAULT 'No',
                custom_answers TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Resumes table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                raw_text TEXT,
                parsed_data TEXT,
                tailored_version TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Applications table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                job_url TEXT NOT NULL,
                job_title TEXT,
                company TEXT,
                platform TEXT,
                status TEXT,
                message TEXT,
                error TEXT,
                screenshot_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # User settings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                daily_limit INTEGER DEFAULT 10,
                linkedin_cookie_encrypted TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Jobs cache table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs_cache (
                cache_key TEXT PRIMARY KEY,
                jobs_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        """)

        # Campaigns (persistent, pause/resume/stop)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT,
                status TEXT NOT NULL,
                config_json TEXT,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Persistent job queue with retries/backoff
        await db.execute("""
            CREATE TABLE IF NOT EXISTS job_queue (
                id TEXT PRIMARY KEY,
                campaign_id TEXT,
                user_id TEXT NOT NULL,
                job_url TEXT NOT NULL,
                platform TEXT,
                status TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                next_run_at TEXT,
                locked_at TEXT,
                locked_by TEXT,
                last_error TEXT,
                application_id TEXT,
                payload_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
            )
        """)

        # Notification state (for idempotent schedulers)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notification_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_applications_created_at ON applications(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_user_id ON campaigns(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_queue_user_id ON job_queue(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_queue_campaign_id ON job_queue(campaign_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_queue_status_next_run ON job_queue(status, next_run_at)")

        await db.commit()

        # Lightweight migrations for additive columns.
        await _migrate_user_settings(db)
        await _migrate_profiles(db)
        await db.commit()


async def _migrate_user_settings(db: aiosqlite.Connection):
    """Add new optional columns to user_settings if missing."""
    cursor = await db.execute("PRAGMA table_info(user_settings)")
    rows = await cursor.fetchall()
    existing = {row[1] for row in rows}  # (cid, name, type, notnull, dflt, pk)

    migrations = [
        ("platform_daily_limits_json", "TEXT"),
        ("slack_webhook_url", "TEXT"),
        ("discord_webhook_url", "TEXT"),
        ("email_notifications_to", "TEXT"),
    ]

    for col, col_type in migrations:
        if col in existing:
            continue
        await db.execute(f"ALTER TABLE user_settings ADD COLUMN {col} {col_type}")


async def _migrate_profiles(db: aiosqlite.Connection):
    """Add new optional columns to profiles if missing."""
    cursor = await db.execute("PRAGMA table_info(profiles)")
    rows = await cursor.fetchall()
    existing = {row[1] for row in rows}

    migrations = [
        ("location", "TEXT"),
        ("website", "TEXT"),
        ("github_url", "TEXT"),
        ("portfolio_url", "TEXT"),
    ]

    for col, col_type in migrations:
        if col in existing:
            continue
        await db.execute(f"ALTER TABLE profiles ADD COLUMN {col} {col_type}")


@asynccontextmanager
async def get_db():
    """Get a database connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


# User operations
async def create_user(user_id: str, email: str, hashed_password: str) -> bool:
    """Create a new user."""
    async with get_db() as db:
        try:
            await db.execute(
                "INSERT INTO users (id, email, hashed_password) VALUES (?, ?, ?)",
                (user_id, email, hashed_password)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_id(user_id: str) -> Optional[Dict]:
    """Get user by ID."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# Profile operations
async def save_profile(user_id: str, profile: Dict) -> bool:
    """Save or update user profile."""
    async with get_db() as db:
        custom_answers = json.dumps(profile.get("custom_answers", {}))
        await db.execute("""
            INSERT OR REPLACE INTO profiles
            (user_id, first_name, last_name, email, phone, linkedin_url,
             location, website, github_url, portfolio_url,
             years_experience, work_authorization, sponsorship_required, custom_answers, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            profile.get("first_name"),
            profile.get("last_name"),
            profile.get("email"),
            profile.get("phone"),
            profile.get("linkedin_url"),
            profile.get("location"),
            profile.get("website"),
            profile.get("github_url"),
            profile.get("portfolio_url"),
            profile.get("years_experience"),
            profile.get("work_authorization", "Yes"),
            profile.get("sponsorship_required", "No"),
            custom_answers,
            datetime.now().isoformat()
        ))
        await db.commit()
        return True


async def get_profile(user_id: str) -> Optional[Dict]:
    """Get user profile."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            profile = dict(row)
            profile["custom_answers"] = json.loads(profile.get("custom_answers") or "{}")
            return profile
        return None


# Resume operations
async def save_resume(user_id: str, file_path: str, raw_text: str, parsed_data: Dict) -> int:
    """Save a new resume."""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO resumes (user_id, file_path, raw_text, parsed_data)
            VALUES (?, ?, ?, ?)
        """, (user_id, file_path, raw_text, json.dumps(parsed_data)))
        await db.commit()
        return cursor.lastrowid


async def get_latest_resume(user_id: str) -> Optional[Dict]:
    """Get the most recent resume for a user."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM resumes WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            resume = dict(row)
            resume["parsed_data"] = json.loads(resume.get("parsed_data") or "{}")
            resume["tailored_version"] = json.loads(resume.get("tailored_version") or "null")
            return resume
        return None


async def update_resume_tailored(resume_id: int, tailored_version: Dict):
    """Update resume with tailored version."""
    async with get_db() as db:
        await db.execute(
            "UPDATE resumes SET tailored_version = ? WHERE id = ?",
            (json.dumps(tailored_version), resume_id)
        )
        await db.commit()


# Application operations
async def save_application(application: Dict) -> bool:
    """Save an application record."""
    async with get_db() as db:
        await db.execute("""
            INSERT OR REPLACE INTO applications
            (id, user_id, job_url, job_title, company, platform, status, message, error, screenshot_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            application["id"],
            application.get("user_id", "default"),
            application["job_url"],
            application.get("job_title"),
            application.get("company"),
            application.get("platform"),
            application["status"],
            application.get("message"),
            application.get("error"),
            application.get("screenshot_path"),
            application.get("timestamp", datetime.now().isoformat())
        ))
        await db.commit()
        return True


async def get_applications(user_id: str, limit: int = 100) -> List[Dict]:
    """Get applications for a user."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_applications_since(user_id: str, since: datetime, limit: int = 500) -> List[Dict]:
    """Get applications for a user since a given time."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM applications WHERE user_id = ? AND created_at > ? ORDER BY created_at DESC LIMIT ?",
            (user_id, since.isoformat(), limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_application(application_id: str) -> Optional[Dict]:
    """Get a specific application."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def count_applications_since(user_id: str, since: datetime) -> int:
    """Count applications since a given time."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT COUNT(*) as count FROM applications
               WHERE user_id = ? AND created_at > ? AND status NOT IN ('error', 'cancelled')""",
            (user_id, since.isoformat())
        )
        row = await cursor.fetchone()
        return row["count"] if row else 0


async def count_applications_since_by_platform(user_id: str, platform: str, since: datetime) -> int:
    """Count applications since a given time for a specific platform."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT COUNT(*) as count FROM applications
               WHERE user_id = ? AND platform = ? AND created_at > ?
                 AND status NOT IN ('error', 'cancelled')""",
            (user_id, platform, since.isoformat()),
        )
        row = await cursor.fetchone()
        return row["count"] if row else 0


# Campaign + Queue operations

async def create_campaign(user_id: str, name: str, config: Dict[str, Any], status: str = "running") -> str:
    """Create a new campaign and return its id."""
    campaign_id = f"camp_{uuid.uuid4().hex}"
    async with get_db() as db:
        await db.execute(
            """INSERT INTO campaigns (id, user_id, name, status, config_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                campaign_id,
                user_id,
                name,
                status,
                json.dumps(config or {}),
                datetime.now().isoformat(),
            ),
        )
        await db.commit()
    return campaign_id


async def get_campaign(campaign_id: str) -> Optional[Dict[str, Any]]:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        camp = dict(row)
        camp["config"] = json.loads(camp.get("config_json") or "{}")
        return camp


async def list_campaigns(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM campaigns WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            camp = dict(row)
            camp["config"] = json.loads(camp.get("config_json") or "{}")
            out.append(camp)
        return out


async def set_campaign_status(campaign_id: str, status: str, last_error: Optional[str] = None):
    async with get_db() as db:
        await db.execute(
            "UPDATE campaigns SET status = ?, last_error = ?, updated_at = ? WHERE id = ?",
            (status, last_error, datetime.now().isoformat(), campaign_id),
        )
        await db.commit()


async def enqueue_jobs(
    user_id: str,
    campaign_id: str,
    jobs: List[Dict[str, Any]],
    *,
    priority: int = 0,
    max_attempts: int = 3,
) -> int:
    """Enqueue a list of job dicts (expects keys: job_url/platform/payload optional)."""
    now = datetime.now().isoformat()
    inserted = 0
    async with get_db() as db:
        for job in jobs:
            job_url = str(job.get("job_url") or job.get("url") or "").strip()
            if not job_url:
                continue

            # De-dupe: skip if a non-terminal queue item already exists for this URL.
            cursor = await db.execute(
                """SELECT id FROM job_queue
                   WHERE user_id = ? AND job_url = ? AND status IN ('queued','retry_scheduled','in_progress')
                   LIMIT 1""",
                (user_id, job_url),
            )
            if await cursor.fetchone():
                continue

            qid = f"q_{uuid.uuid4().hex}"
            platform = (job.get("platform") or "").strip() or None
            payload = job.get("payload") if isinstance(job.get("payload"), dict) else job

            await db.execute(
                """INSERT INTO job_queue
                   (id, campaign_id, user_id, job_url, platform, status, priority,
                    attempts, max_attempts, next_run_at, payload_json, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'queued', ?, 0, ?, ?, ?, ?)""",
                (
                    qid,
                    campaign_id,
                    user_id,
                    job_url,
                    platform,
                    int(priority),
                    int(max_attempts),
                    now,
                    json.dumps(payload or {}),
                    now,
                ),
            )
            inserted += 1
        await db.commit()
    return inserted


async def get_queue_counts(campaign_id: str) -> Dict[str, int]:
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT status, COUNT(*) as count
               FROM job_queue
               WHERE campaign_id = ?
               GROUP BY status""",
            (campaign_id,),
        )
        rows = await cursor.fetchall()
        out: Dict[str, int] = {}
        for row in rows:
            out[str(row["status"])] = int(row["count"])
        return out


async def list_queue_items(campaign_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM job_queue
               WHERE campaign_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (campaign_id, limit),
        )
        rows = await cursor.fetchall()
        items: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.get("payload_json") or "{}")
            items.append(item)
        return items


async def fetch_next_queue_item(worker_id: str) -> Optional[Dict[str, Any]]:
    """
    Atomically claim the next runnable queue item.
    Returns the claimed item dict, or None.
    """
    now = datetime.now().isoformat()
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")

        cursor = await db.execute(
            """
            SELECT q.*
            FROM job_queue q
            JOIN campaigns c ON c.id = q.campaign_id
            WHERE c.status = 'running'
              AND q.status IN ('queued', 'retry_scheduled')
              AND (q.next_run_at IS NULL OR q.next_run_at <= ?)
              AND q.locked_at IS NULL
            ORDER BY q.priority DESC, q.next_run_at ASC, q.created_at ASC
            LIMIT 1
            """,
            (now,),
        )
        row = await cursor.fetchone()
        if not row:
            await db.execute("COMMIT")
            return None

        qid = row["id"]
        await db.execute(
            "UPDATE job_queue SET status='in_progress', locked_at=?, locked_by=?, updated_at=? WHERE id=?",
            (now, worker_id, now, qid),
        )
        await db.commit()

        item = dict(row)
        item["payload"] = json.loads(item.get("payload_json") or "{}")
        return item


async def release_queue_lock(queue_id: str, worker_id: str):
    """Release lock without changing status (used on shutdown/error)."""
    now = datetime.now().isoformat()
    async with get_db() as db:
        await db.execute(
            """UPDATE job_queue
               SET locked_at = NULL, locked_by = NULL, updated_at = ?
               WHERE id = ? AND locked_by = ?""",
            (now, queue_id, worker_id),
        )
        await db.commit()


async def mark_queue_item_completed(
    queue_id: str,
    *,
    application_id: Optional[str] = None,
    status: str = "completed",
    last_error: Optional[str] = None,
):
    now = datetime.now().isoformat()
    async with get_db() as db:
        await db.execute(
            """UPDATE job_queue
               SET status = ?, application_id = ?, last_error = ?, locked_at = NULL, locked_by = NULL,
                   updated_at = ?
               WHERE id = ?""",
            (status, application_id, last_error, now, queue_id),
        )
        await db.commit()


async def schedule_queue_retry(
    queue_id: str,
    *,
    attempts: int,
    next_run_at: datetime,
    last_error: str,
):
    now = datetime.now().isoformat()
    async with get_db() as db:
        await db.execute(
            """UPDATE job_queue
               SET status = 'retry_scheduled',
                   attempts = ?,
                   next_run_at = ?,
                   last_error = ?,
                   locked_at = NULL,
                   locked_by = NULL,
                   updated_at = ?
               WHERE id = ?""",
            (int(attempts), next_run_at.isoformat(), last_error, now, queue_id),
        )
        await db.commit()


async def cancel_campaign_queue(campaign_id: str, reason: str = "cancelled"):
    """Cancel all non-terminal queue items for a campaign."""
    now = datetime.now().isoformat()
    async with get_db() as db:
        await db.execute(
            """UPDATE job_queue
               SET status = ?, last_error = ?, locked_at = NULL, locked_by = NULL, updated_at = ?
               WHERE campaign_id = ?
                 AND status IN ('queued','retry_scheduled','in_progress')""",
            ("cancelled", reason, now, campaign_id),
        )
        await db.commit()


# Notification state (simple key/value)

async def get_notification_state(key: str) -> Optional[Dict[str, Any]]:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM notification_state WHERE key = ?", (key,))
        row = await cursor.fetchone()
        if not row:
            return None
        out = dict(row)
        out["value"] = json.loads(out.get("value") or "null")
        return out


async def set_notification_state(key: str, value: Any):
    async with get_db() as db:
        await db.execute(
            """INSERT OR REPLACE INTO notification_state (key, value, updated_at)
               VALUES (?, ?, ?)""",
            (key, json.dumps(value), datetime.now().isoformat()),
        )
        await db.commit()


# Settings operations
async def save_settings(user_id: str, settings: Dict) -> bool:
    """Save user settings."""
    async with get_db() as db:
        # Merge with existing settings so omitted keys do not get wiped.
        cursor = await db.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        merged = dict(row) if row else {}
        merged.update(settings or {})

        await db.execute(
            """
            INSERT OR REPLACE INTO user_settings
            (user_id, daily_limit, linkedin_cookie_encrypted,
             platform_daily_limits_json, slack_webhook_url, discord_webhook_url, email_notifications_to,
             updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                merged.get("daily_limit", 10),
                merged.get("linkedin_cookie_encrypted"),
                merged.get("platform_daily_limits_json"),
                merged.get("slack_webhook_url"),
                merged.get("discord_webhook_url"),
                merged.get("email_notifications_to"),
                datetime.now().isoformat(),
            ),
        )
        await db.commit()
        return True


async def get_settings(user_id: str) -> Optional[Dict]:
    """Get user settings."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# Cache operations
async def set_cache(key: str, data: Any, ttl_seconds: int = 3600):
    """Set cache with TTL."""
    async with get_db() as db:
        expires_at = datetime.now().timestamp() + ttl_seconds
        await db.execute("""
            INSERT OR REPLACE INTO jobs_cache (cache_key, jobs_data, expires_at)
            VALUES (?, ?, ?)
        """, (key, json.dumps(data), datetime.fromtimestamp(expires_at).isoformat()))
        await db.commit()


async def get_cache(key: str) -> Optional[Any]:
    """Get cached data if not expired."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT jobs_data, expires_at FROM jobs_cache WHERE cache_key = ?",
            (key,)
        )
        row = await cursor.fetchone()
        if row:
            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at > datetime.now():
                return json.loads(row["jobs_data"])
        return None
