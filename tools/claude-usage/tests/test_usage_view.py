from datetime import datetime, timezone

import pytest

import usage_view
from usage_api import Usage, UsageWindow
from usage_view import ViewState

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
T = NOW.timestamp()


def window(utilization, resets_in):
    return UsageWindow(utilization, None if resets_in is None else T + resets_in)


def test_countdown_target_prefers_earliest_reset_below_limits():
    usage = Usage(window(50, 3600), window(30, 86400))
    target = usage_view.countdown_target(usage)
    assert (target.label, target.title, target.limited) == ("5h", "Session (5h)", False)


def test_countdown_target_prefers_limited_window():
    usage = Usage(window(50, 3600), window(100, 86400))
    target = usage_view.countdown_target(usage)
    assert (target.label, target.title, target.limited) == ("7d", "Limit reached", True)


def test_countdown_target_prefers_latest_reset_when_both_limited():
    usage = Usage(window(100, 3600), window(100, 86400))
    assert usage_view.countdown_target(usage).label == "7d"


def test_countdown_target_skips_unknown_reset():
    usage = Usage(window(100, None), None)
    assert usage_view.countdown_target(usage) is None


@pytest.mark.parametrize(
    ("resets_in", "expected"),
    [
        (None, "reset time unknown"),
        (0, "resetting now"),
        (59 * 60, "resets in 59m"),
        (2 * 3600 + 5 * 60, "resets in 2h 05m"),
        (3 * 86400 + 4 * 3600, "resets in 3d 4h"),
    ],
)
def test_format_reset(resets_in, expected):
    resets_at = None if resets_in is None else T + resets_in
    assert usage_view.format_reset(resets_at, T) == expected


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [(0, "0m"), (58, "58m"), (118, "1h 58m"), (3 * 1440 + 65, "3d 1h 5m")],
)
def test_format_countdown(minutes, expected):
    assert usage_view.format_countdown(minutes) == expected


def test_elapsed_fraction():
    assert usage_view.elapsed_fraction(None, 3600, T) is None
    assert usage_view.elapsed_fraction(T + 3600, 4 * 3600, T) == pytest.approx(0.75)
    assert usage_view.elapsed_fraction(T + 8 * 3600, 4 * 3600, T) == 0.0


def pixel_at_bar(image):
    """Color near the left end of the session bar."""
    return image.getpixel((usage_view.BAR_X + 4, usage_view.BLOCK1_Y + 24 + usage_view.BAR_H // 2))


def ring_pixel(image):
    """Color at the 12 o'clock position of the ring."""
    return image.getpixel((usage_view.RING_CX, usage_view.RING_CY - usage_view.RING_R_OUT + 4))


def test_render_size():
    image = usage_view.render(ViewState(None, True, "Loading..."), NOW)
    assert image.size == (usage_view.WIDTH, usage_view.HEIGHT)


def test_render_bars_below_limits():
    usage = Usage(window(30, 3600), window(10, 86400))
    image = usage_view.render(ViewState(usage, False, "Updated 12:00"), NOW)
    assert pixel_at_bar(image) == usage_view.COLOR_OK
    assert ring_pixel(image) != usage_view.COLOR_RING


def test_render_bars_dimmed_when_stale():
    usage = Usage(window(30, 3600), window(10, 86400))
    image = usage_view.render(ViewState(usage, True, "HTTP 500", True), NOW)
    assert pixel_at_bar(image) == usage_view.COLOR_DIM


def test_render_countdown_at_limit():
    usage = Usage(window(100, 3600), window(10, 86400))
    image = usage_view.render(ViewState(usage, False, "Updated 12:00"), NOW)
    assert ring_pixel(image) == usage_view.COLOR_RING


def test_render_countdown_dimmed_when_stale():
    usage = Usage(window(100, 3600), window(10, 86400))
    image = usage_view.render(ViewState(usage, True, "HTTP 500", True), NOW)
    assert ring_pixel(image) == usage_view.COLOR_DIM
