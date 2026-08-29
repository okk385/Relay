from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

from .models import Handoff, OWNER_LABELS, validate_repository


class GitHubError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class LabelSpec:
    name: str
    color: str
    description: str


LABEL_SPECS = (
    LabelSpec("relay:codex", "1f6feb", "Next action belongs to Codex"),
    LabelSpec("relay:chatgpt", "8250df", "Next action belongs to ChatGPT"),
    LabelSpec("relay:human", "d93f0b", "A human decision is required"),
    LabelSpec("relay:done", "2da44e", "Relay task is complete"),
)


def resolve_github_token() -> str:
    for name in ("RELAY_GITHUB_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise GitHubError(
            "No GitHub token found. Set RELAY_GITHUB_TOKEN/GITHUB_TOKEN or run `gh auth login`."
        ) from exc
    token = result.stdout.strip()
    if not token:
        raise GitHubError("`gh auth token` returned an empty token")
    return token


def latest_label_event(events: Iterable[dict[str, Any]], label: str) -> dict[str, Any] | None:
    matching = [
        event
        for event in events
        if event.get("event") == "labeled"
        and isinstance(event.get("label"), dict)
        and event["label"].get("name") == label
        and event.get("id") is not None
    ]
    if not matching:
        return None
    return max(matching, key=lambda event: int(event["id"]))


class GitHubClient:
    def __init__(
        self,
        repository: str,
        token: str,
        *,
        api_base: str = "https://api.github.com",
        timeout_seconds: int = 20,
    ):
        self.repository = validate_repository(repository)
        self.token = token.strip()
        if not self.token:
            raise ValueError("GitHub token must not be empty")
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str | int] | None = None,
        payload: dict[str, Any] | None = None,
        allow_status: set[int] | None = None,
    ) -> Any:
        url = f"{self.api_base}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "relay-ssh/0.1",
                "X-GitHub-Api-Version": "2022-11-28",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = response.read()
                if not data:
                    return None
                return json.loads(data.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if allow_status and exc.code in allow_status:
                return None
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubError(f"GitHub API {method} {path} failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise GitHubError(f"GitHub API request failed: {exc.reason}") from exc

    def list_labeled_issues(self, label: str) -> list[dict[str, Any]]:
        raw = self._request(
            "GET",
            f"/repos/{self.repository}/issues",
            query={"state": "open", "labels": label, "per_page": 100, "sort": "created"},
        )
        if not isinstance(raw, list):
            raise GitHubError("unexpected issues response from GitHub")
        return [item for item in raw if "pull_request" not in item]

    def list_issue_events(self, issue_number: int) -> list[dict[str, Any]]:
        all_events: list[dict[str, Any]] = []
        for page in range(1, 11):
            raw = self._request(
                "GET",
                f"/repos/{self.repository}/issues/{issue_number}/events",
                query={"per_page": 100, "page": page},
            )
            if not isinstance(raw, list):
                raise GitHubError("unexpected issue events response from GitHub")
            all_events.extend(raw)
            if len(raw) < 100:
                break
        return all_events

    def pending_handoffs(
        self,
        label: str,
        processed_event_ids: set[int],
    ) -> list[Handoff]:
        handoffs: list[Handoff] = []
        for issue in self.list_labeled_issues(label):
            number = int(issue["number"])
            event = latest_label_event(self.list_issue_events(number), label)
            if not event:
                continue
            event_id = int(event["id"])
            if event_id in processed_event_ids:
                continue
            handoffs.append(
                Handoff(
                    repository=self.repository,
                    issue_number=number,
                    issue_title=str(issue.get("title", "")),
                    issue_url=str(issue.get("html_url", "")),
                    event_id=event_id,
                    event_created_at=str(event.get("created_at", "")),
                    target_label=label,
                )
            )
        return sorted(handoffs, key=lambda item: (item.event_created_at, item.event_id))

    def issue_has_label(self, issue_number: int, label: str) -> bool:
        issue = self._request("GET", f"/repos/{self.repository}/issues/{issue_number}")
        if not isinstance(issue, dict):
            raise GitHubError("unexpected issue response from GitHub")
        if issue.get("state") != "open":
            return False
        labels = issue.get("labels", [])
        return any(isinstance(item, dict) and item.get("name") == label for item in labels)

    def ensure_protocol_labels(self) -> list[str]:
        created: list[str] = []
        for spec in LABEL_SPECS:
            existing = self._request(
                "GET",
                f"/repos/{self.repository}/labels/{urllib.parse.quote(spec.name, safe='')}",
                allow_status={404},
            )
            if existing is not None:
                continue
            self._request(
                "POST",
                f"/repos/{self.repository}/labels",
                payload={
                    "name": spec.name,
                    "color": spec.color,
                    "description": spec.description,
                },
            )
            created.append(spec.name)
        return created

    def verify_protocol_labels(self) -> set[str]:
        raw = self._request(
            "GET",
            f"/repos/{self.repository}/labels",
            query={"per_page": 100},
        )
        if not isinstance(raw, list):
            raise GitHubError("unexpected labels response from GitHub")
        present = {item.get("name") for item in raw if isinstance(item, dict)}
        return set(OWNER_LABELS).intersection(present)
