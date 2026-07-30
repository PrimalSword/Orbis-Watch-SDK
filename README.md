# Orbis Watch SDK

Independent Python SDK and BLE protocol implementation for HryFine-compatible smartwatches.

## Current status

The implementation supports:

- BLE connection over Nordic UART Service
- HryFine packet building and checksum validation
- Fragment reassembly
- ACK recognition
- Device information query
- Standard GATT reads for battery and firmware metadata
- Raw TX/RX traffic capture and replay
- Safe command discovery
- Offline Android BTSnoop ATT extraction
- Static firmware/transfer-stream triage

The protocol was validated against a G28 watch running firmware `V1.5` with project identifier:

```text
E06B_G28_WE[G28]_RStyle1_240x240_HryFine
```

## Installation

```bash
python -m pip install -e .
```

## SDK example

```python
import asyncio
from orbis_watch import Watch


async def main() -> None:
    async with Watch("41:42:99:10:58:57") as watch:
        info = await watch.get_device_info()
        print(info)


asyncio.run(main())
```

## Firmware acquisition tools

Extract ATT writes and notifications from an Android Bluetooth HCI snoop log:

```bash
orbis-firmware btsnoop btsnoop_hci.log --output g28_att.jsonl
```

Export one selected ATT write stream after identifying its handle:

```bash
orbis-firmware btsnoop btsnoop_hci.log \
  --handle 0x0012 \
  --direction TX \
  --output g28_upload.jsonl \
  --stream g28_upload_transport.bin
```

Run static triage on a candidate binary or transport stream:

```bash
orbis-firmware triage g28_upload_transport.bin \
  --json g28_firmware_report.json \
  --markdown g28_firmware_report.md
```

The exported stream is not assumed to be flashable firmware. See [`docs/FIRMWARE_WORKFLOW.md`](docs/FIRMWARE_WORKFLOW.md) for the read-only capture and evidence workflow.

## Scope

This project is an independent implementation and is not affiliated with HryFine or the watch manufacturer.

## License

MIT
