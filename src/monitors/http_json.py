import requests
import json
import time
from src.monitors import BaseMonitor, MonitorResult, register_monitor


@register_monitor
class HttpJsonMonitor(BaseMonitor):
    type_id = "http_json"
    name = "HTTP JSON API"
    description = "Hit a REST API and evaluate the JSON response with optional assertions"
    config_schema = {
        "url": {"type": "string", "label": "URL", "required": True},
        "method": {"type": "string", "label": "HTTP Method", "default": "GET", "required": False},
        "headers": {"type": "string", "label": "Custom headers (JSON)", "required": False},
        "body": {"type": "string", "label": "Request body (JSON, for POST/PUT)", "required": False},
        "json_path": {"type": "string", "label": "JSON field to check (e.g. status, data.health)", "required": False},
        "expected_value": {"type": "string", "label": "Expected value for that field", "required": False},
        "timeout": {"type": "number", "label": "Timeout (seconds)", "default": 15, "required": False},
    }

    def check(self) -> MonitorResult:
        url = self.config.get("url", "")
        method = self.config.get("method", "GET").upper()
        timeout = int(self.config.get("timeout", 15))

        if not url:
            return MonitorResult(status="error", error="No URL configured")

        try:
            headers = {}
            hdr_raw = self.config.get("headers", "")
            if hdr_raw:
                try:
                    headers = json.loads(hdr_raw)
                except json.JSONDecodeError:
                    return MonitorResult(status="error", error="Invalid headers JSON")

            kwargs = {"timeout": timeout, "headers": headers}
            body_raw = self.config.get("body", "")
            if body_raw and method in ("POST", "PUT", "PATCH"):
                kwargs["json"] = json.loads(body_raw) if body_raw else None

            start = time.time()
            resp = requests.request(method, url, **kwargs)
            elapsed = (time.time() - start) * 1000

            if resp.status_code >= 500:
                return MonitorResult(status="down", status_code=resp.status_code,
                                     response_time_ms=round(elapsed, 1),
                                     error=f"Server error: HTTP {resp.status_code}")

            json_path = self.config.get("json_path", "")
            expected = self.config.get("expected_value", "")

            if json_path and expected:
                try:
                    data = resp.json()
                    parts = json_path.split(".")
                    val = data
                    for p in parts:
                        if isinstance(val, dict):
                            val = val.get(p)
                        elif isinstance(val, list):
                            val = val[int(p)] if p.isdigit() else None
                        else:
                            val = None
                            break

                    matched = str(val) == expected
                    if not matched:
                        return MonitorResult(status="degraded", status_code=resp.status_code,
                                             response_time_ms=round(elapsed, 1),
                                             error=f"Expected {json_path}={expected}, got {val}")
                except (json.JSONDecodeError, ValueError, IndexError, TypeError) as e:
                    return MonitorResult(status="error", status_code=resp.status_code, error=f"JSON eval error: {e}")

            return MonitorResult(
                status="up", status_code=resp.status_code,
                response_time_ms=round(elapsed, 1),
                response_summary=f"HTTP {resp.status_code}, {len(resp.content)} bytes"
            )
        except requests.Timeout:
            return MonitorResult(status="down", error=f"Timeout after {timeout}s")
        except Exception as e:
            return MonitorResult(status="error", error=str(e))
