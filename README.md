# Orbis Watch SDK

Independent Python SDK and BLE protocol implementation for HryFine-compatible smartwatches.

## Current status

The initial implementation supports:

- BLE connection over Nordic UART Service
- HryFine packet building and checksum validation
- Fragment reassembly
- ACK recognition
- Device information query
- Standard GATT reads for battery and firmware metadata

The protocol was validated against a G28 watch running firmware `V1.5` with project identifier:

```text
E06B_G28_WE[G28]_RStyle1_240x240_HryFine
```

## Installation

```bash
python -m pip install -e .
```

## Example

```python
import asyncio
from orbis_watch import Watch


async def main() -> None:
    async with Watch("41:42:99:10:58:57") as watch:
        info = await watch.get_device_info()
        print(info)


asyncio.run(main())
```

## Scope

This project is an independent implementation and is not affiliated with HryFine or the watch manufacturer.

## License

MIT
