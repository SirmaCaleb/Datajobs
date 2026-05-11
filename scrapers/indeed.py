"""
Indeed scraper — Playwright-based.
Scrapes indeed.com job search results for data analysis roles.

Indeed uses Cloudflare; headless=False may be needed if blocked.
Set PROXY_URL in .env for production reliability.
"""
from __future__ import annotations

import random
import time
import re
from typing import Optional
from datetime import datetime

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

from scrapers.base import BaseScraper, JobPost
from config.settings import settings


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
]

# (search term, country subdomain, location param)
INDEED_TARGETS = [
    ("data analyst", "www", ""),
    ("data scientist", "www", ""),
    ("business intelligence analyst", "www", ""),
    ("data analyst", "ke", "Nairobi"),           # Kenya / Africa jobs
    ("analytics engineer", "www", "remote"),
]


class IndeedScraper(BaseScraper):
    source_name = "Indeed"
    rate_limit_seconds = 4.0

    def scrape(self, search_terms: list[str], max_results: int) -> list[JobPost]:
        jobs: list[JobPost] = []
        seen_ids: set[str] = set()

        proxy_config = {"server": settings.proxy_url} if settings.proxy_url else None

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                proxy=proxy_config,
                args=["--no-sandbox"],
            )
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1366, "height": 768},
            )
            page = context.new_page()

            for term, country, location in INDEED_TARGETS:
                if len(jobs) >= max_results:
                    break
                new = self._scrape_target(page, term, country, location, seen_ids, max_results - len(jobs))
                jobs.extend(new)
                self.sleep(random.uniform(4, 7))

            browser.close()

        return jobs

    def _scrape_target(
        self, page: Page, term: str, country: str, location: str,
        seen_ids: set, limit: int
    ) -> list[JobPost]:
        loc_param = f"&l={location.replace(' ', '+')}" if location else ""
        url = f"https://{country}.indeed.com/jobs?q={term.replace(' ', '+')}{loc_param}&sort=date&fromage=30"

        self.logger.info(f"Indeed [{country}]: '{term}' / '{location}'")

        jobs = []
        try:
            page.goto(url, timeout=25_000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))

            # Scroll
            for _ in range(2):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                time.sleep(1)

            # Indeed card selectors (they change frequently)
            cards = page.query_selector_all(
                ".job_seen_beacon, .jobsearch-ResultsList > li[data-jk], .tapItem"
            )
            self.logger.info(f"Indeed: found {len(cards)} cards")

            for card in cards[:limit]:
                job = self._parse_card(card, term, country)
                if job and job.id not in seen_ids:
                    jobs.append(job)
                    seen_ids.add(job.id)

        except PWTimeout:
            self.logger.warning(f"Indeed timeout: {term}")
        except Exception as e:
            self.logger.warning(f"Indeed error: {e}")

        return jobs

    def _parse_card(self, card, search_term: str, country: str) -> Optional[JobPost]:
        try:
            title = self._text(card, "h2.jobTitle span, .jobTitle a span")
            company = self._text(card, "[data-testid='company-name'], .companyName")
            location = self._text(card, "[data-testid='text-location'], .companyLocation")
            salary = self._text(card, ".salary-snippet-container, [data-testid='attribute_snippet_testid']")
            posted_text = self._text(card, ".date, [data-testid='myJobsStateDate']")
            snippet = self._text(card, ".job-snippet, [data-testid='jobsnippet_footer']")

            # Extract job URL
            link = card.query_selector("h2.jobTitle a, a.jcs-JobTitle")
            jk = card.get_attribute("data-jk") or ""
            if link:
                href = link.get_attribute("href") or ""
                base = "https://ke.indeed.com" if country == "ke" else "https://www.indeed.com"
                url = href if href.startswith("http") else base + href
            elif jk:
                url = f"https://www.indeed.com/viewjob?jk={jk}"
            else:
                url = ""

            if not title:
                return None

            remote = self.detect_remote(title + " " + location + " " + snippet)
            experience = self.detect_experience(title + " " + snippet)
            tools = self.extract_tools(title + " " + snippet + " " + search_term)
            salary_clean = salary or self.extract_salary(snippet)

            return JobPost(
                title=title,
                source="Indeed",
                company=company,
                location=location,
                remote=remote,
                url=url,
                posted_at=self.parse_date(posted_text) if posted_text else datetime.utcnow().isoformat(),
                salary=salary_clean,
                experience=experience,
                description=snippet,
                tools=tools,
                raw_data={
                    "search_term": search_term,
                    "country": country,
                    "posted_text": posted_text,
                },
            )
        except Exception as e:
            self.logger.debug(f"Indeed card error: {e}")
            return None

    @staticmethod
    def _text(el, selector: str) -> str:
        node = el.query_selector(selector)
        return node.inner_text().strip() if node else ""
