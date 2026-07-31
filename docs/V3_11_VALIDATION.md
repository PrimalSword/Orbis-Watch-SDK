# Orbis Watch OTA 5610 v3.11 validation

This validation build permits an explicitly confirmed transition into the G28 5610 bootloader when the official server is authenticated but has no published BIN. It automatically performs only the official 0x0F and 0x01 inspection queries after the OTA service appears. Partition-table, firmware-block and finalization operations remain disabled.
