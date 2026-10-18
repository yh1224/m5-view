import json

import pytest

import usage_api

NOW = 1_800_000_000.0


def credentials(**oauth):
    return json.dumps({"claudeAiOauth": {"accessToken": "token", **oauth}})


def test_parse_credentials():
    assert usage_api.parse_credentials(credentials(expiresAt=(NOW + 60) * 1000), NOW) == "token"


def test_parse_credentials_without_expiry():
    assert usage_api.parse_credentials(credentials(), NOW) == "token"


def test_parse_credentials_expired():
    with pytest.raises(usage_api.TokenExpiredError):
        usage_api.parse_credentials(credentials(expiresAt=(NOW - 1) * 1000), NOW)


@pytest.mark.parametrize("raw", ["", "not json", "{}", json.dumps({"claudeAiOauth": {}})])
def test_parse_credentials_invalid(raw):
    with pytest.raises(usage_api.UsageError):
        usage_api.parse_credentials(raw, NOW)


def test_parse_usage():
    usage = usage_api.parse_usage(
        {
            "five_hour": {"utilization": 62.0, "resets_at": "2026-10-18T03:00:00.123456+00:00"},
            "seven_day": {"utilization": 34, "resets_at": None},
        }
    )
    assert usage.session.utilization == 62.0
    assert usage.session.resets_at == pytest.approx(1792292400.123456)
    assert usage.weekly.utilization == 34.0
    assert usage.weekly.resets_at is None


def test_parse_usage_missing_windows():
    usage = usage_api.parse_usage({"five_hour": None})
    assert usage.session is None
    assert usage.weekly is None
