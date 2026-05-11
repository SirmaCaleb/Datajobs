"""
Base scraper — all source scrapers inherit from this.
Provides: deduplication, retry logic, rate limiting, logging, DB upsert.
"""
from __future__ import annotations

import hashlib
import logging
import time
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import dateparser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from config.settings import settings

logger = logging.getLogger(__name__)


# ─── Database setup ──────────────────────────────────────────────────────────

def get_engine():
    import os
    os.makedirs("data", exist_ok=True)
    return create_engine(f"sqlite:///{settings.db_path}", echo=False)


def init_db(engine):
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                company     TEXT,
                location    TEXT,
                remote      INTEGER DEFAULT 0,
                source      TEXT NOT NULL,
                url         TEXT,
                posted_at   TEXT,
                deadline    TEXT,
                experience  TEXT,
                salary      TEXT,
                description TEXT,
                tools       TEXT,          -- JSON array as string
                urgent      INTEGER DEFAULT 0,
                scraped_at  TEXT NOT NULL,
                raw_data    TEXT           -- full JSON blob
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_jobs_scraped ON jobs(scraped_at DESC);
        """))
        conn.commit()


# ─── Base class ──────────────────────────────────────────────────────────────

class JobPost:
    """Normalised job post — every scraper returns a list of these."""

    def __init__(
        self,
        title: str,
        source: str,
        *,
        company: str = "",
        location: str = "",
        remote: bool = False,
        url: str = "",
        posted_at: Optional[str] = None,
        deadline: Optional[str] = None,
        experience: str = "",
        salary: str = "",
        description: str = "",
        tools: Optional[list[str]] = None,
        urgent: bool = False,
        raw_data: Optional[dict] = None,
    ):
        self.title = title.strip()
        self.source = source
        self.company = company.strip()
        self.location = location.strip()
        self.remote = remote
        self.url = url.strip()
        self.posted_at = posted_at or datetime.utcnow().isoformat()
        self.deadline = deadline
        self.experience = experience
        self.salary = salary
        self.description = description[:1000] if description else ""
        self.tools = tools or []
        self.urgent = urgent
        self.raw_data = raw_data or {}
        self.scraped_at = datetime.utcnow().isoformat()

        # Stable dedup key: source + url hash (or title+company hash)
        key_src = url if url else f"{title}|{company}|{source}"
        self.id = hashlib.sha1(key_src.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "remote": int(self.remote),
            "source": self.source,
            "url": self.url,
            "posted_at": self.posted_at,
            "deadline": self.deadline,
            "experience": self.experience,
            "salary": self.salary,
            "description": self.description,
            "tools": json.dumps(self.tools),
            "urgent": int(self.urgent),
            "scraped_at": self.scraped_at,
            "raw_data": json.dumps(self.raw_data),
        }


class BaseScraper(ABC):
    """All scrapers inherit this. Implement `scrape()` only."""

    source_name: str = "Unknown"
    rate_limit_seconds: float = 1.5  # polite crawl delay

    def __init__(self):
        self.engine = get_engine()
        init_db(self.engine)
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def scrape(self, search_terms: list[str], max_results: int) -> list[JobPost]:
        """Fetch and return normalised JobPost objects."""
        ...

    def run(
        self,
        search_terms: Optional[list[str]] = None,
        max_results: Optional[int] = None,
    ) -> int:
        """Run scraper and save results. Returns number of new jobs inserted."""
        from config.settings import SEARCH_TERMS

        terms = search_terms or SEARCH_TERMS
        limit = max_results or settings.max_jobs_per_source

        self.logger.info(f"[{self.source_name}] Starting scrape (terms={len(terms)}, max={limit})")
        try:
            jobs = self.scrape(terms, limit)
        except Exception as e:
            self.logger.error(f"[{self.source_name}] Scrape failed: {e}", exc_info=True)
            return 0

        new_count = self._upsert(jobs)
        self.logger.info(f"[{self.source_name}] Done — {new_count} new jobs saved (total scraped: {len(jobs)})")
        return new_count

    def _upsert(self, jobs: list[JobPost]) -> int:
        """Insert new jobs, skip existing (by ID)."""
        import json
        new_count = 0
        with Session(self.engine) as session:
            for job in jobs:
                exists = session.execute(
                    text("SELECT 1 FROM jobs WHERE id = :id"), {"id": job.id}
                ).fetchone()
                if not exists:
                    session.execute(
                        text("""
                            INSERT INTO jobs
                              (id, title, company, location, remote, source, url,
                               posted_at, deadline, experience, salary, description,
                               tools, urgent, scraped_at, raw_data)
                            VALUES
                              (:id, :title, :company, :location, :remote, :source, :url,
                               :posted_at, :deadline, :experience, :salary, :description,
                               :tools, :urgent, :scraped_at, :raw_data)
                        """),
                        job.to_dict(),
                    )
                    new_count += 1
            session.commit()
        return new_count

    # ── Shared helpers ────────────────────────────────────────────────────────

    @staticmethod
    def extract_tools(text: str) -> list[str]:
        """Extract known data tools/skills mentioned in text."""
        known = [
            "Python", "R", "SQL", "Excel", "Tableau", "Power BI", "PowerBI",
            "Looker", "dbt", "Spark", "PySpark", "Hadoop", "Airflow", "Kafka",
            "pandas", "NumPy", "scikit-learn", "TensorFlow", "PyTorch",
            "BigQuery", "Redshift", "Snowflake", "Databricks", "AWS", "Azure",
            "GCP", "Google Cloud", "S3", "Athena", "SageMaker",
            "Matplotlib", "Seaborn", "Plotly", "D3.js",
            "SPSS", "SAS", "STATA", "MATLAB",
            "MongoDB", "PostgreSQL", "MySQL", "SQLite", "Cassandra",
            "Elasticsearch", "Superset", "Metabase", "QlikView",
            "GitHub", "Git", "Docker", "Kubernetes", "Terraform",
            "Jupyter", "VS Code", "MLflow", "Prefect", "Luigi",
        ]
        found = []
        text_lower = text.lower()
        for tool in known:
            if tool.lower() in text_lower and tool not in found:
                found.append(tool)
        return found[:10]

    @staticmethod
    def detect_experience(text: str) -> str:
        """Guess experience level from job text."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["senior", "sr.", "lead", "principal", "staff", "head of"]):
            return "Senior (5+ yrs)"
        if any(w in text_lower for w in ["mid-level", "mid level", "3+ years", "4+ years", "3-5"]):
            return "Mid level (2-4 yrs)"
        if any(w in text_lower for w in ["junior", "entry", "graduate", "intern", "fresh", "0-2", "1-2 year"]):
            return "Entry level"
        if any(w in text_lower for w in ["manager", "director", "vp ", "vice president"]):
            return "Senior (5+ yrs)"
        return "Mid level (2-4 yrs)"  # default

    @staticmethod
    def detect_remote(text: str, location: str = "") -> bool:
        combined = (text + " " + location).lower()
        return any(w in combined for w in ["remote", "work from home", "wfh", "distributed", "anywhere"])

    @staticmethod
    def extract_salary(text: str) -> str:
        patterns = [
            r"\$[\d,]+[kK]?\s*[-–]\s*\$[\d,]+[kK]?",
            r"£[\d,]+[kK]?\s*[-–]\s*£[\d,]+[kK]?",
            r"€[\d,]+[kK]?\s*[-–]\s*€[\d,]+[kK]?",
            r"KES\s*[\d,]+[kK]?\s*[-–]\s*KES\s*[\d,]+[kK]?",
            r"[\d,]+[kK]\s*[-–]\s*[\d,]+[kK]\s*(?:USD|GBP|EUR|KES)",
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(0).strip()
        return ""

    @staticmethod
    def parse_date(date_str: str) -> str:
        """Parse any date string into ISO format."""
        if not date_str:
            return datetime.utcnow().isoformat()
        try:
            parsed = dateparser.parse(date_str)
            return parsed.isoformat() if parsed else datetime.utcnow().isoformat()
        except Exception:
            return datetime.utcnow().isoformat()

    def sleep(self, seconds: Optional[float] = None):
        time.sleep(seconds or self.rate_limit_seconds)
