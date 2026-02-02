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

        # Create indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_applications_created_at ON applications(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id)")

        await db.commit()


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
             years_experience, work_authorization, sponsorship_required, custom_answers, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            profile.get("first_name"),
            profile.get("last_name"),
            profile.get("email"),
            profile.get("phone"),
            profile.get("linkedin_url"),
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


# Settings operations
async def save_settings(user_id: str, settings: Dict) -> bool:
    """Save user settings."""
    async with get_db() as db:
        await db.execute("""
            INSERT OR REPLACE INTO user_settings
            (user_id, daily_limit, linkedin_cookie_encrypted, updated_at)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            settings.get("daily_limit", 10),
            settings.get("linkedin_cookie_encrypted"),
            datetime.now().isoformat()
        ))
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
