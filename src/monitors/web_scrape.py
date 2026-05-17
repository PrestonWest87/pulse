import requests
import re
import time
from bs4 import BeautifulSoup
from src.monitors import BaseMonitor, MonitorResult, register_monitor


@register_monitor
class WebScrapeMonitor(BaseMonitor):
    type_id = "web_scrape"
    name = "Web Scrape"
    description = "Fetch a webpage and check for content patterns using regex or CSS selectors"
    config_schema = {
        "url": {"type": "string", "label": "URL", "required": True},
        "check_type": {"type": "string", "label": "Check type", "default": "text_present",
                       "enum": ["text_present", "text_absent", "regex_match", "css_selector"], "required": False},
        "pattern": {"type": "string", "label": "Text/regex to find or CSS selector", "required": True},
        "timeout": {"type": "number", "label": "Timeout (seconds)", "default": 15, "required": False},
    }

    def check(self) -> MonitorResult:
        url = self.config.get("url", "")
        check_type = self.config.get("check_type", "text_present")
        pattern = self.config.get("pattern", "")
        timeout = int(self.config.get("timeout", 15))

        if not url or not pattern:
            return MonitorResult(status="error", error="URL and pattern required")

        try:
            start = time.time()
            resp = requests.get(url, timeout=timeout, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; PulseMonitor/1.0)'
            })
            elapsed = (time.time() - start) * 1000

            if resp.status_code != 200:
                return MonitorResult(status="down", status_code=resp.status_code,
                                     response_time_ms=round(elapsed, 1),
                                     error=f"HTTP {resp.status_code}")

            found = False
            detail = ""
            if check_type == "text_present":
                found = pattern.lower() in resp.text.lower()
                detail = f"Text {'found' if found else 'not found'}"
            elif check_type == "text_absent":
                found = pattern.lower() not in resp.text.lower()
                detail = f"Text {'absent' if found else 'present'}"
            elif check_type == "regex_match":
                found = bool(re.search(pattern, resp.text, re.IGNORECASE))
                detail = f"Regex {'matched' if found else 'no match'}"
            elif check_type == "css_selector":
                soup = BeautifulSoup(resp.text, 'html.parser')
                found = len(soup.select(pattern)) > 0
                detail = f"CSS selector {'matched' if found else 'no match'}"

            status = "up" if found else "degraded"
            error = None if found else f"Pattern not matched ({check_type})"

            return MonitorResult(
                status=status, status_code=resp.status_code,
                response_time_ms=round(elapsed, 1),
                response_summary=detail, error=error
            )
        except Exception as e:
            return MonitorResult(status="error", error=str(e))
