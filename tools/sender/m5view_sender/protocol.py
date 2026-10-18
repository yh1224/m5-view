"""Messages of the m5-view image transfer protocol (docs/protocol.md)."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Iterator

NUS_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
NUS_RX_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
NUS_TX_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

MAGIC = b"IMG0"
HEADER_SIZE = 12
MAX_LENGTH = 512 * 1024
ACK_WINDOW = 4096


def build_header(data: bytes) -> bytes:
    """Build the header (magic + length + CRC32) for the body data."""
    if not data:
        raise ValueError("data must not be empty")
    if len(data) > MAX_LENGTH:
        raise ValueError(f"data is too large: {len(data)} > {MAX_LENGTH}")
    return MAGIC + struct.pack("<II", len(data), zlib.crc32(data))


def iter_chunks(data: bytes, chunk_size: int) -> Iterator[bytes]:
    """Split data into chunks of at most chunk_size bytes."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    for offset in range(0, len(data), chunk_size):
        yield data[offset : offset + chunk_size]


def iter_windows(length: int, window: int = ACK_WINDOW) -> Iterator[tuple[int, int]]:
    """Return the (start, end) offsets of each window that waits for an ACK."""
    for start in range(0, length, window):
        yield start, min(start + window, length)


@dataclass(frozen=True)
class Ack:
    received: int


@dataclass(frozen=True)
class Ok:
    pass


@dataclass(frozen=True)
class Error:
    reason: str


Notification = Ack | Ok | Error


def parse_notification(payload: bytes) -> Notification:
    """Parse a TX notification. Raises ValueError if malformed."""
    text = payload.decode("ascii").strip()
    if text == "OK":
        return Ok()
    if text.startswith("ACK "):
        return Ack(int(text[4:]))
    if text.startswith("ERR "):
        return Error(text[4:])
    raise ValueError(f"unknown notification: {text!r}")
