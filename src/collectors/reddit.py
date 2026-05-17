import feedparser
from datetime import datetime, timezone
from src.collectors import BaseCollector, CollectionResult, CollectedData, register_collector


@register_collector
class RedditCollector(BaseCollector):
    type_id = "reddit"
    name = "Reddit"
    description = "Collect posts from any public subreddit via RSS. No API key needed."
    config_schema = {
        "subreddit": {"type": "string", "label": "Subreddit name", "required": True},
        "sort": {"type": "string", "label": "Sort order", "enum": ["hot", "new", "top"], "default": "new"},
        "max_age_hours": {"type": "number", "label": "Max age (hours)", "default": 72},
    }

    def collect(self) -> CollectionResult:
        subreddit = self.config.get("subreddit", "").strip()
        sort = self.config.get("sort", "new")
        max_age = float(self.config.get("max_age_hours", 72))

        if not subreddit:
            return CollectionResult(status="error", error="No subreddit configured")

        url = f"https://www.reddit.com/r/{subreddit}/{sort}/.rss"

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

                content = entry.get("summary", "") or (entry.get("content") or [{}])[0].get("value", "")

                items.append(CollectedData(
                    title=entry.get("title", "Untitled"),
                    content=content,
                    url=entry.get("link", ""),
                    author=entry.get("author", ""),
                    published_at=pub_dt,
                    raw_data={"subreddit": subreddit, "sort": sort}
                ))

            return CollectionResult(
                status="success",
                items=items,
                summary=f"{len(items)} posts from r/{subreddit}"
            )

        except Exception as e:
            return CollectionResult(status="error", error=str(e))
