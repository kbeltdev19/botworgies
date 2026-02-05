"""
Unified Configuration Module for Job Applier

All configuration settings are centralized here.
Import from this module: from api.config import config
"""

import os
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class AppConfig:
    """Unified application configuration."""

    # === Server Settings ===
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # === CORS Settings ===
    CORS_ORIGINS: List[str] = field(default_factory=lambda: [
        origin.strip() for origin in
        os.getenv("CORS_ORIGINS", "http://localhost:3000,https://job-applier.pages.dev").split(",")
        if origin.strip()
    ])
    CORS_ALLOW_CREDENTIALS: bool = True

    # === Rate Limiting ===
    DEFAULT_DAILY_LIMIT: int = int(os.getenv("DEFAULT_DAILY_LIMIT", "10"))
    MAX_DAILY_LIMIT: int = int(os.getenv("MAX_DAILY_LIMIT", "1000"))

    # === File Upload ===
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
    ALLOWED_EXTENSIONS: List[str] = field(default_factory=lambda: [".pdf", ".docx", ".txt"])

    # === API Keys ===
    MOONSHOT_API_KEY: Optional[str] = os.getenv("MOONSHOT_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    BROWSERBASE_API_KEY: Optional[str] = os.getenv("BROWSERBASE_API_KEY")
    BROWSERBASE_PROJECT_ID: Optional[str] = os.getenv("BROWSERBASE_PROJECT_ID")

    # Model configuration
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o")
    MODEL_API_KEY: Optional[str] = (
        os.getenv("MODEL_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("MOONSHOT_API_KEY")
    )

    # === Browser Automation (Stagehand) ===
    # Stagehand is enabled by default when the SDK and an API key are available
    STAGEHAND_ENABLED: bool = os.getenv("STAGEHAND_ENABLED", "true").lower() == "true"
    STAGEHAND_API_URL: str = os.getenv("STAGEHAND_API_URL", "https://api.stagehand.browserbase.com/v1")
    STAGEHAND_MODEL_NAME: str = os.getenv("STAGEHAND_MODEL_NAME", "gpt-4o")
    STAGEHAND_MODEL_API_KEY: Optional[str] = (
        os.getenv("STAGEHAND_MODEL_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    BROWSER_TIMEOUT_MS: int = int(os.getenv("BROWSER_TIMEOUT_MS", "60000"))
    MAX_SEARCH_PAGES: int = int(os.getenv("MAX_SEARCH_PAGES", "5"))
    MAX_APPLICATION_STEPS: int = int(os.getenv("MAX_APPLICATION_STEPS", "25"))

    # Browser environment: "BROWSERBASE" or "LOCAL"
    BROWSER_ENV: str = os.getenv("BROWSER_ENV", "BROWSERBASE")
    LOCAL_BROWSER_ENABLED: bool = os.getenv("LOCAL_BROWSER_ENABLED", "true").lower() == "true"
    MAX_LOCAL_BROWSERS: int = int(os.getenv("MAX_LOCAL_BROWSERS", "20"))
    PREFER_LOCAL_BROWSER: bool = os.getenv("PREFER_LOCAL_BROWSER", "false").lower() == "true"

    # === AI Service ===
    AI_MAX_RETRIES: int = int(os.getenv("AI_MAX_RETRIES", "3"))
    AI_RETRY_DELAY_SECONDS: float = float(os.getenv("AI_RETRY_DELAY_SECONDS", "1.0"))
    AI_TIMEOUT_SECONDS: int = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))

    # === Human-like Delays ===
    MIN_HUMAN_DELAY: float = float(os.getenv("MIN_HUMAN_DELAY", "1.0"))
    MAX_HUMAN_DELAY: float = float(os.getenv("MAX_HUMAN_DELAY", "3.0"))
    MIN_TYPING_DELAY_MS: int = int(os.getenv("MIN_TYPING_DELAY_MS", "50"))
    MAX_TYPING_DELAY_MS: int = int(os.getenv("MAX_TYPING_DELAY_MS", "150"))

    # === Security ===
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    PASSWORD_SALT: str = os.getenv("PASSWORD_SALT", "job-applier-default-salt")

    # === Paths ===
    DATA_DIR: str = os.getenv("DATA_DIR", "./data")
    LOG_DIR: str = os.getenv("LOG_DIR", "./logs")
    
    # === Campaign Settings ===
    CAMPAIGN_DEFAULT_MAX_APPLICATIONS: int = int(os.getenv("CAMPAIGN_DEFAULT_MAX_APPLICATIONS", "10"))
    CAMPAIGN_DAILY_LIMIT: int = int(os.getenv("CAMPAIGN_DAILY_LIMIT", "10"))
    
    @property
    def stagehand_config(self) -> dict:
        """Get Stagehand configuration dictionary."""
        cfg = {
            "env": self.BROWSER_ENV,
            "model_name": self.STAGEHAND_MODEL_NAME,
            "model_client_options": {"apiKey": self.STAGEHAND_MODEL_API_KEY},
        }
        # Only include BrowserBase credentials when using that environment
        if self.BROWSER_ENV == "BROWSERBASE":
            cfg["api_key"] = self.BROWSERBASE_API_KEY
            cfg["project_id"] = self.BROWSERBASE_PROJECT_ID
        return cfg
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of missing required settings."""
        missing = []

        # At least one AI model key is required
        if not self.OPENAI_API_KEY and not self.MOONSHOT_API_KEY:
            missing.append("OPENAI_API_KEY (or MOONSHOT_API_KEY)")

        # BrowserBase keys only required in BROWSERBASE mode
        if self.BROWSER_ENV == "BROWSERBASE":
            if not self.BROWSERBASE_API_KEY:
                missing.append("BROWSERBASE_API_KEY")
            if not self.BROWSERBASE_PROJECT_ID:
                missing.append("BROWSERBASE_PROJECT_ID")

        return missing


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
