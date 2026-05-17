import feedparser
from datetime import datetime, timezone
from src.collectors import BaseCollector, CollectionResult, CollectedData, register_collector


@register_collector
class SteamCollector(BaseCollector):
    type_id = "steam"
    name = "Steam News"
    description = "Track Steam news, updates, and announcements for any game. Use 'all' as App ID for the general feed."
    config_schema = {
        "app_id": {"type": "string", "label": "Steam App ID (or 'all')", "required": True},
        "max_age_hours": {"type": "number", "label": "Max age (hours)", "default": 72},
    }

    def collect(self) -> CollectionResult:
        app_id = self.config.get("app_id", "").strip()
        max_age = float(self.config.get("max_age_hours", 72))

        if not app_id:
            return CollectionResult(status="error", error="No App ID configured")

        url = "https://store.steampowered.com/feeds/news/" if app_id == "all" else f"https://store.steampowered.com/feeds/news/app/{app_id}/"

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

                content = (entry.get("content") or [{}])[0].get("value", "") or entry.get("summary", "") or entry.get("description", "")

                items.append(CollectedData(
                    title=entry.get("title", "Untitled"),
                    content=content,
                    url=entry.get("link", ""),
                    author=entry.get("author", ""),
                    published_at=pub_dt,
                    raw_data={"app_id": app_id}
                ))

            return CollectionResult(
                status="success",
                items=items,
                summary=f"{len(items)} Steam news items for app={app_id}"
            )

        except Exception as e:
            return CollectionResult(status="error", error=str(e))
