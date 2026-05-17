import feedparser
from datetime import datetime, timezone
from src.collectors import BaseCollector, CollectionResult, CollectedData, register_collector


@register_collector
class RSSCollector(BaseCollector):
    type_id = "rss"
    name = "RSS / Atom Feed"
    description = "Collect articles from any RSS or Atom feed. Every new entry is stored and searchable."
    config_schema = {
        "url": {"type": "string", "label": "Feed URL", "required": True},
        "max_age_hours": {"type": "number", "label": "Max age (hours)", "default": 72},
    }

    def collect(self) -> CollectionResult:
        url = self.config.get("url", "")
        if not url:
            return CollectionResult(status="error", error="No URL configured")

        max_age = float(self.config.get("max_age_hours", 72))

        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                return CollectionResult(status="error", error=f"Feed parse error: {feed.bozo_exception}")

            cutoff = datetime.now(timezone.utc).timestamp() - (max_age * 3600)
            items = []

            for entry in feed.entries:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    entry_ts = datetime(*published[:6], tzinfo=timezone.utc).timestamp()
                    if entry_ts < cutoff:
                        continue
                    pub_dt = datetime.fromtimestamp(entry_ts, tz=timezone.utc)
                else:
                    pub_dt = datetime.now(timezone.utc)

                content = ""
                if entry.get("content"):
                    content = entry.content[0].get("value", "")
                elif entry.get("summary"):
                    content = entry.summary
                elif entry.get("description"):
                    content = entry.description

                items.append(CollectedData(
                    title=entry.get("title", "Untitled"),
                    content=content,
                    url=entry.get("link", ""),
                    author=entry.get("author", ""),
                    published_at=pub_dt,
                    raw_data={
                        "feed_title": feed.feed.get("title", "") if hasattr(feed, "feed") else "",
                        "feed_link": feed.feed.get("link", "") if hasattr(feed, "feed") else "",
                    }
                ))

            return CollectionResult(
                status="success",
                items=items,
                summary=f"{len(items)} entries from feed"
            )

        except Exception as e:
            return CollectionResult(status="error", error=str(e))
