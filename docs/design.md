# Design

## 1. Overview

A system that connects from macOS to an M5Stack CoreS3 over BLE, transfers a PNG image and shows it on the screen.

- **Firmware**: runs on the CoreS3, receives images over BLE and shows them
- **Sender**: a Python CLI running on macOS that converts images to 320×240 PNG and sends them

```mermaid
flowchart LR
    subgraph mac[macOS]
        img[Image file] --> prep[imageprep<br/>resize, PNG encode]
        prep --> cli[send.py<br/>bleak]
    end
    subgraph m5[M5Stack CoreS3]
        ble[ble_transport<br/>NimBLE / NUS] --> rx[image_receiver<br/>state, CRC]
        rx --> ui[display_ui<br/>drawing, overlays]
    end
    cli -- BLE / NUS --> ble
```

See the [protocol](protocol.md) for the communication details.

## 2. Requirements

### 2.1 Functional requirements

| Item | Description |
| --- | --- |
| Communication | Transfer images over the BLE Nordic UART Service (NUS) |
| Image format | PNG (320×240), decoded on the device |
| Resizing | The sender fits images to 320×240. The default is `contain` (black padding) |
| Display | Show the last image received. The image is kept in memory and a restart clears it |
| Orientation | Fixed landscape (320×240) |
| Idle screen | Show the device name and the BLE connection status |
| During transfer | Overlay a progress bar at the bottom of the screen |
| Errors | Show the error as a toast for a few seconds, then return to the previous image |
| Security | Any Central can connect without pairing |
| Power | The screen stays on at a fixed medium brightness |

### 2.2 Non-functional requirements

| Item | Description |
| --- | --- |
| Image size limit | 512 KiB (PNG byte length) |
| Timeout | Discard a transfer after 5 seconds without data |
| Reliability | Verify the transferred data with CRC32. On failure, the sender resends from the start |

## 3. Hardware

| Item | Value |
| --- | --- |
| Board | M5Stack CoreS3 (ESP32-S3) |
| Bluetooth | BLE 5.0 |
| Display | 320×240, RGB565 |
| PSRAM | 8 MB |

## 4. Firmware design

### 4.1 Development environment

- PlatformIO (`espressif32`) with the Arduino framework
- Libraries
  - `m5stack/M5Unified`: display and device control (uses `drawPng` from M5GFX)
  - `h2zero/NimBLE-Arduino`: BLE stack

### 4.2 Source layout

```
src/
├── main.cpp               # setup() / loop(). Module setup and event handling
├── ble_transport.h/.cpp   # NUS service, advertising, connections, notifications
├── image_receiver.h/.cpp  # Receiver state machine, buffer, CRC32, timeout
└── display_ui.h/.cpp      # Image storage and drawing, idle screen, progress bar, toast
```

### 4.3 Modules

#### ble_transport

- Initializes NimBLE and registers the NUS service (RX / TX)
- Builds the device name `M5-View-XXXX` from the BLE MAC address and advertises it
- Sets the preferred ATT_MTU to 517 (the Central starts the MTU exchange). Allows one connection at a time
- Interface
  - Callback for RX writes (`onReceive(const uint8_t*, size_t)`)
  - Callback for disconnection
  - Connection status (`isConnected()`)
  - Sending TX notifications (`notify(const char*)`)
- Resumes advertising after disconnection

#### image_receiver

