from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class JobOut(BaseModel):
    id: str
    title: str
    company: Optional[str] = ""
    location: Optional[str] = ""
    remote: bool = False
    source: str
    url: Optional[str] = ""
    posted_at: Optional[str] = None
    posted_human: Optional[str] = None   # computed "2 hours ago"
    deadline: Optional[str] = None
    experience: Optional[str] = ""
    salary: Optional[str] = ""
    description: Optional[str] = ""
    tools: list[str] = []
    urgent: bool = False
    scraped_at: Optional[str] = None

    @field_validator("tools", mode="before")
    @classmethod
    def parse_tools(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v or []

    @field_validator("remote", "urgent", mode="before")
    @classmethod
    def int_to_bool(cls, v):
        return bool(v)

    @classmethod
    def compute_posted_human(cls, posted_at: Optional[str]) -> str:
        if not posted_at:
            return "Recently posted"
        try:
            from dateutil import parser as dp
            dt = dp.parse(posted_at)
            if dt.tzinfo is None:
                from datetime import timezone
                dt = dt.replace(tzinfo=timezone.utc)
            from datetime import timezone
            now = datetime.now(timezone.utc)
            delta = now - dt
            hours = int(delta.total_seconds() / 3600)
            if hours < 1:
                return "Just now"
            if hours < 24:
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            days = hours // 24
            if days < 7:
                return f"{days} day{'s' if days != 1 else ''} ago"
            weeks = days // 7
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        except Exception:
            return "Recently posted"


class JobsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    jobs: list[JobOut]


class SourceStatus(BaseModel):
    source: str
    count: int
    latest_scraped: Optional[str]


class StatsResponse(BaseModel):
    total_jobs: int
    remote_jobs: int
    sources: int
    posted_today: int
    top_tools: list[dict]
    by_source: list[dict]
    by_experience: list[dict]
