# Orbis Watch Lab for Android

Experimental Android client for the HryFine-compatible G28 validated by the Orbis Watch SDK.

## What the first APK does

- requests the Android Nearby devices/Bluetooth permissions;
- scans for BLE peripherals and auto-selects the known G28 address or a device named G28;
- connects to Nordic UART Service;
- enables notifications and negotiates a larger MTU;
- sends the validated read/query packets `0xF3`, `0x19`, `0x1A` and `0x18` subcommands `0..3`;
- reads battery level and the feature bitmap through standard GATT characteristics;
- records TX/RX bytes in a copyable session log;
- exposes a guarded raw-frame sender;
- exposes one deliberately limited watchface experiment: a single empty `0x0F` handshake followed by a `0xF3` liveness check.

## Deliberate limits

This build does not upload firmware, erase flash, restore factory settings, stream a watchface, or send a transfer finalization command. Commands associated with OTA, reset, factory restore and flash operations are blocked in the raw sender.

The empty `0x0F` handshake is still experimental because the vendor behavior has not yet been captured. It requires typing `ARRISCAR` and is transmitted only once. It should be tested only with the watch well charged and HryFine force-stopped.

## Downloading the APK

1. Open the repository's **Actions** tab.
2. Select **Android Mobile APK**.
3. Open the latest successful run from branch `mobile-experimental`.
4. Download the artifact **Orbis-Watch-Lab-Android**.
5. Extract `Orbis-Watch-Lab-debug.apk` and install it on the Android phone.

Android may ask permission to install unknown apps for the browser or file manager used to open the APK.

## First test order

1. Force-stop HryFine.
2. Keep the G28 awake and above 70% battery.
3. Open Orbis Watch Lab and grant Nearby devices permission.
4. Scan, select G28 and connect.
5. Run **Ler diagnóstico completo**.
6. Copy the log and preserve it.
7. Run **Teste expandido 0x18**.
8. Only after both tests succeed, consider the guarded `0x0F` handshake.

The first useful result is not a visual change. It is a clean log showing whether Android receives `DATA`, `ACK`, a disconnect, or another state transition after the experimental frame.
