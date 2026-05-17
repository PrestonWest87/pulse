# Pulse — Universal Monitor & Alerting Platform

## Overview

General-purpose monitoring platform. Monitors anything via plugins and alerts via multiple channels.

## Architecture

- **Frontend** (`src/app.py`): Streamlit dashboard on port 8501
- **Worker** (`src/scheduler.py`): Background scheduler for periodic checks
- **Webhook** (`src/webhook_listener.py`): FastAPI gateway on port 8100
- **Database**: SQLite (default) or PostgreSQL (set `DATABASE_URL` in `.env`)

## Developer Commands

```bash
docker compose up --build -d
docker compose logs -f worker
docker compose logs -f webhook
docker compose restart worker
```

## Key Files

| File | Purpose |
|------|---------|
| `src/app.py` | Streamlit UI entrypoint |
| `src/services.py` | Data Access Layer (DAL) |
| `src/database.py` | SQLAlchemy models and init |
| `src/scheduler.py` | Background task scheduler |
| `src/alert_engine.py` | Alert evaluation and dispatch |
| `src/monitors/__init__.py` | Base Monitor plugin class |
| `src/notifiers/__init__.py` | Base Notifier plugin class |
| `src/llm.py` | LLM integration |
| `src/mailer.py` | SMTP mailer |

## Monitor Types

| Type | File | Description |
|------|------|-------------|
| rss | `src/monitors/rss.py` | RSS/Atom feed polling |
| http_status | `src/monitors/http_status.py` | HTTP status code check |
| http_json | `src/monitors/http_json.py` | REST API JSON evaluation |
| web_scrape | `src/monitors/web_scrape.py` | Web content scraping |
| tcp_ping | `src/monitors/tcp_ping.py` | TCP port connectivity |
| script | `src/monitors/script.py` | Shell command execution |
| webhook_in | `src/webhook_listener.py` | Inbound webhook receiver |

## Notification Channels

| Type | File | Description |
|------|------|-------------|
| webhook | `src/notifiers/webhook.py` | Outbound webhook POST |
| slack | `src/notifiers/slack.py` | Slack webhook integration |
| discord | `src/notifiers/discord.py` | Discord webhook with embeds |
| twilio_sms | `src/notifiers/twilio_sms.py` | Twilio SMS |
| email | `src/notifiers/email.py` | SMTP email |

## Default Credentials

- Login: `admin` / `admin123`
- Webhook (inbound): `POST http://localhost:8100/webhook/{monitor_name}`

## Adding New Monitor Types

1. Create a new file in `src/monitors/`
2. Subclass `BaseMonitor`, set `type_id`, `name`, `config_schema`
3. Implement `check()` returning `MonitorResult`
4. Decorate with `@register_monitor`

## Adding New Notification Channels

1. Create a new file in `src/notifiers/`
2. Subclass `BaseNotifier`, set `channel_type`, `name`, `config_schema`
3. Implement `send()` returning `NotificationResult`
4. Decorate with `@register_notifier`
