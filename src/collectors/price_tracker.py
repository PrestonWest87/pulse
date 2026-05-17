import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from src.collectors import BaseCollector, CollectionResult, CollectedData, register_collector


@register_collector
class PriceTracker(BaseCollector):
    type_id = "price_tracker"
    name = "Price Tracker"
    description = "Monitor product prices on any website. Provide a URL and CSS selector for the price element."
    config_schema = {
        "url": {"type": "string", "label": "Product URL", "required": True},
        "price_selector": {"type": "string", "label": "CSS selector for price element", "required": True},
        "name_selector": {"type": "string", "label": "CSS selector for product name (optional)", "required": False},
        "currency": {"type": "string", "label": "Currency symbol", "default": "$"},
        "timeout": {"type": "number", "label": "Timeout (seconds)", "default": 30},
    }

    def collect(self) -> CollectionResult:
        url = self.config.get("url", "")
        price_sel = self.config.get("price_selector", "")
        name_sel = self.config.get("name_selector", "")
        currency = self.config.get("currency", "$")
        timeout = int(self.config.get("timeout", 30))

        if not url or not price_sel:
            return CollectionResult(status="error", error="URL and price selector required")

        try:
            resp = requests.get(url, timeout=timeout, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; PulseCollector/1.0)'
            })
            if resp.status_code != 200:
                return CollectionResult(status="error", error=f"HTTP {resp.status_code}")

            soup = BeautifulSoup(resp.text, 'html.parser')
            price_el = soup.select_one(price_sel)
            if not price_el:
                return CollectionResult(status="error", error=f"Price selector '{price_sel}' not found on page")

            price_text = price_el.get_text(strip=True)
            price_match = re.search(r'[\d,.]+', price_text)
            price_value = price_match.group(0) if price_match else price_text

            title = url
            if name_sel:
                name_el = soup.select_one(name_sel)
                if name_el:
                    title = name_el.get_text(strip=True)[:200]

            return CollectionResult(
                status="success",
                items=[CollectedData(
                    title=f"{title} \u2014 {currency}{price_value}",
                    content=f"Price: {currency}{price_value}\nSelector: {price_sel}\nFull text: {price_text}",
                    url=url,
                    published_at=datetime.utcnow(),
                    raw_data={"price": price_value, "currency": currency, "full_text": price_text}
                )],
                summary=f"Price {currency}{price_value} at {url[:80]}"
            )

        except requests.Timeout:
            return CollectionResult(status="error", error=f"Timeout after {timeout}s")
        except Exception as e:
            return CollectionResult(status="error", error=str(e))
