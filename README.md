# DataJobs Scraper — Full Stack System

A multi-source data analysis job aggregator that scrapes Reddit, LinkedIn, Indeed,
Glassdoor, RemoteOK, We Work Remotely, and more.

## Architecture

```
datajobs/
├── scrapers/          # Individual source scrapers
│   ├── reddit.py      # Reddit API (PRAW) scraper
│   ├── linkedin.py    # LinkedIn scraper (Playwright)
│   ├── indeed.py      # Indeed scraper (Playwright)
│   ├── remoteok.py    # RemoteOK API scraper
│   ├── weworkremotely.py  # WWR RSS scraper
│   ├── adzuna.py      # Adzuna API scraper
│   └── base.py        # Base scraper class
├── api/
│   ├── server.py      # FastAPI server
│   └── models.py      # Pydantic models
├── frontend/          # React frontend
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
├── config/
│   └── settings.py    # Config & env vars
├── data/              # SQLite database lives here
├── scheduler.py       # APScheduler job runner
├── requirements.txt
└── .env.example
```

## Quick Start

### 1. Python backend

```bash
cd datajobs
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium      # For LinkedIn/Indeed
cp .env.example .env             # Fill in your credentials
```

### 2. Configure .env

```
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=DataJobsScraper/1.0

ADZUNA_APP_ID=your_id
ADZUNA_APP_KEY=your_key

# Optional - speeds up LinkedIn/Indeed
PROXY_URL=http://user:pass@host:port
```

### 3. Run scrapers

```bash
# Run all scrapers once
python scheduler.py --run-now

# Start scheduler (runs every 2 hours)
python scheduler.py
```

### 4. Start API server

```bash
uvicorn api.server:app --reload --port 8000
```

### 5. Start frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /jobs | List jobs (filter by q, source, level, remote, location) |
| GET | /jobs/{id} | Single job detail |
| GET | /sources | Scraper health status |
| GET | /stats | Aggregated stats |
| POST | /scrape | Trigger manual scrape |

## Getting API Keys

- **Reddit**: https://www.reddit.com/prefs/apps → create app (script type)
- **Adzuna**: https://developer.adzuna.com → free tier, 250 req/day
- **RemoteOK**: No key needed — public JSON API
- **We Work Remotely**: No key needed — RSS feed
- **LinkedIn/Indeed**: Playwright-based (no API key, uses browser automation)
