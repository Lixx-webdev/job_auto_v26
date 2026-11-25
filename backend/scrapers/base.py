from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class RawJob:
    external_id: str
    platform: str
    title: str
    company: str
    location: str
    is_remote: bool
    seniority: str   # "junior" | "mid" | "senior" | "unknown"
    description: str
    apply_url: str
    posted_at: Optional[datetime]
    recruiter_email: Optional[str] = None


class BaseScraper(ABC):
    def __init__(self, filters: dict):
        """
        filters keys:
          - keywords: List[str]
          - locations: List[str]
          - seniority: List[str]
          - max_age_days: int
          - max_jobs: int
        """
        self.filters = filters

    @abstractmethod
    async def scrape(self) -> List[RawJob]:
        pass

    def infer_seniority(self, title: str) -> str:
        """Heuristic seniority detection from job title."""
        t = title.lower()
        junior_keywords = ["junior", "jr.", "jr ", "intern", "entry", "associate", "trainee", "graduate"]
        senior_keywords = ["senior", "sr.", "sr ", "lead", "principal", "staff", "head", "director",
                           "vp ", "vice president", "architect", "manager"]
        mid_keywords = ["mid", "ii", "2", "intermediate", "engineer ii", "developer ii"]

        for kw in junior_keywords:
            if kw in t:
                return "junior"
        for kw in senior_keywords:
            if kw in t:
                return "senior"
        for kw in mid_keywords:
            if kw in t:
                return "mid"
        return "unknown"

    def infer_remote(self, location: str, description: str) -> bool:
        """Detect remote work from location string and description text."""
        combined = (location + " " + description).lower()
        remote_keywords = ["remote", "work from home", "wfh", "fully remote", "work remotely",
                           "anywhere", "distributed", "telecommute", "telework"]
        return any(kw in combined for kw in remote_keywords)

    def is_location_match(self, location: str) -> bool:
        """Check if the job location matches any of the filter locations."""
        if not self.filters.get("locations"):
            return True
        loc_lower = location.lower()
        return any(fl.lower() in loc_lower for fl in self.filters["locations"])
