"""
LinkedIn Jobs scraper — uses Playwright (headless Chromium).
No official API access needed. Scrapes the public job search page.

LinkedIn aggressively rate-limits. Strategy:
  - Rotate user agents
  - Add human-like delays
  - Use a proxy if available (set PROXY_URL in .env)

Install: playwright install chromium
"""
from __future__ import annotations

import json
import re
import time
import random
from typing import Optional
from datetime import datetime

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

from scrapers.base import BaseScraper, JobPost
from config.settings import settings


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


class LinkedInScraper(BaseScraper):
    source_name = "LinkedIn"
    rate_limit_seconds = 3.0

    # LinkedIn job search URL pattern
    BASE_URL = "https://www.linkedin.com/jobs/search/"

    def scrape(self, search_terms: list[str], max_results: int) -> list[JobPost]:
        jobs: list[JobPost] = []
        seen_ids: set[str] = set()

        proxy_config = None
        if settings.proxy_url:
            proxy_config = {"server": settings.proxy_url}

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                proxy=proxy_config,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )

            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            page = context.new_page()

            # Search for the top terms (to stay within rate limits)
            priority_terms = [
                "data analyst",
                "business intelligence analyst",
                "data scientist",
                "analytics engineer",
            ]

            for term in priority_terms:
                if len(jobs) >= max_results:
                    break

                new_jobs = self._scrape_term(page, term, seen_ids, max_results - len(jobs))
                jobs.extend(new_jobs)
                self.sleep(random.uniform(3, 6))

            browser.close()

        return jobs

    def _scrape_term(
        self, page: Page, term: str, seen_ids: set, limit: int
    ) -> list[JobPost]:
        jobs = []
        url = (
            f"{self.BASE_URL}?keywords={term.replace(' ', '%20')}"
            f"&f_TPR=r2592000"  # last 30 days
            f"&sortBy=DD"       # most recent
        )

        self.logger.info(f"LinkedIn: searching '{term}'")

        try:
            page.goto(url, timeout=20_000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))

            # Scroll to load more results
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)

            # Get all job cards
            cards = page.query_selector_all(".job-search-card, .base-card")
            self.logger.info(f"LinkedIn: found {len(cards)} cards for '{term}'")

            for card in cards[:limit]:
                job = self._parse_card(card, term)
                if job and job.id not in seen_ids:
                    jobs.append(job)
                    seen_ids.add(job.id)

        except PWTimeout:
            self.logger.warning(f"LinkedIn timeout for '{term}'")
        except Exception as e:
            self.logger.warning(f"LinkedIn error for '{term}': {e}")

        return jobs

    def _parse_card(self, card, search_term: str) -> Optional[JobPost]:
        try:
            title = self._text(card, ".base-search-card__title, h3.base-card__full-link")
            company = self._text(card, ".base-search-card__subtitle, h4.base-search-card__subtitle a")
            location = self._text(card, ".job-search-card__location")
            posted_text = self._text(card, "time.job-search-card__listdate, time")
            posted_dt = card.query_selector("time")
            posted_iso = posted_dt.get_attribute("datetime") if posted_dt else datetime.utcnow().isoformat()

            # Extract job URL
            link_el = card.query_selector("a.base-card__full-link, a[href*='/jobs/view/']")
            url = link_el.get_attribute("href") if link_el else ""
            if url and not url.startswith("http"):
                url = "https://www.linkedin.com" + url

            if not title:
                return None

            remote = self.detect_remote(title + " " + location)
            experience = self.detect_experience(title)
            tools = self.extract_tools(title + " " + search_term)

            return JobPost(
                title=title,
                source="LinkedIn",
                company=company,
                location=location or ("Remote" if remote else ""),
                remote=remote,
                url=url,
                posted_at=posted_iso or datetime.utcnow().isoformat(),
                experience=experience,
                tools=tools,
                raw_data={"search_term": search_term, "posted_text": posted_text},
            )
        except Exception as e:
            self.logger.debug(f"LinkedIn card parse error: {e}")
            return None

    @staticmethod
    def _text(el, selector: str) -> str:
        node = el.query_selector(selector)
        return node.inner_text().strip() if node else ""
