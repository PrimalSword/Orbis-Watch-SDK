# Orbis Watch OTA 5610 v3.12 validation

This validation build keeps firmware writes disabled and focuses on resilient, chipset-neutral bootloader discovery for the G28. It recognizes the observed 4C31/MAC/5610 advertisement, delays service discovery, refreshes Android's GATT cache, retries empty profiles, prevents overlapping OTA scans, and dumps every discovered service before any protocol probe.

The implementation does not assume that the device is Realtek RTL8762C or Bluetrum; the resulting GATT profile will be used to distinguish the actual bootloader family safely.