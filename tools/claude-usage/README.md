# Claude Usage display tool

A resident macOS tool that renders Claude subscription usage (the 5-hour and 7-day windows) with the same layout as m5-claude-usage and sends it to m5-view every minute.

It fetches usage with the Claude Code login on this Mac.

## Requirements

- M5Stack CoreS3 or Tab5 flashed with the m5-view firmware (the 320×240 image is enlarged to fit the Tab5 screen)
- macOS with Bluetooth
- [uv](https://docs.astral.sh/uv/)
- Claude Code, logged in on this Mac

## Installation

```sh
cd tools/claude-usage
uv sync
```

## Usage

```sh
uv run claude_usage.py
```

While running, the tool fetches usage every minute, updates the screen and sends it to the device. It reconnects automatically if the connection drops. Press Ctrl+C to quit.

On the first run, macOS asks to let the `security` command access `Claude Code-credentials` in the keychain. Choose "Always Allow". If macOS asks to allow the terminal app to use Bluetooth, allow that too.

### Options

| Option | Default | Description |
| --- | --- | --- |
| `--name PREFIX` | `M5-View` | Find the device by name prefix |
| `--address ADDRESS` | - | Connect to this device (a CoreBluetooth UUID on macOS) |
| `--interval SEC` | `60` | Seconds between usage fetches |
| `--once` | - | Fetch and send once, then exit |
| `--save PATH` | - | Also write the rendered image to a file |

Example:

```sh
uv run claude_usage.py --once --save usage.png
```

### Screen

- Normally shows the usage of the 5-hour and 7-day windows as bars. The vertical line in each bar marks how much of the window has elapsed
- The bar color follows the pace, usage over the elapsed share: green below 0.75, yellow up to 1.0, orange below 1.25, red from there or at 100%. The pace is taken against a marker of at least 20%, so a fresh window does not turn red at the first message. When the reset time is unknown, the color follows usage alone (yellow from 50%, orange from 75%, red from 90%)
- When either window reaches its limit, the screen switches to a countdown to the reset
- While fetching fails, the last values are shown in gray and the status line shows the error

### Access token expiry

The Claude Code access token expires after a while, and using Claude Code refreshes it. While it is expired, the status line shows `token expired - run Claude Code`.

## Tests

```sh
uv run pytest
```

## Documents

- [Design](docs/design.md)
