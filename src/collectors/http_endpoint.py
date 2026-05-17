import requests
from datetime import datetime
from bs4 import BeautifulSoup
from src.collectors import BaseCollector, CollectionResult, CollectedData, register_collector


@register_collector
class HttpEndpointCollector(BaseCollector):
    type_id = "http_endpoint"
    name = "HTTP Endpoint"
    description = "Fetch any URL or API endpoint and store the response. Perfect for JSON APIs, status pages, or any HTTP resource."
    config_schema = {
        "url": {"type": "string", "label": "URL", "required": True},
        "method": {"type": "string", "label": "HTTP Method", "default": "GET"},
        "headers": {"type": "string", "label": "Custom headers (JSON)", "required": False},
        "body": {"type": "string", "label": "Request body (for POST/PUT)", "required": False},
        "timeout": {"type": "number", "label": "Timeout (seconds)", "default": 30},
    }

    def collect(self) -> CollectionResult:
        url = self.config.get("url", "")
        method = self.config.get("method", "GET").upper()
        timeout = int(self.config.get("timeout", 30))

        if not url:
            return CollectionResult(status="error", error="No URL configured")

        try:
            headers = {"User-Agent": "PulseCollector/1.0"}
            hdr_raw = self.config.get("headers", "")
            if hdr_raw:
                import json
                headers.update(json.loads(hdr_raw))

            kwargs = {"timeout": timeout, "headers": headers}
            body_raw = self.config.get("body", "")
            if body_raw and method in ("POST", "PUT", "PATCH"):
                kwargs["data"] = body_raw

            resp = requests.request(method, url, **kwargs)

            content_type = resp.headers.get("content-type", "")
            is_json = "json" in content_type

            title = f"{method} {url}"
            content = ""

            if is_json:
                try:
                    import json
                    data = resp.json()
                    content = json.dumps(data, indent=2)
                except Exception:
                    content = resp.text[:50000]
            else:
                try:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    text = soup.get_text(separator='\n', strip=True)
                    content = text[:50000] if len(text) > 50000 else text
                    if soup.title and soup.title.string:
                        title = soup.title.string.strip()
                except Exception:
                    content = resp.text[:50000]

            return CollectionResult(
                status="success",
                items=[CollectedData(
                    title=title,
                    content=content,
                    url=url,
                    published_at=datetime.utcnow(),
                    raw_data={
                        "http_status": resp.status_code,
                        "content_length": len(resp.content),
                        "content_type": content_type,
                    }
                )],
                summary=f"HTTP {resp.status_code} ({len(resp.content)} bytes)"
            )

        except requests.Timeout:
            return CollectionResult(status="error", error=f"Timeout after {timeout}s")
        except Exception as e:
            return CollectionResult(status="error", error=str(e))
