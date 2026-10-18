import struct
import zlib

import pytest

from m5view_sender import protocol


def test_build_header():
    data = b"\x89PNG" + bytes(range(256)) * 10
    header = protocol.build_header(data)
    assert len(header) == protocol.HEADER_SIZE
    assert header[:4] == b"IMG0"
    assert struct.unpack("<I", header[4:8])[0] == len(data)
    assert struct.unpack("<I", header[8:12])[0] == zlib.crc32(data)


def test_build_header_known_crc():
    # CRC-32 (IEEE) check value
    header = protocol.build_header(b"123456789")
    assert header == b"IMG0" + bytes([9, 0, 0, 0]) + bytes([0x26, 0x39, 0xF4, 0xCB])


def test_build_header_rejects_empty():
    with pytest.raises(ValueError):
        protocol.build_header(b"")


def test_build_header_rejects_too_large():
    protocol.build_header(bytes(protocol.MAX_LENGTH))
    with pytest.raises(ValueError):
        protocol.build_header(bytes(protocol.MAX_LENGTH + 1))


def test_iter_chunks():
    data = bytes(range(250))
    chunks = list(protocol.iter_chunks(data, 100))
    assert [len(c) for c in chunks] == [100, 100, 50]
    assert b"".join(chunks) == data


def test_iter_chunks_rejects_invalid_size():
    with pytest.raises(ValueError):
        list(protocol.iter_chunks(b"abc", 0))


def test_iter_windows():
    assert list(protocol.iter_windows(10000)) == [(0, 4096), (4096, 8192), (8192, 10000)]
    assert list(protocol.iter_windows(8192)) == [(0, 4096), (4096, 8192)]
    assert list(protocol.iter_windows(1)) == [(0, 1)]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"OK\n", protocol.Ok()),
        (b"ACK 4096\n", protocol.Ack(4096)),
        (b"ERR crc\n", protocol.Error("crc")),
        (b"ERR bad_header", protocol.Error("bad_header")),
    ],
)
def test_parse_notification(payload, expected):
    assert protocol.parse_notification(payload) == expected


@pytest.mark.parametrize("payload", [b"", b"HELLO\n", b"ACK abc\n"])
def test_parse_notification_rejects_invalid(payload):
    with pytest.raises(ValueError):
        protocol.parse_notification(payload)


def test_build_header_with_max_length():
    protocol.build_header(bytes(protocol.MAX_LENGTH + 1), max_length=protocol.MAX_LENGTH + 1)
    with pytest.raises(ValueError):
        protocol.build_header(bytes(11), max_length=10)


def test_parse_info():
    info = protocol.parse_info(b"width=1280 height=720 max_length=4194304")
    assert info == protocol.DeviceInfo(1280, 720, 4194304)


def test_parse_info_ignores_unknown_items():
    info = protocol.parse_info(b"width=320 height=240 max_length=524288 extra=1")
    assert info == protocol.DEFAULT_INFO


@pytest.mark.parametrize(
    "payload",
    [b"", b"width=320 height=240", b"width=320 height=240 max_length", b"width=a height=240 max_length=1",
     b"width=0 height=240 max_length=1"],
)
def test_parse_info_rejects_invalid(payload):
    with pytest.raises(ValueError):
        protocol.parse_info(payload)
