from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Required secrets ---
    GEMINI_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str

    # --- Optional integrations ---
    LINKEDIN_EMAIL: str = ""
    LINKEDIN_PASSWORD: str = ""
    GMAIL_ADDRESS: str = ""
    GMAIL_APP_PASSWORD: str = ""

    # --- Tuning knobs ---
    AI_MATCH_THRESHOLD: int = 70
    SCRAPE_INTERVAL_HOURS: int = 4
    MAX_JOBS_PER_RUN: int = 30

    TARGET_LOCATIONS: str = "India,Remote,Bengaluru,Hyderabad,Mumbai,Pune,Chennai,Delhi"
    TARGET_SENIORITY: str = "mid,senior"
    TARGET_KEYWORDS: str = "security engineer,data scientist,software engineer,ML engineer,fintech"
    MAX_JOB_AGE_DAYS: int = 7

    # --- Infrastructure ---
    DB_URL: str = "sqlite:///./job_automation.db"
    LOG_LEVEL: str = "INFO"

    # -----------------------------------------------------------------
    # Computed helpers
    # -----------------------------------------------------------------

    @property
    def target_locations_list(self) -> List[str]:
        return [loc.strip() for loc in self.TARGET_LOCATIONS.split(",") if loc.strip()]

    @property
    def target_keywords_list(self) -> List[str]:
        return [k.strip() for k in self.TARGET_KEYWORDS.split(",") if k.strip()]

    @property
    def target_seniority_list(self) -> List[str]:
        return [s.strip() for s in self.TARGET_SENIORITY.split(",") if s.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
