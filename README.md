# Pulse — Data Collector

Collect data from RSS feeds, web pages, release trackers, and HTTP endpoints.
Everything collected is stored, searchable, and can trigger notifications on keyword matches.

Track game updates, Steam releases, news headlines, product deals, changelogs — anything you want.

## Architecture

- **Frontend**: Streamlit dashboard on port 8501
- **Worker**: Background scheduler for periodic collection
- **Webhook**: FastAPI gateway on port 8100 (ingest data from external sources)
- **Database**: SQLite (default) or PostgreSQL

## Quick Start

```bash
docker compose up --build -d
```

Access the dashboard at `http://localhost:8501` (default: `admin` / `admin123`).

## Collector Types

| Type | What it collects |
|------|-----------------|
| RSS / Atom | Feed entries from any RSS or Atom source |
| Web Page | Page content snapshots with CSS selector extraction |
| Release Tracker | New releases from GitHub, PyPI, npm, Docker Hub |
| HTTP Endpoint | Response data from any URL or API |

## Use Cases

- Track new game releases or updates from Steam/Epic/Itch.io RSS feeds
- Monitor GitHub releases for your favorite tools and libraries
- Follow news headlines from any RSS source
- Watch for price drops or deals on product pages
- Collect changelogs and patch notes
- Archive content from any website that updates regularly

## Notification Channels

| Channel | Destination |
|---------|-------------|
| Outbound Webhook | POST to any URL |
| Slack | Incoming webhook |
| Discord | Webhook with embeds |
| SMS | Twilio text messaging |
| Email | SMTP with TLS |

## License

MIT
