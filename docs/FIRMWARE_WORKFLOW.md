# G28 firmware acquisition workflow

This workflow separates capture, reconstruction, analysis, and writing. Capture and analysis are read-only. Do not send OTA, watchface, flash-read, reset, or factory commands until an original backup and a verified recovery method exist.

## 1. Capture one official transfer

On Android:

1. Enable Developer options.
2. Enable **Bluetooth HCI snoop log**.
3. Restart Bluetooth so logging takes effect.
4. Connect the G28 in HryFine.
5. Perform exactly one official watchface or firmware transfer.
6. Stop logging and generate a bug report with `adb bugreport`.
7. Extract `btsnoop_hci.log`.

Keep the original log unchanged and record the watch battery, HryFine version, firmware/project string, transfer start/end time, selected item, and whether the operation completed.

## 2. Extract ATT traffic

```bash
orbis-firmware btsnoop btsnoop_hci.log --output g28_att.jsonl
```

The command prints traffic totals by ATT handle. After identifying the high-volume write handle, filter it and export a transport stream:

```bash
orbis-firmware btsnoop btsnoop_hci.log \
  --handle 0x0012 \
  --direction TX \
  --output g28_upload.jsonl \
  --stream g28_upload_transport.bin
```

The transport stream is only concatenated ATT values. It is not automatically a firmware image because protocol headers, sequence numbers, checksums, metadata, compression, and control frames may remain.

Known HryFine-style frames can be isolated with:

```bash
orbis-firmware btsnoop btsnoop_hci.log \
  --orbis-only \
  --output g28_orbis_frames.jsonl
```

## 3. Static triage

```bash
orbis-firmware triage g28_upload_transport.bin \
  --json g28_firmware_report.json \
  --markdown g28_firmware_report.md
```

The report calculates SHA-256 and entropy, searches common signatures and printable strings, and applies a conservative ARM Cortex-M vector-table heuristic. Vendor, RTOS, and UI-library strings are hints, not proof of the processor.

## 4. Evidence required before a modification

- original transfer file or deterministic reconstruction;
- exact packet order and acknowledgement behavior;
- checksum, hash, and signature behavior;
- confirmed SoC and flash markings, preferably from PCB photographs;
- identified recovery/debug pads or a documented boot mode;
- verified backup when readout is possible;
- tested restoration procedure.

The first controlled experiment should alter a reversible visual resource, not executable code, boot vectors, partition tables, or the bootloader.