Implements the state machine (`IDLE` / `RECEIVING` / `PROCESSING`) in [protocol §4](protocol.md#4-state-transitions-receiver).

- **Header**: validates the magic and length, then allocates a receive buffer of `length` bytes in PSRAM (`ps_malloc`)
- **Body**: copies data into the buffer with `memcpy` in the RX callback and updates the total byte count and the time of the last write. Each time the total reaches or passes a 4096-byte boundary, notifies `ACK <n>` with that boundary
- **Completion**: when the total reaches `length`, moves to `PROCESSING` and hands over to `loop()`
- **CRC32**: computed in `loop()` after reception with a table-driven software implementation (zlib compatible)
- **Timeout**: `loop()` calls `poll()` regularly. If 5 seconds have passed since the last write in `RECEIVING`, notifies `ERR timeout` and discards the transfer
- **Disconnection**: in `RECEIVING`, frees the receive buffer, returns to `IDLE` and shows the toast `Error: disconnected`. In `PROCESSING`, `loop()` is still using the buffer, so `finish()` frees it when processing completes

#### display_ui

- Holds two 320×240 canvases (`M5Canvas`) in PSRAM
  - `current`: the image on screen
  - `staging`: the decode target
- **Image update**: decodes the PNG into `staging`, and on success swaps it with `current` and pushes it to the screen. On failure, keeps `current` and the image on screen
- **Idle screen**: until an image arrives, shows the device name and the connection status (`Advertising` / `Connected`) on a black background
- **Progress bar**: during a transfer, overlays a bar a few pixels tall at the bottom of the screen. Updates redraw the bar area alone
- **Toast**: on errors, shows a message (e.g. `Error: crc`) at the bottom of the screen for about 3 seconds, then redraws `current` (or the idle screen) to clear it
- Brightness is fixed at 128/255 (medium)

### 4.4 Threads and locking

NimBLE callbacks run on the NimBLE host task, and `loop()` runs on the Arduino main task.

| Work | Context |
| --- | --- |
| Header parsing, buffer allocation, `memcpy`, `ACK` notifications | NimBLE host task (RX callback) |
| CRC check, PNG decoding, drawing, `OK` / `ERR` notifications | `loop()` |
| Timeout checks, UI updates (progress, toast, connection status) | `loop()` |

- The state, the total byte count and the buffer pointer live inside `image_receiver`, guarded by a mutex (`std::mutex`)
- The RX callback copies into the buffer and updates the state. CRC calculation, decoding and drawing happen in `loop()`
- `loop()` polls for state changes (progress, completion, errors, connection status) and reflects them in the UI
- RX writes arriving during `PROCESSING` are discarded

### 4.5 Memory

| Use | Size | Location |
| --- | --- | --- |
| Receive buffer | Up to 512 KiB (`length` bytes) | PSRAM, allocated and freed per transfer |
| Canvas × 2 | 150 KiB × 2 | PSRAM, allocated at startup |

### 4.6 Processing flow

```mermaid
sequenceDiagram
    participant BLE as NimBLE task
    participant RX as image_receiver
    participant L as loop()
    participant UI as display_ui
    BLE->>RX: onReceive(header)
    RX->>RX: validate, ps_malloc → RECEIVING
    loop body
        BLE->>RX: onReceive(chunk)
        RX->>RX: memcpy, ACK every 4 KiB
        L->>UI: show progress (progress bar)
    end
    RX->>RX: total = length → PROCESSING
    L->>RX: CRC check
    L->>UI: decode into staging → swap with current → draw
    L->>BLE: notify OK / ERR
    L->>RX: free buffer → IDLE
```

## 5. Sender design

### 5.1 Development environment

- Python (managed with `uv`)
- Dependencies: `bleak` (BLE), `Pillow` (image processing)
- Tests: `pytest`

### 5.2 Source layout

```
tools/sender/
├── pyproject.toml
├── send.py               # CLI launcher
├── m5view_sender/        # Package, also used as a dependency by other tools
│   ├── cli.py            # CLI. Argument parsing and sending
│   ├── transfer.py       # BLE connection and transfer (M5ViewClient)
│   ├── protocol.py       # Header building, chunking, notification parsing
│   └── imageprep.py      # Image loading, fitting, PNG encoding
├── samples/              # Images for trying things out
└── tests/
    ├── test_protocol.py
    └── test_imageprep.py
```

### 5.3 CLI

```
uv run send.py IMAGE [--name PREFIX] [--address ADDRESS]
                     [--fit contain|cover|stretch] [--bg #RRGGBB]
```

| Option | Default | Description |
| --- | --- | --- |
| `IMAGE` | (required) | Image file to send, in any format Pillow can read |
| `--name` | `M5-View` | Find the device by name prefix and connect to the first match |
| `--address` | - | Connect to this device (a CoreBluetooth UUID on macOS). Takes precedence over `--name` |
| `--fit` | `contain` | `contain`: shrink to fit and pad / `cover`: enlarge to fill and crop / `stretch`: stretch ignoring the aspect ratio |
| `--bg` | `#000000` | Padding color for `contain` |

- Exit code: `0` on success, `1` if the device is not found, the connection fails, `ERR` arrives or the transfer times out

### 5.4 Modules

#### imageprep

- Opens the image with Pillow, applies the EXIF orientation and converts it to RGB
- Fits it to 320×240 according to `--fit` (resampling with `LANCZOS`)
- Encodes it as PNG (`optimize=True`) and returns the bytes

#### protocol

- `build_header(data: bytes) -> bytes`: builds `"IMG0"` + `length` + `zlib.crc32`
- `iter_chunks(data, chunk_size)`: splits the body
- `parse_notification(bytes)`: parses `ACK <n>` / `OK` / `ERR <reason>`
- Pure functions independent of BLE, covered by unit tests

#### transfer

`M5ViewClient` keeps the connection open and sends any number of images.

- `connect()`: finds the device with `BleakScanner`, connects with `BleakClient` and subscribes to TX notifications. Incoming notifications go into an `asyncio.Queue`
- `send(png)`: sends one image and waits until the device has shown it
  1. Drops notifications left from the previous transfer
  2. Sends the header
  3. Picks the chunk size from `max_write_without_response_size` and sends with `response=False` within each 4096-byte window, waiting for `ACK` at the end of each window
  4. Succeeds on `OK` and fails on `ERR`. Waiting for a reply times out after 10 seconds
- `disconnect()`: disconnects
- Reports every failure as `TransferError`

#### cli

1. Builds the PNG with `imageprep` (exits with an error before sending if it exceeds 512 KiB)
2. Connects with `M5ViewClient` and sends while showing progress in the terminal
3. Disconnects when finished

## 6. Testing

| Target | Method |
| --- | --- |
| `protocol` | Unit tests with `pytest` (header format, CRC, chunking, notification parsing) |
| `imageprep` | Unit tests with `pytest` (output size, padding color, PNG encoding) |
| Firmware | Manual tests on the device |

Manual test points (using the images in `tools/sender/samples/`):

- Each `--fit` mode shows the image correctly
- Large images (PNG of a few hundred KiB) transfer and show correctly
- If the sender stops mid-transfer, an error appears after the 5-second timeout and the previous image returns
- If the connection drops mid-transfer, the transfer is discarded, an error appears and the previous image returns
- An invalid header or a CRC mismatch returns `ERR` and shows a toast
- The connection status on the idle screen follows disconnected → connected → disconnected
