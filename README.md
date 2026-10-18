# m5-view

Firmware and a sender tool that send images from macOS to an M5Stack CoreS3 over Bluetooth (BLE) and show them on its screen.

- **Firmware**: receives PNG images over the BLE Nordic UART Service (NUS) and shows them on the 320×240 screen
- **Sender**: a Python CLI that converts any image to a 320×240 PNG and sends it from macOS over BLE

## Requirements

- M5Stack CoreS3
- macOS with Bluetooth
- [PlatformIO Core](https://platformio.org/install/cli)
- [uv](https://docs.astral.sh/uv/)

## Installation

### Firmware

Connect the CoreS3 over USB, then build and flash.

```sh
pio run -t upload
```

On startup, the idle screen shows the device name (`M5-View-XXXX`) and the connection status.

### Sender

```sh
cd tools/sender
uv sync
```

On the first run, macOS asks to allow the terminal app to use Bluetooth. Allow it (System Settings > Privacy & Security > Bluetooth).

## Usage

```sh
cd tools/sender
uv run send.py ~/Pictures/photo.jpg
```

The sender connects to a nearby device whose name starts with `M5-View` and sends the image. During the transfer, a progress bar appears at the bottom of the device screen, and the image is shown once the transfer completes.

### Options

| Option | Default | Description |
| --- | --- | --- |
| `--name PREFIX` | `M5-View` | Find the device by name prefix |
| `--address ADDRESS` | - | Connect to this device (a CoreBluetooth UUID on macOS) |
| `--fit MODE` | `contain` | `contain` (fit the whole image) / `cover` (fill the screen and crop) / `stretch` (stretch to fill) |
| `--bg COLOR` | `#000000` | Padding color for `contain` |

Examples:

```sh
uv run send.py photo.jpg --fit cover
uv run send.py logo.png --bg '#FFFFFF' --name M5-View-3FA2
```

### Sample images

`tools/sender/samples/` contains images for trying things out.

| File | Content |
| --- | --- |
| `color-bars.png` | Color bars at the screen size of 320×240 |
| `portrait.jpg` | Portrait (600×1000), for comparing `--fit` modes |
| `landscape.png` | Landscape (1600×400), for comparing `--fit` modes |
| `noise.png` | Nearly incompressible noise, for testing large transfers |

```sh
uv run send.py samples/portrait.jpg --fit cover
```

### Notes

- The device shows the last image sent, and a restart clears it
- Connecting requires no pairing, so anyone nearby can connect and send images
- The converted PNG must be 512 KiB or smaller

## Tests

```sh
cd tools/sender
uv run pytest
```

## Documents

- [Design](docs/design.md)
- [Protocol](docs/protocol.md)

## License

[MIT](LICENSE)
