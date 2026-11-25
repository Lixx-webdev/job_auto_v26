from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String, unique=True, index=True, nullable=False)
    platform = Column(String, nullable=False)          # e.g. "linkedin", "naukri"
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=True)
    is_remote = Column(Boolean, default=False)
    seniority = Column(String, nullable=True)          # e.g. "mid", "senior"
    description = Column(Text, nullable=True)
    apply_url = Column(String, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # AI evaluation
    ai_score = Column(Float, nullable=True)
    ai_reasons = Column(Text, nullable=True)           # JSON string

    # Workflow state
    status = Column(String, default="pending")         # pending | reviewed | applied | rejected
    cover_letter = Column(Text, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    recruiter_email = Column(String, nullable=True)

    # Relationships
    logs = relationship("ApplicationLog", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Job id={self.id} title={self.title!r} company={self.company!r}>"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    portfolio_url = Column(String, nullable=True)
    resume_path = Column(String, nullable=True)        # local filesystem path

    # Stored as JSON strings
    skills = Column(Text, nullable=True)               # JSON array of strings
    experience = Column(Text, nullable=True)           # JSON array of objects
    education = Column(Text, nullable=True)            # JSON array of objects

    raw_text = Column(Text, nullable=True)             # raw resume text
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<UserProfile id={self.id} name={self.name!r}>"


class ApplicationLog(Base):
    __tablename__ = "application_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    event_type = Column(String, nullable=False)        # e.g. "scraped", "ai_scored", "applied"
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    job = relationship("Job", back_populates="logs")

    def __repr__(self) -> str:
        return f"<ApplicationLog id={self.id} job_id={self.job_id} event={self.event_type!r}>"
