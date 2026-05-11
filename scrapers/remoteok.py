"""
RemoteOK scraper — uses their public JSON API (no key required).
https://remoteok.com/api — returns all jobs tagged with relevant categories.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from scrapers.base import BaseScraper, JobPost
from config.settings import settings

# RemoteOK tag categories relevant to data analysis
REMOTEOK_TAGS = [
    "data",
    "analyst",
    "data-science",
    "machine-learning",
    "python",
    "sql",
    "bi",
    "analytics",
]


class RemoteOKScraper(BaseScraper):
    source_name = "RemoteOK"
    rate_limit_seconds = 2.0
    API_URL = "https://remoteok.com/api?tag={tag}"

    HEADERS = {
        "User-Agent": "DataJobsScraper/1.0 (+https://github.com/yourusername/datajobs)",
        "Accept": "application/json",
    }

    def scrape(self, search_terms: list[str], max_results: int) -> list[JobPost]:
        jobs: list[JobPost] = []
        seen_ids: set[str] = set()

        for tag in REMOTEOK_TAGS:
            if len(jobs) >= max_results:
                break

            self.logger.info(f"RemoteOK: fetching tag '{tag}'")
            try:
                with httpx.Client(timeout=15) as client:
                    resp = client.get(
                        self.API_URL.format(tag=tag),
                        headers=self.HEADERS,
                        follow_redirects=True,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                # First item is metadata, skip it
                listings = [item for item in data if isinstance(item, dict) and "id" in item]

                for item in listings:
                    if len(jobs) >= max_results:
                        break
                    job = self._parse(item)
                    if job and job.id not in seen_ids:
                        jobs.append(job)
                        seen_ids.add(job.id)

                self.sleep()

            except Exception as e:
                self.logger.warning(f"RemoteOK tag '{tag}' failed: {e}")
                continue

        return jobs

    def _parse(self, item: dict) -> JobPost | None:
        title = item.get("position", "")
        company = item.get("company", "")
        description = item.get("description", "")
        tags = item.get("tags", [])
        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        url = item.get("url", f"https://remoteok.com/l/{item.get('slug', '')}")
        date_str = item.get("date", "")
        epoch = item.get("epoch")

        if not title:
            return None

        # Salary formatting
        salary = ""
        if salary_min and salary_max:
            salary = f"${salary_min:,}–${salary_max:,}/yr"
        elif salary_min:
            salary = f"${salary_min:,}+/yr"

        # Convert epoch to ISO
        if epoch:
            posted_iso = datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()
        else:
            posted_iso = self.parse_date(date_str)

        experience = self.detect_experience(title + " " + description + " " + " ".join(tags))
        tools = self.extract_tools(title + " " + description + " " + " ".join(tags))

        return JobPost(
            title=title,
            source="RemoteOK",
            company=company,
            location="Remote",
            remote=True,
            url=url,
            posted_at=posted_iso,
            salary=salary,
            experience=experience,
            description=self._strip_html(description)[:800],
            tools=tools,
            raw_data={
                "remoteok_id": item.get("id"),
                "tags": tags,
                "applicants": item.get("applicants"),
            },
        )

    @staticmethod
    def _strip_html(text: str) -> str:
        import re
        return re.sub(r"<[^>]+>", " ", text).strip()
