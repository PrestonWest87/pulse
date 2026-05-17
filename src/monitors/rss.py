import feedparser
import re
from datetime import datetime, timezone
from src.monitors import BaseMonitor, MonitorResult, register_monitor


@register_monitor
class RSSFeedMonitor(BaseMonitor):
    type_id = "rss"
    name = "RSS/Atom Feed"
    description = "Poll any RSS or Atom feed for new entries, with optional keyword filtering"
    config_schema = {
        "url": {"type": "string", "label": "Feed URL", "required": True},
        "keyword_filter": {"type": "string", "label": "Keyword filter (comma-separated, optional)", "required": False},
        "max_age_hours": {"type": "number", "label": "Max entry age (hours)", "default": 24, "required": False},
    }

    def check(self) -> MonitorResult:
        url = self.config.get("url", "")
        if not url:
            return MonitorResult(status="error", error="No URL configured")

        keywords = [k.strip().lower() for k in self.config.get("keyword_filter", "").split(",") if k.strip()]
        max_age = float(self.config.get("max_age_hours", 24))

        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                return MonitorResult(status="error", error=f"Feed parse error: {feed.bozo_exception}")

            cutoff = datetime.now(timezone.utc).timestamp() - (max_age * 3600)
            recent = []
            for entry in feed.entries[:20]:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    entry_ts = datetime(*published[:6], tzinfo=timezone.utc).timestamp()
                    if entry_ts < cutoff:
                        continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                if keywords:
                    text = (title + " " + summary).lower()
                    if not any(kw in text for kw in keywords):
                        continue

                recent.append({"title": title, "link": entry.get("link", ""), "published": entry.get("published", "")})

            if recent:
                summary = f"{len(recent)} new entries"
                return MonitorResult(status="up", response_summary=summary, raw_data=recent)
            else:
                return MonitorResult(status="up", response_summary="No new entries")

        except Exception as e:
            return MonitorResult(status="error", error=str(e))
