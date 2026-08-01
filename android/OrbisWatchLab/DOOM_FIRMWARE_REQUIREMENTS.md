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

## Runtime survey policy

The next safe survey may send only official read requests used by HryFine:

- `0x09/0x00` — current settings;
- `0x20/0x00` — product identification.

These requests must not be confused with firmware reads. They are used only to document the clock/UI/BLE behavior that a future DOOM firmware must preserve.
