from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    # Reddit
    reddit_client_id: str = Field(default="", env="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", env="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(
        default="DataJobsScraper/1.0", env="REDDIT_USER_AGENT"
    )

    # Adzuna
    adzuna_app_id: str = Field(default="", env="ADZUNA_APP_ID")
    adzuna_app_key: str = Field(default="", env="ADZUNA_APP_KEY")

    # Optional proxy
    proxy_url: Optional[str] = Field(default=None, env="PROXY_URL")

    # Scraper behaviour
    scrape_interval_hours: int = Field(default=24, env="SCRAPE_INTERVAL_HOURS")
    max_jobs_per_source: int = Field(default=50, env="MAX_JOBS_PER_SOURCE")
    db_path: str = Field(default="data/jobs.db", env="DB_PATH")

    # API
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000", env="CORS_ORIGINS"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Data analysis search terms — covers both roles and tools
SEARCH_TERMS = [
    "data analyst",
    "data analysis",
    "business analyst",
    "data scientist",
    "analytics engineer",
    "BI analyst",
    "business intelligence",
    "SQL analyst",
    "Python analyst",
    "Power BI",
    "Tableau",
    "data engineer",
    "quantitative analyst",
    "reporting analyst",
    "insights analyst",
]

REDDIT_SUBREDDITS = [
    "datascience",
    "datasets",
    "analytics",
    "BusinessIntelligence",
    "jobs",
    "forhire",
    "remotework",
    "cscareerquestions",
    "dataengineering",
]
