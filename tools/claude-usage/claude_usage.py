"""Render the Claude usage screen and send it to m5-view periodically."""

from __future__ import annotations

import argparse
import asyncio
import io
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from m5view_sender.transfer import M5ViewClient, TransferError

import usage_api
import usage_view

BACKOFF_MIN_SEC = 30
BACKOFF_MAX_SEC = 600
RECONNECT_INTERVAL_SEC = 30
# Slack so that a fetch aligned with the per-minute render is not pushed to
# the next minute by a slight wake-up delay
FETCH_TOLERANCE_SEC = 1.0

logger = logging.getLogger("claude_usage")


def next_backoff(current: int) -> int:
    """Retry interval after failures. Doubles from 30 s up to 10 min."""
    return BACKOFF_MIN_SEC if current == 0 else min(current * 2, BACKOFF_MAX_SEC)


def next_minute(now: float) -> float:
    return (int(now) // 60 + 1) * 60


def encode_png(state: usage_view.ViewState, now: datetime) -> bytes:
    buffer = io.BytesIO()
    usage_view.render(state, now).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


class UsageFeed:
    """Track usage fetching and the screen state."""

    def __init__(self, agent: str, interval: int) -> None:
        self._agent = agent
        self._interval = interval
        self._backoff = 0
        self.next_fetch = 0.0
        self.state = usage_view.ViewState(usage=None, stale=True, status="Loading...")

    def fetch_due(self, now: float) -> bool:
        return now >= self.next_fetch - FETCH_TOLERANCE_SEC

    async def fetch(self) -> None:
        started = time.time()
        usage = self.state.usage
        try:
            usage = await asyncio.to_thread(usage_api.fetch_usage, self._agent)
        except usage_api.TokenExpiredError as e:
            self._backoff = 0
            self.next_fetch = started + self._interval
            self.state = usage_view.ViewState(usage, stale=True, status=str(e), status_is_error=True)
            logger.error("%s", e)
            return
        except usage_api.UsageError as e:
            self._backoff = next_backoff(self._backoff)
            self.next_fetch = started + self._backoff
            status = f"{e} - retry in {self._backoff}s"
            self.state = usage_view.ViewState(usage, stale=True, status=status, status_is_error=True)
            logger.error("%s", status)
            return

        self._backoff = 0
        self.next_fetch = started + self._interval
        stamp = datetime.now().strftime("%H:%M")
        self.state = usage_view.ViewState(usage, stale=False, status=f"Updated {stamp}")
        logger.info(
            "usage: session=%s weekly=%s",
            f"{usage.session.utilization:.0f}%" if usage.session else "-",
            f"{usage.weekly.utilization:.0f}%" if usage.weekly else "-",
        )


async def run(args: argparse.Namespace) -> int:
    feed = UsageFeed(usage_api.user_agent(), args.interval)
    client = M5ViewClient(args.name, args.address)
    last_sent: bytes | None = None
    next_connect = 0.0

    try:
        while True:
            now = time.time()
            if feed.fetch_due(now):
                await feed.fetch()

            png = encode_png(feed.state, datetime.now())
            if args.save:
                args.save.write_bytes(png)

            if not client.is_connected:
                # A restarted m5-view has lost its image, so resend on connect
                last_sent = None
                if time.time() >= next_connect:
                    try:
                        await client.connect()
                        logger.info("connected to %s", client.device_name)
                    except TransferError as e:
                        logger.warning("connect failed: %s", e)
                        if args.once:
                            return 1
                        next_connect = time.time() + RECONNECT_INTERVAL_SEC

            if client.is_connected and png != last_sent:
                try:
                    await client.send(png)
                    last_sent = png
                    logger.info("sent %d bytes", len(png))
                except TransferError as e:
                    logger.warning("send failed: %s", e)
                    if args.once:
                        return 1

            if args.once:
                return 0

            now = time.time()
            wake = min(next_minute(now), feed.next_fetch)
            if not client.is_connected:
                wake = min(wake, max(next_connect, now + 1))
            await asyncio.sleep(max(wake - now, 0.0))
    finally:
        await client.disconnect()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show Claude usage on m5-view.")
    parser.add_argument("--name", default="M5-View", help="device name prefix (default: %(default)s)")
    parser.add_argument("--address", help="device address (CoreBluetooth UUID on macOS)")
    parser.add_argument("--interval", type=int, default=60, help="seconds between usage fetches (default: %(default)s)")
    parser.add_argument("--once", action="store_true", help="fetch, send once and exit")
    parser.add_argument("--save", type=Path, metavar="PATH", help="also write the rendered PNG to PATH")
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error("--interval must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
