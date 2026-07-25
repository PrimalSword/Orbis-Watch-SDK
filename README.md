# Orbis Watch SDK

Independent Python SDK and BLE reverse-engineering toolkit for HryFine-compatible smartwatches.

## Validated device

- Model: G28
- Firmware: `V1.5`
- Project: `E06B_G28_WE[G28]_RStyle1_240x240_HryFine`
- Screen: 240x240
- Transport: Nordic UART Service

## Installation

```bash
git switch v0.3-dev
git pull
python -m pip install -e .
```

## Applications

### Orbis Console

```bash
orbis-watch 41:42:99:10:58:57
```

Interactive BLE console with device information, battery and feature reads, GATT inspection, protected raw traffic, capture, replay, discovery, export, reports and benchmarks.

### Orbis Watch Studio

```bash
orbis-watch-studio 41:42:99:10:58:57
```

Tkinter desktop interface with connection controls, safe protocol requests, GATT tree, console output, capture analysis and Markdown report generation. Studio intentionally has no unsafe mode.

### Orbis Watch Lab

Analyze a capture:

```bash
orbis-watch-lab analyze captura_g28.jsonl --report relatorio_detalhado.md
```

Safely crawl command and subcommand ranges:

```bash
orbis-watch-lab crawl 41:42:99:10:58:57 0x18 0x1A --sub-start 0 --sub-end 3 --output crawl.csv
```

The crawler skips known mutating command IDs unless `--unsafe` is explicitly supplied.

### Orbis G28 Emulator

```bash
orbis-watch-emulator --host 127.0.0.1 --port 8787
```

This starts a transport-neutral TCP protocol twin for parser and client development. Send one hexadecimal HryFine request per line. The emulator reproduces the validated G28 `DEVICE_INFO` data-plus-ACK ordering and known ACK behavior. It does not advertise itself as a BLE peripheral.

## Safety model

Safe mode is enabled by default. Known mutating command IDs are blocked during ordinary raw sends, packet sends, discovery, crawling and replay:

- `0x01`: OTA / firmware transfer
- `0x02`: device settings
- `0x0F`: watchface transfer

Operations that can alter the device require `--unsafe` and an exact confirmation where supported. Guessed high-level methods such as factory reset, shutdown, OTA and watchface upload remain deliberately absent until their payloads are validated on hardware.

## Python example

```python
import asyncio
from orbis_watch import Watch


async def main() -> None:
    async with Watch("41:42:99:10:58:57") as watch:
        print(await watch.get_device_info())
        print(await watch.get_battery_level())
        print(await watch.get_features())


asyncio.run(main())
```

## Scope

This project is an independent implementation and is not affiliated with HryFine or the watch manufacturer.

## License

MIT
