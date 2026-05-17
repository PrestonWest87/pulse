# Pulse — Universal Monitor & Alerting Platform

A general-purpose monitoring and alerting platform. Watch anything — RSS feeds, websites, APIs, TCP endpoints, or custom scripts — and get notified via webhooks, Slack, Discord, SMS, or email.

Built from the NOC Intelligence Fusion Center, generalized into a plugin-based universal monitor.

## Architecture

- **Frontend**: Streamlit dashboard on port 8501
- **Worker**: Background scheduler for periodic checks
- **Webhook**: FastAPI gateway on port 8100 (inbound + outbound)
- **Database**: SQLite (default) or PostgreSQL

## Quick Start

```bash
docker compose up --build -d
```

Access the dashboard at `http://localhost:8501` (default: `admin` / `admin123`).

## Monitor Types

| Type | Description |
|------|-------------|
| RSS/Atom | Poll feeds for new entries |
| HTTP Status | Check if a URL returns expected status |
| HTTP JSON | Hit a REST API, evaluate JSON response |
| Web Scrape | Fetch HTML, check for content patterns |
| TCP Ping | Open TCP connection to host:port |
| Script | Run a command/script, check exit code |
| Webhook (inbound) | Listen for external system events |

## Notification Channels

| Channel | Description |
|---------|-------------|
| Outbound Webhook | POST JSON to any URL |
| Slack | Incoming webhook integration |
| Discord | Webhook integration with embeds |
| SMS | Twilio-based text messaging |
| Email | SMTP with TLS support |

## License

MIT
