"""
Reddit scraper — uses PRAW (official Reddit API).
Searches r/datascience, r/analytics, r/forhire, r/jobs and more.

No proxy needed. Free API: 60 req/min.
Get credentials at https://www.reddit.com/prefs/apps (choose "script").
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

import praw
from praw.models import Submission

from scrapers.base import BaseScraper, JobPost
from config.settings import settings, REDDIT_SUBREDDITS


class RedditScraper(BaseScraper):
    source_name = "Reddit"
    rate_limit_seconds = 0.5  # PRAW handles rate limits internally

    # Posts must contain at least one of these to be considered job posts
    JOB_SIGNALS = [
        "[hiring]", "[h]", "hiring", "job opening", "we are hiring",
        "looking for", "job opportunity", "open position", "apply now",
        "full-time", "part-time", "contract", "remote position",
        "data analyst", "data scientist", "data engineer",
    ]

    def __init__(self):
        super().__init__()
        self.reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            read_only=True,
        )

    def scrape(self, search_terms: list[str], max_results: int) -> list[JobPost]:
        jobs: list[JobPost] = []
        seen_ids: set[str] = set()

        for subreddit_name in REDDIT_SUBREDDITS:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)

                # Combine search terms into one query for efficiency
                # Reddit search supports OR operator
                query = " OR ".join(f'"{t}"' for t in search_terms[:5])

                self.logger.info(f"Searching r/{subreddit_name} ...")
                results = subreddit.search(
                    query,
                    sort="new",
                    time_filter="month",
                    limit=30,
                )

                for post in results:
                    if post.id in seen_ids:
                        continue
                    if not self._is_job_post(post):
                        continue

                    job = self._parse_post(post)
                    if job:
                        jobs.append(job)
                        seen_ids.add(post.id)

                    if len(jobs) >= max_results:
                        break

                self.sleep(1.0)

            except Exception as e:
                self.logger.warning(f"r/{subreddit_name} failed: {e}")
                continue

            if len(jobs) >= max_results:
                break

        return jobs

    def _is_job_post(self, post: Submission) -> bool:
        """Heuristic: is this actually a job posting?"""
        text = (post.title + " " + (post.selftext or "")).lower()
        return any(signal in text for signal in self.JOB_SIGNALS)

    def _parse_post(self, post: Submission) -> Optional[JobPost]:
        body = post.selftext or ""
        title = post.title

        # Clean up [HIRING] tags from title
        clean_title = re.sub(r"\[.*?\]", "", title).strip()
        if not clean_title:
            clean_title = title

        # Extract company from flair or text patterns
        company = post.author_flair_text or ""
        if not company:
            m = re.search(
                r"(?:at|@|company|employer)[:\s]+([A-Z][A-Za-z\s&]+?)(?:\s*[|,\n]|$)",
                body[:500],
            )
            if m:
                company = m.group(1).strip()

        # Location
        location = ""
        loc_m = re.search(
            r"(?:location|based in|office in|city)[:\s]+([A-Za-z,\s]+?)(?:\n|$)",
            body[:600],
            re.IGNORECASE,
        )
        if loc_m:
            location = loc_m.group(1).strip()

        remote = self.detect_remote(body + title, location)
        salary = self.extract_salary(body)
        tools = self.extract_tools(body + " " + title)
        experience = self.detect_experience(body + " " + title)

        # Posted datetime from unix timestamp
        posted_dt = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
        posted_iso = posted_dt.isoformat()

        # Human-readable "X ago"
        delta = datetime.now(tz=timezone.utc) - posted_dt
        hours = int(delta.total_seconds() / 3600)
        if hours < 1:
            posted_human = "Just now"
        elif hours < 24:
            posted_human = f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = hours // 24
            posted_human = f"{days} day{'s' if days != 1 else ''} ago"

        # Extract deadline
        deadline = None
        dl_m = re.search(
            r"(?:deadline|apply by|closing date)[:\s]+([A-Za-z0-9,\s]+?)(?:\n|$)",
            body,
            re.IGNORECASE,
        )
        if dl_m:
            deadline = dl_m.group(1).strip()

        url = f"https://reddit.com{post.permalink}"

        # Truncate description
        desc = re.sub(r"\n{3,}", "\n\n", body).strip()[:800]

        return JobPost(
            title=clean_title or title,
            source="Reddit",
            company=company,
            location=location or ("Remote" if remote else ""),
            remote=remote,
            url=url,
            posted_at=posted_iso,
            deadline=deadline,
            experience=experience,
            salary=salary,
            description=desc,
            tools=tools,
            urgent=bool(deadline),
            raw_data={
                "reddit_id": post.id,
                "subreddit": post.subreddit.display_name,
                "score": post.score,
                "num_comments": post.num_comments,
                "posted_human": posted_human,
            },
        )
