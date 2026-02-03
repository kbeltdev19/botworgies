"""
Configuration module for Job Applier API.
Centralizes all configurable constants and settings.
"""

import os
from typing import List
from dataclasses import dataclass, field


@dataclass
class AppConfig:
    """Application configuration."""

    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # CORS settings - MUST be configured for production
    CORS_ORIGINS: List[str] = field(default_factory=lambda: [
        origin.strip() for origin in
        os.getenv("CORS_ORIGINS", "http://localhost:3000,https://job-applier.pages.dev").split(",")
        if origin.strip()
    ])
    CORS_ALLOW_CREDENTIALS: bool = True

    # Rate limiting
    DEFAULT_DAILY_LIMIT: int = int(os.getenv("DEFAULT_DAILY_LIMIT", "10"))
    MAX_DAILY_LIMIT: int = int(os.getenv("MAX_DAILY_LIMIT", "1000"))

    # File upload
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
    ALLOWED_EXTENSIONS: List[str] = field(default_factory=lambda: [".pdf", ".docx", ".txt"])

    # Browser automation
    BROWSER_TIMEOUT_MS: int = int(os.getenv("BROWSER_TIMEOUT_MS", "60000"))
    MAX_SEARCH_PAGES: int = int(os.getenv("MAX_SEARCH_PAGES", "5"))
    MAX_APPLICATION_STEPS: int = int(os.getenv("MAX_APPLICATION_STEPS", "10"))
    
    # Local browser fallback settings
    LOCAL_BROWSER_ENABLED: bool = os.getenv("LOCAL_BROWSER_ENABLED", "true").lower() == "true"
    MAX_LOCAL_BROWSERS: int = int(os.getenv("MAX_LOCAL_BROWSERS", "20"))
    BROWSERBASE_COOLDOWN_MINUTES: int = int(os.getenv("BROWSERBASE_COOLDOWN_MINUTES", "5"))
    PREFER_LOCAL_BROWSER: bool = os.getenv("PREFER_LOCAL_BROWSER", "false").lower() == "true"

    # AI service
    AI_MAX_RETRIES: int = int(os.getenv("AI_MAX_RETRIES", "3"))
    AI_RETRY_DELAY_SECONDS: float = float(os.getenv("AI_RETRY_DELAY_SECONDS", "1.0"))
    AI_TIMEOUT_SECONDS: int = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))

    # Human-like delays (seconds)
    MIN_HUMAN_DELAY: float = float(os.getenv("MIN_HUMAN_DELAY", "1.0"))
    MAX_HUMAN_DELAY: float = float(os.getenv("MAX_HUMAN_DELAY", "3.0"))
    MIN_TYPING_DELAY_MS: int = int(os.getenv("MIN_TYPING_DELAY_MS", "50"))
    MAX_TYPING_DELAY_MS: int = int(os.getenv("MAX_TYPING_DELAY_MS", "150"))

    # Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    PASSWORD_SALT: str = os.getenv("PASSWORD_SALT", "job-applier-default-salt")

    # Paths
    DATA_DIR: str = os.getenv("DATA_DIR", "./data")
    LOG_DIR: str = os.getenv("LOG_DIR", "./logs")


# Global config instance
config = AppConfig()


def get_config() -> AppConfig:
    """Get the application configuration."""
    return config


# User agent list - updated for 2025/2026
USER_AGENTS = [
    # Chrome on Windows (most common)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",

    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",

    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",

    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",

    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",

    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


# LinkedIn GeoIDs for country filtering
LINKEDIN_GEO_IDS = {
    "US": "103644278",
    "CA": "101174742",
    "GB": "101165590",
    "DE": "101282230",
    "FR": "105015875",
    "AU": "101452733",
    "IN": "102713980",
    "NL": "102890719",
    "SG": "102454443",
}


# Indeed remote job filter ID
INDEED_REMOTE_FILTER = "032b3046-06a3-4876-8dfd-474eb5e7ed11"
