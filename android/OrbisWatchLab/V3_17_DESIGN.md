# Orbis Watch OTA 5610 v3.17

The v3.17 laboratory build adds only the official `D5/0x01` identity query after a successful `D5/0x0F` / `V1.1` protocol handshake. Partition-table, firmware data, checksum-finalization, transfer reboot and flash writes remain disabled.

The future custom firmware target is explicitly required to preserve three capabilities alongside Doom:

1. a continuously available clock display backed by RTC or an equivalent persistent time source;
2. a recoverable BLE management/OTA channel that remains reachable after Doom is installed;
3. a safe launcher or mode switch so the watch can leave Doom and return to clock/maintenance functions without reflashing.

No future image should be written until the current firmware layout, display path, input path, timekeeping path and recovery channel are understood well enough to satisfy those requirements.
