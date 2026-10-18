"""Fetch Claude usage with the Claude Code credentials."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
BETA_HEADER = "oauth-2025-04-20"
KEYCHAIN_SERVICE = "Claude Code-credentials"
# Used when the version cannot be read from the claude command
FALLBACK_USER_AGENT = "claude-code/2.1.233"
REQUEST_TIMEOUT = 15.0


class UsageError(Exception):
    """Usage could not be fetched. The message is shown in the status line."""


class TokenExpiredError(UsageError):
    """The access token has expired. Using Claude Code refreshes it."""

    def __init__(self) -> None:
        super().__init__("token expired - run Claude Code")


@dataclass(frozen=True)
class UsageWindow:
    utilization: float  # Percentage used (0-100)
    resets_at: float | None  # Reset time (epoch seconds), None if null


@dataclass(frozen=True)
class Usage:
    session: UsageWindow | None  # five_hour
    weekly: UsageWindow | None  # seven_day


def user_agent() -> str:
    """Return the same User-Agent as the installed Claude Code."""
    try:
        result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=10, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return FALLBACK_USER_AGENT
    version = result.stdout.split()
    return f"claude-code/{version[0]}" if version else FALLBACK_USER_AGENT


def read_keychain() -> str:
    """Read the credentials (JSON) Claude Code stores in the keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise UsageError("keychain unavailable") from e
    if result.returncode != 0:
        raise UsageError("no Claude Code login in keychain")
    return result.stdout.strip()


def parse_credentials(raw: str, now: float) -> str:
    """Extract the access token. Raises TokenExpiredError if expired."""
    try:
        oauth = json.loads(raw)["claudeAiOauth"]
        token = oauth["accessToken"]
    except (ValueError, KeyError, TypeError) as e:
        raise UsageError("unexpected keychain data") from e
    expires_at = oauth.get("expiresAt")
    if isinstance(expires_at, (int, float)) and expires_at / 1000 <= now:
        raise TokenExpiredError()
    return token


def parse_timestamp(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def parse_window(value: object) -> UsageWindow | None:
    if not isinstance(value, dict):
        return None
    utilization = value.get("utilization")
    return UsageWindow(
        utilization=float(utilization) if isinstance(utilization, (int, float)) else 0.0,
        resets_at=parse_timestamp(value.get("resets_at")),
    )


def parse_usage(body: dict) -> Usage:
    return Usage(session=parse_window(body.get("five_hour")), weekly=parse_window(body.get("seven_day")))


def fetch_usage(agent: str) -> Usage:
    """Fetch usage. Blocks on network I/O."""
    token = parse_credentials(read_keychain(), time.time())
    request = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": BETA_HEADER,
            "User-Agent": agent,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            body = json.load(response)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise TokenExpiredError() from e
        raise UsageError(f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise UsageError("network error") from e
    except ValueError as e:
        raise UsageError("invalid response") from e
    if not isinstance(body, dict):
        raise UsageError("invalid response")
    return parse_usage(body)
