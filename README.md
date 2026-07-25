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

Start the console:

```bash
orbis-watch 41:42:99:10:58:57
```

## v0.3 console

The development console includes:

- device information, battery and feature bitmap reads;
- nearby BLE scan;
- GATT service and characteristic inspection;
- arbitrary GATT reads;
- protected arbitrary GATT writes;
- exact raw NUS frames;
- safe packet builder;
- live traffic listening and hexadecimal dump;
- JSONL capture, replay and command history;
- command-range discovery with CSV output;
- capture analysis, normalized CSV export and Markdown report generation;
- latency benchmark.

Use `help` inside the console for the exact syntax.

## Safety model

Safe mode is always enabled by default.

Known mutating command IDs are blocked during ordinary raw sends, packet sends, discovery and replay:

- `0x01`: OTA / firmware transfer
- `0x02`: device settings
- `0x0F`: watchface transfer

Operations that can alter the device require `--unsafe` and an exact `YES` confirmation. The SDK does not expose guessed high-level methods such as factory reset, shutdown, OTA or watchface upload until their protocol payloads are validated on hardware.

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
