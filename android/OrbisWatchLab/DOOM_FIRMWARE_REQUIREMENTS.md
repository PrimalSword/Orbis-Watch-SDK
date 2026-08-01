# G28 DOOM firmware — preservation requirements

The DOOM experiment must remain a smartwatch firmware, not a one-way demo image.

## Mandatory invariants

1. **Clock and RTC remain functional.** The watch must show the time outside the game and retain or resynchronize time after reset.
2. **BLE maintenance remains available.** A documented service must allow identification, health checks and a future OTA/recovery transition.
3. **DOOM has an exit path.** A button, touch gesture or timeout must return to the watch UI without reflashing.
4. **Recovery remains possible.** The known normal and XOR55 bootloader addresses and the 18A8/2AA8/2AA9 transport must not be intentionally removed.
5. **No blind partition writes.** Command `0x03` and firmware data remain disabled until a genuine manifest or independently validated memory map exists.
6. **Preserve a baseline.** Before any firmware experiment, capture the normal-mode GATT layout and readable characteristics and save the recovery passport.

## Confirmed device identity

- Project: G28
- Current firmware: V1.5
- Boot protocol: V1.1
- Unique code: `6800A4B00456312E3503473238`
- Normal BLE transport: Nordic UART Service 6E400001/2/3
- Bootloader transport: 18A8, RX 2AA8, TX 2AA9
- Normal/boot address relation: final byte XOR `0x55`

## Normal-mode GATT baseline captured on 2026-08-01

- Battery service `180F`, level characteristic `2A19`: `0x64` (100%).
- Device Information service `180A`:
  - serial `2A25`: `10000004`;
  - hardware revision `2A27`: `10000`;
  - firmware revision `2A26`: `10000`;
  - software revision `2A28`: 26-byte binary structure, not treated as text.
- Runtime transports:
  - `FF10 / FFF1` write/write-no-response;
  - `FF12 / FF13 / FF14` write plus read/notify;
  - NUS `6E400001 / 6E400002 / 6E400003`;
  - `FF00 / FF01 / FF02` read/notify plus write/write-no-response.
- All eight readable characteristics completed successfully.
- Empty direct reads from notify channels are expected until a command or event produces a notification.

## Runtime survey findings

The official NUS settings request `0x09/0x00` returned a stable 71-byte payload. The bytes are preserved verbatim and are not assigned meanings without an A/B test.

The product-identification request `0x20/0x00` returned only the normal `FD` acknowledgement on this G28; no `DF/0x20` payload was observed. Product identification is therefore not a mandatory compatibility feature for the custom firmware unless later evidence changes this conclusion.

A passive 30-second capture on NUS alone produced no spontaneous notification. This does not prove that the watch has no events; the alternate notify channels `FF14`, `FF01`, and battery `2A19` had not been enabled in that session.

## v3.20 safe survey policy

The next survey may:

- enable CCCDs for NUS, `FF14`, `FF01`, and battery `2A19`;
- listen passively on all enabled channels;
- issue the official read-only settings request `0x09/0x00`;
- store two settings snapshots and compare byte offsets locally.

The survey must not:

- set time or RTC;
- change any watch setting from the Android application;
- send partition command `0x03`;
- send firmware blocks, checksums, finalization, or reboot commands.

The exact frame produced by `SettingIssuedUtils.settingSysTime()` remains required before any clock synchronization implementation is allowed.

## HryFine 3.8.9 full-protocol extraction

The complete installed HryFine 3.8.9 project was exported and inspected. This replaces the earlier assumption that the 71-byte settings block was opaque.

Confirmed runtime frame layout:

- `DF` data/command and `FD` acknowledgement;
- 16-bit big-endian body length at bytes 1–2;
- additive 8-bit checksum at byte 3, excluding byte 3 itself;
- command at byte 4, protocol version at byte 5, key/action at byte 6;
- 16-bit big-endian payload length at bytes 7–8;
- payload from byte 9.

Confirmed read-only commands now allowed in the laboratory:

- `0x09/0x00`: device settings;
- `0x11/0x00`: drink-water reminder;
- `0x14/0x00`: sedentary reminder;
- `0x19/0x00`: device feature bitmap;
- `0x20/0x00`: product identification, although the G28 has so far returned only an ACK.

Confirmed but still non-transmitting previews:

- `0x02/0x01`: packed system time/RTC;
- `0x02/0x0B`: phone finds bracelet;
- `0x02/0x0C`: camera mode;
- `0x02/0x21`: drink-water write schema;
- `0x02/0x03`: sedentary write schema.

Incoming `0x0C` device-control actions are now decoded, including find phone, take photo, media controls, Bluetooth status, and Android bond requests.

No explicit NUS command or Android Assistant intent was found for “OK Google”. Feature query `0x19/0x00` must be used to check `supportHID`; Bluetooth Classic/HID remains the leading hypothesis, not a confirmed fact.

## v3.21 safe policy

v3.21 may decode all normal NUS frames and issue the read-only commands above. It may build exact RTC/camera/find-bracelet frames locally for inspection.

v3.21 must not transmit the recovered runtime writes, must not use command `0x0A FLASH_READ`, and must not unlock any OTA partition or firmware operation.
