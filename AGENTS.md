# Pulse — Data Collector

## Overview

Collect data from RSS feeds, web pages, release trackers (GitHub/PyPI/npm), and HTTP endpoints. Everything collected is stored, searchable, and can trigger alerts on keyword matches.

## Architecture

- **Frontend** (`src/app.py`): Streamlit — Feed, Sources, Search, Alerts
- **Worker** (`src/scheduler.py`): Background collector scheduler
- **Webhook** (`src/webhook_listener.py`): FastAPI inbound data gateway (port 8100)
- **Database**: SQLite (default) or PostgreSQL

## Commands

```bash
docker compose up --build -d
docker compose logs -f worker
docker compose logs -f webhook
docker compose restart worker
```

## Key Files

| File | Purpose |
|------|---------|
| `src/app.py` | Streamlit UI |
| `src/services.py` | Data access layer |
| `src/database.py` | Models: Source, CollectedItem, Alert, etc. |
| `src/scheduler.py` | Background collector scheduler |
| `src/alert_engine.py` | Keyword matching + alert dispatch |
| `src/collectors/` | Collector plugins |
| `src/outbounds/` | Notification channel plugins |

## Collector Types

| Type | File | Collects |
|------|------|----------|
| rss | `src/collectors/rss.py` | RSS/Atom feed entries |
| web_page | `src/collectors/web_page.py` | Web page content snapshots |
| release_tracker | `src/collectors/release_tracker.py` | GitHub, PyPI, npm, Docker releases |
| http_endpoint | `src/collectors/http_endpoint.py` | Any HTTP API/endpoint response |

## Outbound Channels

| Type | File | Destination |
|------|------|-------------|
| webhook | `src/outbounds/webhook.py` | POST to any URL |
| slack | `src/outbounds/slack.py` | Slack webhook |
| discord | `src/outbounds/discord.py` | Discord webhook |
| twilio_sms | `src/outbounds/twilio_sms.py` | SMS via Twilio |
| email | `src/outbounds/email.py` | SMTP email |

## Collection Flow

1. Scheduler calls `collect()` on each enabled Source at its interval
2. Collector returns `CollectionResult(items=[...])`
3. New items are deduplicated by content hash and saved as `CollectedItem`
4. If source has `alert_on_keywords`, items are scanned and alerts fire
5. Alerts route through notification rules to outbound channels

## Adding a New Collector

```python
from src.collectors import BaseCollector, CollectionResult, CollectedData, register_collector

@register_collector
class MyCollector(BaseCollector):
    type_id = "my_type"
    name = "My Collector"
    config_schema = {"api_key": {"type": "string", "label": "API Key", "required": True}}

    def collect(self) -> CollectionResult:
        # ... fetch data ...
        return CollectionResult(status="success", items=[CollectedData(title="...", content="...")])
```

## Default Credentials

- Login: `admin` / `admin123`
- Ingest webhook: `POST http://localhost:8100/ingest/{source_name}`
