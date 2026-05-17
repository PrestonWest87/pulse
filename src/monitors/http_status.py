import requests
import time
from src.monitors import BaseMonitor, MonitorResult, register_monitor


@register_monitor
class HttpStatusMonitor(BaseMonitor):
    type_id = "http_status"
    name = "HTTP Status"
    description = "Check if a URL returns an expected HTTP status code"
    config_schema = {
        "url": {"type": "string", "label": "URL", "required": True},
        "method": {"type": "string", "label": "HTTP Method", "default": "GET", "required": False},
        "expected_status": {"type": "number", "label": "Expected status code", "default": 200, "required": False},
        "timeout": {"type": "number", "label": "Timeout (seconds)", "default": 10, "required": False},
    }

    def check(self) -> MonitorResult:
        url = self.config.get("url", "")
        method = self.config.get("method", "GET").upper()
        expected = int(self.config.get("expected_status", 200))
        timeout = int(self.config.get("timeout", 10))

        if not url:
            return MonitorResult(status="error", error="No URL configured")

        try:
            start = time.time()
            resp = requests.request(method, url, timeout=timeout, allow_redirects=True)
            elapsed = (time.time() - start) * 1000

            status = "up" if resp.status_code == expected else "degraded"
            error = None if resp.status_code == expected else f"Expected {expected}, got {resp.status_code}"

            return MonitorResult(
                status=status,
                status_code=resp.status_code,
                response_time_ms=round(elapsed, 1),
                response_summary=f"HTTP {resp.status_code} ({len(resp.content)} bytes)",
                error=error
            )
        except requests.Timeout:
            return MonitorResult(status="down", error=f"Timeout after {timeout}s")
        except requests.ConnectionError as e:
            return MonitorResult(status="down", error=f"Connection error: {e}")
        except Exception as e:
            return MonitorResult(status="error", error=str(e))
