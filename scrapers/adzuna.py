"""
Adzuna scraper — uses the official Adzuna Jobs API.
Free tier: 250 req/day. Great coverage in Kenya/Africa/UK/US.
Register at https://developer.adzuna.com

Covers: indeed-aggregated + local job boards in each country.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from scrapers.base import BaseScraper, JobPost
from config.settings import settings


# (country_code, country_label)
# Adzuna supports: gb, us, au, ca, de, fr, in, nz, sg, za, ke (Kenya!)
ADZUNA_COUNTRIES = [
    ("ke", "Kenya"),
    ("za", "South Africa"),
    ("gb", "UK"),
    ("us", "USA"),
]

DATA_SEARCH_TERMS = [
    "data analyst",
    "business intelligence analyst",
    "data scientist",
    "analytics engineer",
    "SQL analyst",
]


class AdzunaScraper(BaseScraper):
    source_name = "Adzuna"
    rate_limit_seconds = 1.5
    BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"

    def scrape(self, search_terms: list[str], max_results: int) -> list[JobPost]:
        if not settings.adzuna_app_id or not settings.adzuna_app_key:
            self.logger.warning("Adzuna: ADZUNA_APP_ID or ADZUNA_APP_KEY not set — skipping")
            return []

        jobs: list[JobPost] = []
        seen_ids: set[str] = set()

        with httpx.Client(timeout=15) as client:
            for country_code, country_label in ADZUNA_COUNTRIES:
                for term in DATA_SEARCH_TERMS[:3]:  # limit per country to save quota
                    if len(jobs) >= max_results:
                        break

                    new = self._fetch(client, country_code, country_label, term, seen_ids)
                    jobs.extend(new)
                    self.sleep()

                if len(jobs) >= max_results:
                    break

        return jobs

    def _fetch(
        self, client: httpx.Client, country: str, country_label: str,
        term: str, seen_ids: set
    ) -> list[JobPost]:
        self.logger.info(f"Adzuna [{country_label}]: '{term}'")
        try:
            resp = client.get(
                self.BASE_URL.format(country=country),
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": term,
                    "results_per_page": 20,
                    "sort_by": "date",
                    "max_days_old": 30,
                    "content-type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.logger.warning(f"Adzuna [{country_label}] '{term}' failed: {e}")
            return []

        jobs = []
        for item in data.get("results", []):
            job = self._parse(item, country_label, term)
            if job and job.id not in seen_ids:
                jobs.append(job)
                seen_ids.add(job.id)

        return jobs

    def _parse(self, item: dict, country_label: str, search_term: str) -> Optional[JobPost]:
        try:
            title = item.get("title", "")
            company = item.get("company", {}).get("display_name", "")
            location_data = item.get("location", {})
            location = location_data.get("display_name", country_label)
            description = item.get("description", "")
            url = item.get("redirect_url", "")
            created = item.get("created", "")
            salary_min = item.get("salary_min")
            salary_max = item.get("salary_max")

            if not title:
                return None

            # Salary
            salary = ""
            currency_map = {"ke": "KES", "za": "ZAR", "gb": "£", "us": "$"}
            currency = currency_map.get(country_label[:2].lower(), "$")
            if salary_min and salary_max:
                salary = f"{currency}{int(salary_min):,}–{currency}{int(salary_max):,}/yr"
            elif salary_min:
                salary = f"{currency}{int(salary_min):,}+/yr"

            remote = self.detect_remote(title + " " + description + " " + location)
            experience = self.detect_experience(title + " " + description)
            tools = self.extract_tools(title + " " + description)
            posted_iso = self.parse_date(created) if created else datetime.utcnow().isoformat()

            return JobPost(
                title=title,
                source="Adzuna",
                company=company,
                location=location,
                remote=remote,
                url=url,
                posted_at=posted_iso,
                salary=salary,
                experience=experience,
                description=description[:800],
                tools=tools,
                raw_data={
                    "adzuna_id": item.get("id"),
                    "country": country_label,
                    "search_term": search_term,
                    "category": item.get("category", {}).get("label"),
                },
            )
        except Exception as e:
            self.logger.debug(f"Adzuna parse error: {e}")
            return None
