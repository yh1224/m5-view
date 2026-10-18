"""Render Claude usage to a 320x240 image with the m5-claude-usage layout.

Shows two bars for 5h and 7d, and switches to a countdown to the reset once
either window reaches its limit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from usage_api import Usage, UsageWindow

WIDTH = 320
HEIGHT = 240

HEADER_H = 34
STATUS_Y = HEIGHT - 22

BAR_X = 16
BAR_W = WIDTH - BAR_X * 2
BAR_H = 26

# Top of each block's label line. The bar sits below it
BLOCK1_Y = HEADER_H + 12
BLOCK2_Y = BLOCK1_Y + 84

# Countdown: remaining-time ring on the left, numbers and labels on the right
RING_CX = 78
RING_CY = 126
RING_R_OUT = 58
RING_R_IN = 43
CD_COL_X = 152
CD_COL_W = WIDTH - CD_COL_X - BAR_X
CD_COL_CX = CD_COL_X + CD_COL_W // 2
CD_TITLE_Y = 84
CD_TIME_Y = CD_TITLE_Y + 22
CD_TIME_H = 42
CD_SUB_Y = CD_TIME_Y + CD_TIME_H
# Angles run clockwise from 3 o'clock. The countdown starts at 12 o'clock
RING_START_DEG = -90.0

# The API returns only the reset time, so the elapsed fraction needs the
# window length
SESSION_WINDOW_SEC = 5 * 3600
WEEKLY_WINDOW_SEC = 7 * 86400

MARKER_W = 2

FONT_PATH = "/System/Library/Fonts/Helvetica.ttc"
FONT_INDEX_REGULAR = 0
FONT_INDEX_BOLD = 1
# Sizes matching M5GFX FreeSans 9pt / 12pt / 18pt
SIZE_SMALL = 18
SIZE_MEDIUM = 24
SIZE_LARGE = 35


def rgb565(value: int) -> tuple[int, int, int]:
    r = (value >> 11) & 0x1F
    g = (value >> 5) & 0x3F
    b = value & 0x1F
    return (r * 255 // 31, g * 255 // 63, b * 255 // 31)


# Same colors as m5-claude-usage (RGB565)
COLOR_BG = rgb565(0x0000)
COLOR_FG = rgb565(0xFFFF)
COLOR_DIM = rgb565(0x8410)
COLOR_TRACK = rgb565(0x2124)
COLOR_ACCENT = rgb565(0xFD00)
COLOR_RING = rgb565(0x34DF)
COLOR_OK = rgb565(0x07E0)
COLOR_WARN = rgb565(0xFFE0)
COLOR_HIGH = rgb565(0xFC00)
COLOR_CRIT = rgb565(0xF800)
COLOR_ERROR = rgb565(0xF800)


@dataclass(frozen=True)
class ViewState:
    usage: Usage | None  # None until the first successful fetch
    stale: bool  # The last fetch failed and the values are old
    status: str
    status_is_error: bool = False


@dataclass(frozen=True)
class Countdown:
    label: str
    title: str
    resets_at: float
    window_sec: int
    limited: bool  # The window has reached its limit


@lru_cache(maxsize=None)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    index = FONT_INDEX_BOLD if bold else FONT_INDEX_REGULAR
    return ImageFont.truetype(FONT_PATH, size, index=index)


def countdown_target(usage: Usage) -> Countdown | None:
    """Choose the window to count down.

    Among limited windows, the one that resets last (work can resume only
    after the last reset). Otherwise the one that resets first. Windows with
    an unknown reset time are skipped.
    """
    candidates = [
        (usage.session, "5h", "Session (5h)", SESSION_WINDOW_SEC),
        (usage.weekly, "7d", "Weekly (7d)", WEEKLY_WINDOW_SEC),
    ]
    best: Countdown | None = None
    for window, label, title, window_sec in candidates:
        if window is None or window.resets_at is None:
            continue
        limited = window.utilization >= 100.0
        # A limited window wins over an unlimited one that resets earlier
        better = (
            best is None
            or (limited and not best.limited)
            or (
                limited == best.limited
                and (window.resets_at > best.resets_at if limited else window.resets_at < best.resets_at)
            )
        )
        if better:
            best = Countdown(label, "Limit reached" if limited else title, window.resets_at, window_sec, limited)
    return best


def bar_color(percent: float) -> tuple[int, int, int]:
    if percent >= 90.0:
        return COLOR_CRIT
    if percent >= 75.0:
        return COLOR_HIGH
    if percent >= 50.0:
        return COLOR_WARN
    return COLOR_OK


def elapsed_fraction(resets_at: float | None, window_sec: int, now: float) -> float | None:
    """Elapsed fraction (0.0-1.0) of the window, derived from its reset time."""
    if resets_at is None or window_sec <= 0:
        return None
    remain = resets_at - now
    return min(max((window_sec - remain) / window_sec, 0.0), 1.0)


def format_reset(resets_at: float | None, now: float) -> str:
    """Format the time until reset as "resets in 1h 05m"."""
    if resets_at is None:
        return "reset time unknown"
    remain = int(resets_at - now)
    if remain <= 0:
        return "resetting now"
    days, rest = divmod(remain, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days > 0:
        return f"resets in {days}d {hours}h"
    if hours > 0:
        return f"resets in {hours}h {minutes:02d}m"
    return f"resets in {minutes}m"


def format_countdown(remain_min: int) -> str:
    """Format the countdown as "1h 58m"."""
    days, rest = divmod(remain_min, 1440)
    hours, minutes = divmod(rest, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def render(state: ViewState, now: datetime) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), COLOR_BG)
    draw = ImageDraw.Draw(image)
    timestamp = now.timestamp()

    draw.text((BAR_X, 8), "Claude Usage", font=font(SIZE_MEDIUM, bold=True), fill=COLOR_ACCENT, anchor="la")
    draw.line([(0, HEADER_H - 2), (WIDTH - 1, HEADER_H - 2)], fill=COLOR_TRACK)
    draw.text((WIDTH - BAR_X, 12), now.strftime("%H:%M"), font=font(SIZE_SMALL), fill=COLOR_DIM, anchor="ra")

    if state.usage is not None:
        target = countdown_target(state.usage)
        if target is not None and target.limited:
            _draw_countdown(draw, target, state.stale, timestamp)
        else:
            _draw_bar(draw, BLOCK1_Y, "Session (5h)", state.usage.session, SESSION_WINDOW_SEC, state.stale, timestamp)
            _draw_bar(draw, BLOCK2_Y, "Weekly (7d)", state.usage.weekly, WEEKLY_WINDOW_SEC, state.stale, timestamp)

    draw.text(
        (BAR_X, STATUS_Y),
        state.status,
        font=font(SIZE_SMALL),
        fill=COLOR_ERROR if state.status_is_error else COLOR_DIM,
        anchor="la",
    )
    return image


def _draw_bar(
    draw: ImageDraw.ImageDraw,
    y: int,
    label: str,
    window: UsageWindow | None,
    window_sec: int,
    stale: bool,
    now: float,
) -> None:
    percent = window.utilization if window else 0.0
    color = COLOR_DIM if stale or window is None else bar_color(percent)

    draw.text((BAR_X, y), label, font=font(SIZE_SMALL), fill=COLOR_DIM if stale else COLOR_FG, anchor="la")
    value = f"{percent:.0f}%" if window else "--"
    draw.text((BAR_X + BAR_W, y - 4), value, font=font(SIZE_MEDIUM, bold=True), fill=color, anchor="ra")

    bar_y = y + 24
    draw.rounded_rectangle([BAR_X, bar_y, BAR_X + BAR_W - 1, bar_y + BAR_H - 1], radius=4, fill=COLOR_TRACK)
    fill = int(BAR_W * min(percent, 100.0) / 100.0 + 0.5) if window else 0
    if fill > 0:
        draw.rounded_rectangle([BAR_X, bar_y, BAR_X + max(fill, 8) - 1, bar_y + BAR_H - 1], radius=4, fill=color)

    # Where the fill would be if usage kept pace with time. A fill past the
    # marker means usage is outpacing the window. The marker comes from the
    # local clock, so it stays bright even when the values are stale
    elapsed = elapsed_fraction(window.resets_at, window_sec, now) if window else None
    if elapsed is not None:
        marker_x = BAR_X + int((BAR_W - MARKER_W) * elapsed + 0.5)
        draw.rectangle([marker_x, bar_y + 2, marker_x + MARKER_W - 1, bar_y + BAR_H - 3], fill=COLOR_FG)

    draw.rounded_rectangle([BAR_X, bar_y, BAR_X + BAR_W - 1, bar_y + BAR_H - 1], radius=4, outline=COLOR_TRACK)

    reset = format_reset(window.resets_at, now) if window else "no data"
    draw.text((BAR_X, bar_y + BAR_H + 4), reset, font=font(SIZE_SMALL), fill=COLOR_DIM, anchor="la")


def _draw_countdown(draw: ImageDraw.ImageDraw, target: Countdown, stale: bool, now: float) -> None:
    remain = max(target.resets_at - now, 0.0)
    # Round up so that 0m appears only once the window has actually reset
    remain_min = math.ceil(remain / 60)

    draw.text(
        (CD_COL_CX, CD_TITLE_Y),
        target.title,
        font=font(SIZE_SMALL),
        fill=COLOR_CRIT if target.limited else COLOR_DIM,
        anchor="ma",
    )
    draw.text((CD_COL_CX, CD_SUB_Y), "until reset", font=font(SIZE_SMALL), fill=COLOR_DIM, anchor="ma")

    # The ring shrinks clockwise from 12 o'clock with the remaining time
    left = min(remain / target.window_sec, 1.0) if target.window_sec > 0 else 0.0
    ring_color = COLOR_DIM if stale else COLOR_RING
    box = [RING_CX - RING_R_OUT, RING_CY - RING_R_OUT, RING_CX + RING_R_OUT, RING_CY + RING_R_OUT]
    width = RING_R_OUT - RING_R_IN
    draw.arc(box, 0, 360, fill=COLOR_TRACK, width=width)
    if left > 0.0:
        draw.arc(box, RING_START_DEG, RING_START_DEG + 360.0 * left, fill=ring_color, width=width)
    draw.text((RING_CX, RING_CY), target.label, font=font(SIZE_MEDIUM, bold=True), fill=ring_color, anchor="mm")

    text = format_countdown(remain_min)
    # A 7d countdown with days left does not fit the column in the large font
    time_font = font(SIZE_LARGE, bold=True)
    if draw.textlength(text, font=time_font) > CD_COL_W:
        time_font = font(SIZE_MEDIUM, bold=True)
    draw.text((CD_COL_CX, CD_TIME_Y + CD_TIME_H // 2), text, font=time_font, fill=COLOR_FG, anchor="mm")
