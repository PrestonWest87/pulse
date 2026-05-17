import requests
import re
import hashlib
from datetime import datetime
from bs4 import BeautifulSoup
from src.collectors import BaseCollector, CollectionResult, CollectedData, register_collector


@register_collector
class WebPageCollector(BaseCollector):
    type_id = "web_page"
    name = "Web Page"
    description = "Fetch a webpage and store its content. Each fetch captures a snapshot you can compare against."
    config_schema = {
        "url": {"type": "string", "label": "URL", "required": True},
        "extract_selector": {"type": "string", "label": "CSS selector to extract (leave blank for full body)", "required": False},
        "strip_tags": {"type": "boolean", "label": "Strip HTML tags", "default": True},
        "timeout": {"type": "number", "label": "Timeout (seconds)", "default": 30},
    }

    def collect(self) -> CollectionResult:
        url = self.config.get("url", "")
        timeout = int(self.config.get("timeout", 30))
        selector = self.config.get("extract_selector", "")
        strip = bool(self.config.get("strip_tags", True))

        if not url:
            return CollectionResult(status="error", error="No URL configured")

        try:
            resp = requests.get(url, timeout=timeout, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; PulseCollector/1.0)'
            })

            if resp.status_code != 200:
                return CollectionResult(status="error", error=f"HTTP {resp.status_code}")

            soup = BeautifulSoup(resp.text, 'html.parser')

            if selector:
                selected = soup.select(selector)
                content = "\n".join(str(s) for s in selected) if selected else resp.text
            else:
                content = resp.text

            if strip:
                text = BeautifulSoup(content, 'html.parser').get_text(separator='\n', strip=True)
            else:
                text = content

            title = soup.title.string.strip() if soup.title and soup.title.string else url

            return CollectionResult(
                status="success",
                items=[CollectedData(
                    title=title,
                    content=text[:50000],
                    url=url,
                    published_at=datetime.utcnow(),
                    raw_data={
                        "http_status": resp.status_code,
                        "content_length": len(resp.text),
                        "content_type": resp.headers.get("content-type", ""),
                    }
                )],
                summary=f"Fetched {len(text)} chars from {url}"
            )

        except requests.Timeout:
            return CollectionResult(status="error", error=f"Timeout after {timeout}s")
        except Exception as e:
            return CollectionResult(status="error", error=str(e))
