# OMirror

[![CI](https://github.com/omar-hindawi98/omirror/actions/workflows/ci.yml/badge.svg)](https://github.com/omar-hindawi98/omirror/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-117%20passing-brightgreen)](tests/)

A Raspberry Pi smart mirror with a pygame GUI, Bluetooth LE configuration, RGB LED control, and an iOS companion app.

## Features

- **Weather** — current conditions and multi-day forecast via OpenWeatherMap
- **News** — configurable RSS feed with relative timestamps
- **Activities** — upcoming calendar-style events with countdown timers
- **Time-based overlay text** — show custom messages during specific time windows
- **Name & quote display** — personalised welcome messages and rotating quotes
- **RGB LEDs** — single colour, flash sequences, and fade modes via pigpio PWM
- **Auto-sleep** — blanks the display between configurable hours
- **Bluetooth LE** — configure everything from the companion iOS app over GATT
- **4-rotation layout** — portrait and landscape support for any mirror orientation

## Hardware

| Component | Details |
|-----------|---------|
| Board | Raspberry Pi 3 B+ or later |
| Display | HDMI monitor / official touchscreen |
| LEDs | Common-anode RGB LED wired to GPIO pins via pigpio |
| Button | Two GPIO momentary buttons (display toggle + rotation) |

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for dependency management

Pi-only extras (`RPi.GPIO`, `pigpio`, `dbus-python`) are in the `[pi]` optional group and are not installed on non-Pi machines.

## Installation

```bash
# Clone and enter the repo
git clone https://github.com/omar-hindawi98/omirror.git
cd omirror

# Install (add --extra pi on Raspberry Pi)
uv sync
# uv sync --extra pi   # on Raspberry Pi

# Copy and edit settings
cp settings.json settings.local.json   # optional — settings.json works directly
```

Edit `settings.json` with your OpenWeatherMap API key, city name, and preferences.

## Configuration

All settings live in `settings.json` at the repo root:

| Key | Type | Description |
|-----|------|-------------|
| `name` | string | Display name shown on the mirror |
| `weather_city` | string | City name for weather (e.g. `"London"`) |
| `weather_api` | string | OpenWeatherMap API key |
| `rotation` | 0–3 | Layout rotation (0 = default portrait) |
| `pota_delay` | int | Seconds to show the name card |
| `quote_delay` | int | Seconds to show the quote card |
| `autosleep` | 0/1 | Enable auto-sleep |
| `autosleep_time` | `"HH:MM,HH:MM"` | Sleep window start and end |
| `rgb_mode` | 0–2 | LED mode: 0 off, 1 single, 2 flash |
| `rgb_single` | `"R,G,B"` | Static LED colour |
| `rgb_flash_sequence` | `"R,G,B:R,G,B:…"` | Flash colour sequence |
| `rgb_flash_delay` | int (ms) | Delay between flash steps |
| `rgb_fade_delay` | int | Fade speed |
| `news_rss` | URL | RSS feed URL |
| `news_max` | int | Maximum news items to display |

## Running

```bash
# Development (any machine — GPIO/Bluetooth silently no-ops)
uv run omirror

# Production (Raspberry Pi, requires pigpio daemon)
sudo pigpiod
uv run omirror

# Bluetooth GATT server (separate process, Pi only)
uv run omirror-bt
```

## Project layout

```
OMirror/
├── src/omirror/
│   ├── app.py                  # Main loop and background threads
│   ├── config.py               # JSON settings read/write
│   ├── const.py                # Path constants
│   ├── assets/                 # Fonts and images (package data)
│   ├── bluetooth/              # BLE GATT server
│   ├── display/
│   │   ├── renderer.py         # BoxContainer, Fader, text_surface
│   │   ├── centered_text.py    # Time-range overlay data
│   │   └── widgets/            # One widget class per file
│   ├── hardware/
│   │   ├── rgb.py              # GPIO/pigpio LED control
│   │   └── wifi.py             # Wi-Fi provisioning helper
│   └── widgets/                # Data-fetching modules (no pygame)
├── settings.json               # Default configuration (edit in place)
├── pyproject.toml
└── uv.lock
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for a full module map, data-flow diagram, and breadboard wiring diagram.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © Omar Hindawi
