"""CLI that sends an image file to m5-view."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from PIL import ImageColor

from m5view_sender import imageprep, protocol
from m5view_sender.transfer import M5ViewClient, TransferError


def print_progress(sent: int, total: int) -> None:
    percent = sent * 100 // total
    print(f"\rSending {percent:3d}% ({sent}/{total} bytes)", end="", file=sys.stderr, flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send an image to m5-view over BLE.")
    parser.add_argument("image", type=Path, help="image file to send")
    parser.add_argument("--name", default="M5-View", help="device name prefix (default: %(default)s)")
    parser.add_argument("--address", help="device address (CoreBluetooth UUID on macOS)")
    parser.add_argument("--fit", choices=imageprep.FIT_MODES, default="contain", help="fit mode (default: %(default)s)")
    parser.add_argument("--bg", default="#000000", help="background color for contain (default: %(default)s)")
    args = parser.parse_args(argv)
    try:
        ImageColor.getrgb(args.bg)
    except ValueError:
        parser.error(f"invalid color: {args.bg}")
    return args


async def main_async(args: argparse.Namespace) -> None:
    png = imageprep.prepare(args.image, args.fit, args.bg)
    if len(png) > protocol.MAX_LENGTH:
        raise TransferError(f"PNG is too large: {len(png)} > {protocol.MAX_LENGTH} bytes")
    print(f"Prepared PNG: {len(png)} bytes", file=sys.stderr)

    client = M5ViewClient(args.name, args.address)
    await client.connect()
    try:
        print(f"Connected to {client.device_name}", file=sys.stderr)
        await client.send(png, print_progress)
        print("\nDone", file=sys.stderr)
    finally:
        await client.disconnect()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        asyncio.run(main_async(args))
    except (TransferError, OSError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    return 0
