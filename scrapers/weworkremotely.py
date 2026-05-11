"""
We Work Remotely scraper — uses their RSS feeds (no key needed).
https://weworkremotely.com — strong data/programming section.
"""
from __future__ import annotations

import re
import feedparser
from datetime import datetime

from scrapers.base import BaseScraper, JobPost


# WWR RSS feed URLs for relevant categories
WWR_FEEDS = [
    ("https://weworkremotely.com/categories/remote-programming-jobs.rss", "Programming"),
    ("https://weworkremotely.com/categories/remote-data-science-ai-statistics-jobs.rss", "Data Science"),
    ("https://weworkremotely.com/categories/remote-management-finance-jobs.rss", "Finance/Analytics"),
    ("https://weworkremotely.com/remote-jobs.rss", "All Remote"),
]

# Only keep posts matching these keywords
DATA_KEYWORDS = [
    "data", "analyst", "analytics", "sql", "python", "bi ",
    "tableau", "power bi", "looker", "scientist", "intelligence",
    "insight", "reporting", "dashboard", "quantitative",
]


class WeWorkRemotelyScraper(BaseScraper):
    source_name = "We Work Remotely"
    rate_limit_seconds = 2.0

    def scrape(self, search_terms: list[str], max_results: int) -> list[JobPost]:
        jobs: list[JobPost] = []
        seen_ids: set[str] = set()

        for feed_url, category in WWR_FEEDS:
            if len(jobs) >= max_results:
                break

            self.logger.info(f"WWR: fetching '{category}' feed")
            try:
                feed = feedparser.parse(feed_url)

                for entry in feed.entries:
                    if len(jobs) >= max_results:
                        break

                    job = self._parse_entry(entry, category)
                    if not job:
                        continue

                    # Filter for data-relevant roles
                    text = (job.title + " " + job.description).lower()
                    if not any(kw in text for kw in DATA_KEYWORDS):
                        continue

                    if job.id not in seen_ids:
                        jobs.append(job)
                        seen_ids.add(job.id)

                self.sleep()

            except Exception as e:
                self.logger.warning(f"WWR feed '{category}' failed: {e}")

        return jobs

    def _parse_entry(self, entry, category: str) -> JobPost | None:
        try:
            title_raw = entry.get("title", "")
            # WWR format: "Company: Job Title"
            if ":" in title_raw:
                company, title = title_raw.split(":", 1)
                company = company.strip()
                title = title.strip()
            else:
                title = title_raw
                company = ""

            url = entry.get("link", "")
            summary = entry.get("summary", "")
            clean_summary = self._strip_html(summary)

            # Published date
            published = entry.get("published", "")
            posted_iso = self.parse_date(published) if published else datetime.utcnow().isoformat()

            # Region from tags
            region_tags = [t.term for t in entry.get("tags", []) if hasattr(t, "term")]
            location = ", ".join(region_tags) if region_tags else "Remote"

            experience = self.detect_experience(title + " " + clean_summary)
            tools = self.extract_tools(title + " " + clean_summary)
            salary = self.extract_salary(clean_summary)

            return JobPost(
                title=title,
                source="We Work Remotely",
                company=company,
                location=location,
                remote=True,
                url=url,
                posted_at=posted_iso,
                salary=salary,
                experience=experience,
                description=clean_summary[:800],
                tools=tools,
                raw_data={"category": category, "region_tags": region_tags},
            )
        except Exception as e:
            self.logger.debug(f"WWR entry parse error: {e}")
            return None

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", " ", text).strip()
