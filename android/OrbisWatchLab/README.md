# Orbis Watch Lab for Android

Android BLE laboratory for the G28 / HryFine-compatible watch already validated by the Orbis Watch SDK.

## Version 2.0 emergency build

- scans and connects to the G28;
- reads device information, battery, and feature bitmap;
- performs the validated `0x18` subcommand test;
- sends controlled `0x0F` watchface subcommands one at a time;
- consults `DEVICE_INFO` after every `0x0F` experiment;
- includes a fixed emergency-stop button that cancels scheduled work, blocks new writes, and closes GATT;
- does not expose OTA, reset, factory restore, flash-read, or bulk-transfer commands.

The emergency stop cannot retract a BLE frame that was already delivered to the watch. It prevents subsequent app operations and disconnects immediately.

This branch exists only to validate the Android build in GitHub Actions.
