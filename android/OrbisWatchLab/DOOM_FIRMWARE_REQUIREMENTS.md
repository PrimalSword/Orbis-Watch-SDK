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
- Normal BLE transport: Nordic UART Service 6E400001/2/3
- Bootloader transport: 18A8, RX 2AA8, TX 2AA9
- Normal/boot address relation: final byte XOR `0x55`
