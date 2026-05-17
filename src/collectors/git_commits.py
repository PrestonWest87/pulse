import requests
from datetime import datetime
from src.collectors import BaseCollector, CollectionResult, CollectedData, register_collector


@register_collector
class GitCommitWatcher(BaseCollector):
    type_id = "git_commits"
    name = "Git Commit Watcher"
    description = "Watch a GitHub repo for new commits on a branch. Get notified every time code is pushed."
    config_schema = {
        "owner": {"type": "string", "label": "Repo owner (user/org)", "required": True},
        "repo": {"type": "string", "label": "Repo name", "required": True},
        "branch": {"type": "string", "label": "Branch", "default": "main"},
        "max_age_hours": {"type": "number", "label": "Max age (hours)", "default": 72},
    }

    def collect(self) -> CollectionResult:
        owner = self.config.get("owner", "").strip()
        repo = self.config.get("repo", "").strip()
        branch = self.config.get("branch", "main")
        max_age = float(self.config.get("max_age_hours", 72))

        if not owner or not repo:
            return CollectionResult(status="error", error="Owner and repo required")

        url = f"https://api.github.com/repos/{owner}/{repo}/commits?sha={branch}&per_page=15"
        resp = requests.get(url, timeout=15, headers={
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'PulseCollector/1.0'
        })
        if resp.status_code != 200:
            return CollectionResult(status="error", error=f"GitHub API: HTTP {resp.status_code}")

        data = resp.json()
        if not isinstance(data, list):
            return CollectionResult(status="error", error="Unexpected GitHub API response")

        cutoff = datetime.utcnow().timestamp() - (max_age * 3600)
        items = []

        for commit in data:
            commit_info = commit.get("commit", {})
            committer = commit_info.get("committer", {})
            date_str = committer.get("date", "")
            pub_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")) if date_str else datetime.utcnow()

            if pub_dt.timestamp() < cutoff:
                continue

            author = ""
            if isinstance(commit_info.get("author"), dict):
                author = commit_info["author"].get("name", "")
            sha_short = commit.get("sha", "")[:8]
            message = (commit_info.get("message") or "").split("\n")[0]
            title = f"{owner}/{repo}: {message[:100]}"

            items.append(CollectedData(
                title=title,
                content=commit_info.get("message", ""),
                url=commit.get("html_url", ""),
                author=author,
                published_at=pub_dt,
                raw_data={
                    "sha": commit.get("sha", ""),
                    "branch": branch,
                    "committer": committer.get("name", ""),
                }
            ))

        return CollectionResult(
            status="success",
            items=items,
            summary=f"{len(items)} new commits on {owner}/{repo}/{branch}"
        )
