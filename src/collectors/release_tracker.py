import requests
import re
from datetime import datetime
from src.collectors import BaseCollector, CollectionResult, CollectedData, register_collector


@register_collector
class ReleaseTracker(BaseCollector):
    type_id = "release_tracker"
    name = "Release Tracker"
    description = "Track new releases from GitHub, PyPI, npm, or any semver API. Get notified when new versions ship."
    config_schema = {
        "source_type": {"type": "string", "label": "Source", "enum": ["github_releases", "pypi", "npm", "docker_hub"], "required": True},
        "owner": {"type": "string", "label": "Owner/org (GitHub/Docker)", "required": False},
        "repo": {"type": "string", "label": "Repo/project name", "required": True},
        "include_prereleases": {"type": "boolean", "label": "Include pre-releases", "default": False},
    }

    def collect(self) -> CollectionResult:
        source_type = self.config.get("source_type", "")
        repo = self.config.get("repo", "")
        owner = self.config.get("owner", "")

        if not repo:
            return CollectionResult(status="error", error="No repo configured")

        try:
            if source_type == "github_releases":
                return self._collect_github(owner, repo)
            elif source_type == "pypi":
                return self._collect_pypi(repo)
            elif source_type == "npm":
                return self._collect_npm(repo)
            elif source_type == "docker_hub":
                return self._collect_docker(owner, repo)
            else:
                return CollectionResult(status="error", error=f"Unknown source type: {source_type}")
        except Exception as e:
            return CollectionResult(status="error", error=str(e))

    def _collect_github(self, owner, repo):
        include_pre = bool(self.config.get("include_prereleases", False))
        url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=10"
        resp = requests.get(url, timeout=15, headers={
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'PulseCollector/1.0'
        })
        if resp.status_code != 200:
            return CollectionResult(status="error", error=f"GitHub API: HTTP {resp.status_code}")

        data = resp.json()
        if not isinstance(data, list):
            return CollectionResult(status="error", error="Unexpected GitHub API response")

        items = []
        for rel in data:
            if not include_pre and rel.get("prerelease"):
                continue
            tag = rel.get("tag_name", "")
            published = rel.get("published_at")
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00")) if published else datetime.utcnow()

            items.append(CollectedData(
                title=f"{owner}/{repo} {tag}",
                content=rel.get("body") or rel.get("name") or "",
                url=rel.get("html_url", ""),
                author=rel.get("author", {}).get("login", "") if isinstance(rel.get("author"), dict) else "",
                published_at=pub_dt,
                raw_data={
                    "tag": tag,
                    "prerelease": rel.get("prerelease", False),
                    "draft": rel.get("draft", False),
                }
            ))

        return CollectionResult(
            status="success",
            items=items,
            summary=f"{len(items)} releases from {owner}/{repo}"
        )

    def _collect_pypi(self, package):
        url = f"https://pypi.org/pypi/{package}/json"
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return CollectionResult(status="error", error=f"PyPI API: HTTP {resp.status_code}")

        data = resp.json()
        info = data.get("info", {})
        releases = data.get("releases", {})

        items = []
        for version, files in releases.items():
            if not files:
                continue
            upload = files[0].get("upload_time")
            pub_dt = datetime.fromisoformat(upload) if upload else datetime.utcnow()

            items.append(CollectedData(
                title=f"{package} v{version}",
                content=info.get("summary", ""),
                url=f"https://pypi.org/project/{package}/{version}/",
                author=info.get("author", ""),
                published_at=pub_dt,
                raw_data={"version": version, "package": package}
            ))

        items.sort(key=lambda x: x.published_at, reverse=True)
        return CollectionResult(
            status="success",
            items=items[:20],
            summary=f"{min(len(items), 20)} releases from PyPI/{package}"
        )

    def _collect_npm(self, package):
        url = f"https://registry.npmjs.org/{package}"
        resp = requests.get(url, timeout=15, headers={'Accept': 'application/vnd.npm.install-v1+json'})
        if resp.status_code != 200:
            return CollectionResult(status="error", error=f"npm API: HTTP {resp.status_code}")

        data = resp.json()
        versions = data.get("versions", {})
        time_data = data.get("time", {})

        items = []
        for ver in reversed(list(versions.keys())[-20:]):
            pub_str = time_data.get(ver)
            pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00")) if pub_str else datetime.utcnow()
            ver_info = versions[ver] or {}

            items.append(CollectedData(
                title=f"npm:{package}@{ver}",
                content=ver_info.get("description", "") if isinstance(ver_info, dict) else "",
                url=f"https://www.npmjs.com/package/{package}/v/{ver}",
                author="",
                published_at=pub_dt,
                raw_data={"version": ver, "package": package}
            ))

        return CollectionResult(
            status="success",
            items=items,
            summary=f"{len(items)} releases from npm/{package}"
        )

    def _collect_docker(self, owner, repo):
        if not owner:
            owner = "library"
        url = f"https://hub.docker.com/v2/repositories/{owner}/{repo}/tags?page_size=20"
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return CollectionResult(status="error", error=f"Docker Hub API: HTTP {resp.status_code}")

        data = resp.json()
        results = data.get("results", [])

        items = []
        for tag in results:
            tag_name = tag.get("name", "")
            last_updated = tag.get("last_updated")
            pub_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00")) if last_updated else datetime.utcnow()

            items.append(CollectedData(
                title=f"docker:{owner}/{repo}:{tag_name}",
                content="",
                url=f"https://hub.docker.com/r/{owner}/{repo}/tags",
                published_at=pub_dt,
                raw_data={"tag": tag_name, "image": f"{owner}/{repo}"}
            ))

        return CollectionResult(
            status="success",
            items=items,
            summary=f"{len(items)} tags from docker/{owner}/{repo}"
        )
