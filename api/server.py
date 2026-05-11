"""
FastAPI server — serves scraped job data to the frontend.

Start: uvicorn api.server:app --reload --port 8000
Docs:  http://localhost:8000/docs
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.models import JobOut, JobsResponse, SourceStatus, StatsResponse
from scrapers.base import get_engine, init_db
from config.settings import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="DataJobs API",
    description="Multi-source data analysis job aggregator",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = get_engine()
init_db(engine)


# ── Helpers ──────────────────────────────────────────────────────────────────

def rows_to_jobs(rows) -> list[JobOut]:
    jobs = []
    for row in rows:
        d = dict(row._mapping)
        job = JobOut(**d)
        job.posted_human = JobOut.compute_posted_human(job.posted_at)
        jobs.append(job)
    return jobs


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/jobs", response_model=JobsResponse, tags=["Jobs"])
def list_jobs(
    q: Optional[str] = Query(None, description="Search in title/company/description"),
    source: Optional[str] = Query(None, description="Filter by source (e.g. Reddit, LinkedIn)"),
    level: Optional[str] = Query(None, description="Experience level: entry | mid | senior"),
    remote: Optional[bool] = Query(None, description="Remote only"),
    location: Optional[str] = Query(None, description="Location keyword"),
    tool: Optional[str] = Query(None, description="Required tool (e.g. Python, Tableau)"),
    days: int = Query(30, description="Max age of jobs in days"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conditions = ["1=1"]
    params: dict = {}

    # Age filter
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conditions.append("(scraped_at >= :cutoff OR posted_at >= :cutoff)")
    params["cutoff"] = cutoff

    if q:
        conditions.append(
            "(LOWER(title) LIKE :q OR LOWER(company) LIKE :q OR LOWER(description) LIKE :q)"
        )
        params["q"] = f"%{q.lower()}%"

    if source:
        conditions.append("LOWER(source) = :source")
        params["source"] = source.lower()

    if level:
        conditions.append("LOWER(experience) LIKE :level")
        params["level"] = f"%{level.lower()}%"

    if remote is not None:
        conditions.append("remote = :remote")
        params["remote"] = int(remote)

    if location:
        conditions.append("LOWER(location) LIKE :location")
        params["location"] = f"%{location.lower()}%"

    if tool:
        conditions.append("LOWER(tools) LIKE :tool")
        params["tool"] = f"%{tool.lower()}%"

    where = " AND ".join(conditions)
    offset = (page - 1) * page_size

    with engine.connect() as conn:
        total_row = conn.execute(
            text(f"SELECT COUNT(*) FROM jobs WHERE {where}"), params
        ).fetchone()
        total = total_row[0] if total_row else 0

        rows = conn.execute(
            text(
                f"SELECT * FROM jobs WHERE {where} "
                f"ORDER BY scraped_at DESC LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page_size, "offset": offset},
        ).fetchall()

    return JobsResponse(total=total, page=page, page_size=page_size, jobs=rows_to_jobs(rows))


@app.get("/jobs/{job_id}", response_model=JobOut, tags=["Jobs"])
def get_job(job_id: str):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job = JobOut(**dict(row._mapping))
    job.posted_human = JobOut.compute_posted_human(job.posted_at)
    return job


@app.get("/sources", response_model=list[SourceStatus], tags=["Meta"])
def list_sources():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT source, COUNT(*) as count, MAX(scraped_at) as latest_scraped
            FROM jobs
            GROUP BY source
            ORDER BY count DESC
        """)).fetchall()
    return [SourceStatus(**dict(r._mapping)) for r in rows]


@app.get("/stats", response_model=StatsResponse, tags=["Meta"])
def get_stats():
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar() or 0
        remote = conn.execute(text("SELECT COUNT(*) FROM jobs WHERE remote=1")).scalar() or 0
        sources = conn.execute(text("SELECT COUNT(DISTINCT source) FROM jobs")).scalar() or 0

        today_cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        posted_today = conn.execute(
            text("SELECT COUNT(*) FROM jobs WHERE scraped_at >= :cutoff"),
            {"cutoff": today_cutoff},
        ).scalar() or 0

        by_source = conn.execute(text("""
            SELECT source, COUNT(*) as count FROM jobs GROUP BY source ORDER BY count DESC
        """)).fetchall()

        by_exp = conn.execute(text("""
            SELECT experience, COUNT(*) as count FROM jobs
            WHERE experience != '' GROUP BY experience ORDER BY count DESC
        """)).fetchall()

        # Top tools — parse JSON arrays from tools column
        tool_rows = conn.execute(text("SELECT tools FROM jobs WHERE tools != '[]' AND tools != ''")).fetchall()

    # Count tools
    tool_counter: Counter = Counter()
    for row in tool_rows:
        try:
            tool_list = json.loads(row[0]) if row[0] else []
            tool_counter.update(tool_list)
        except Exception:
            pass

    top_tools = [{"tool": t, "count": c} for t, c in tool_counter.most_common(15)]

    return StatsResponse(
        total_jobs=total,
        remote_jobs=remote,
        sources=sources,
        posted_today=posted_today,
        top_tools=top_tools,
        by_source=[dict(r._mapping) for r in by_source],
        by_experience=[dict(r._mapping) for r in by_exp],
    )


@app.post("/scrape", tags=["Meta"])
def trigger_scrape(background_tasks: BackgroundTasks):
    """Trigger an immediate scrape of all sources (runs in background)."""
    def _run():
        from scheduler import run_all_scrapers
        run_all_scrapers()

    background_tasks.add_task(_run)
    return {"status": "Scrape started in background"}


@app.get("/", tags=["Meta"])
def root():
    return {
        "name": "DataJobs API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": ["/jobs", "/jobs/{id}", "/sources", "/stats", "/scrape"],
    }
