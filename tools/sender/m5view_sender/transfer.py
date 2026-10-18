"""BLE connection to m5-view and image transfer."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from m5view_sender import protocol

SCAN_TIMEOUT = 10.0
RESPONSE_TIMEOUT = 10.0

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]


class TransferError(Exception):
    pass


async def find_device(name_prefix: str, address: str | None) -> BLEDevice:
    if address:
        device = await BleakScanner.find_device_by_address(address, timeout=SCAN_TIMEOUT)
        if device is None:
            raise TransferError(f"device not found: {address}")
        return device

    def match(device, advertisement) -> bool:
        name = advertisement.local_name or device.name or ""
        return name.startswith(name_prefix)

    device = await BleakScanner.find_device_by_filter(match, timeout=SCAN_TIMEOUT)
    if device is None:
        raise TransferError(f"device not found: {name_prefix}*")
    return device


class M5ViewClient:
    """Client that keeps the connection open and sends any number of images."""

    def __init__(self, name_prefix: str = "M5-View", address: str | None = None) -> None:
        self._name_prefix = name_prefix
        self._address = address
        self._client: BleakClient | None = None
        self._notifications: asyncio.Queue[protocol.Notification] = asyncio.Queue()

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def device_name(self) -> str | None:
        return self._client.name if self._client else None

    async def connect(self) -> None:
        """Find the device, connect and subscribe to notifications."""
        await self.disconnect()
        try:
            device = await find_device(self._name_prefix, self._address)
            client = BleakClient(device)
            await client.connect()
            try:
                await client.start_notify(protocol.NUS_TX_UUID, self._on_notify)
            except BaseException:
                await client.disconnect()
                raise
        except BleakError as e:
            raise TransferError(str(e)) from e
        self._client = client

    async def disconnect(self) -> None:
        client, self._client = self._client, None
        if client is not None and client.is_connected:
            try:
                await client.disconnect()
            except BleakError as e:
                logger.debug("disconnect failed: %s", e)

    async def send(self, png: bytes, progress: ProgressCallback | None = None) -> None:
        """Send one PNG and wait until the device has shown it."""
        if not self.is_connected:
            raise TransferError("not connected")
        try:
            await self._send(png, progress)
        except BleakError as e:
            raise TransferError(str(e)) from e

    async def _send(self, png: bytes, progress: ProgressCallback | None) -> None:
        client = self._client
        assert client is not None
        rx = client.services.get_characteristic(protocol.NUS_RX_UUID)
        if rx is None:
            raise TransferError("NUS RX characteristic not found")
        chunk_size = rx.max_write_without_response_size

        # Drop notifications left from the previous transfer so they are not
        # taken as replies to this one
        while not self._notifications.empty():
            self._notifications.get_nowait()

        await client.write_gatt_char(rx, protocol.build_header(png), response=True)
        self._raise_if_error()

        for start, end in protocol.iter_windows(len(png)):
            for chunk in protocol.iter_chunks(png[start:end], chunk_size):
                await client.write_gatt_char(rx, chunk, response=False)
            self._raise_if_error()
            if progress:
                progress(end, len(png))
            if end == len(png):
                break
            while True:
                notification = await self._wait_notification()
                if isinstance(notification, protocol.Ack) and notification.received >= end:
                    break

        while not isinstance(await self._wait_notification(), protocol.Ok):
            pass

    def _on_notify(self, _sender, payload: bytearray) -> None:
        try:
            self._notifications.put_nowait(protocol.parse_notification(bytes(payload)))
        except ValueError as e:
            logger.warning("ignored notification: %s", e)

    def _raise_if_error(self) -> None:
        """Raise if a received notification is ERR."""
        while not self._notifications.empty():
            notification = self._notifications.get_nowait()
            if isinstance(notification, protocol.Error):
                raise TransferError(f"device returned error: {notification.reason}")

    async def _wait_notification(self) -> protocol.Notification:
        try:
            notification = await asyncio.wait_for(self._notifications.get(), RESPONSE_TIMEOUT)
        except asyncio.TimeoutError:
            raise TransferError("timed out waiting for response") from None
        if isinstance(notification, protocol.Error):
            raise TransferError(f"device returned error: {notification.reason}")
        return notification
