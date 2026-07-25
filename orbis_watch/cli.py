from __future__ import annotations

import argparse
import asyncio
import shlex

from .watch import Watch


BANNER = """Orbis Watch Console v0.1
Type 'help' for commands.
"""


async def run_console(address: str) -> None:
    print(BANNER)

    async with Watch(address) as watch:
        print(f"Connected: {watch.is_connected}")
        print(f"Address: {address}\n")

        while True:
            try:
                raw = await asyncio.to_thread(input, "orbis> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break

            parts = shlex.split(raw)
            if not parts:
                continue

            command = parts[0].lower()

            try:
                if command in {"exit", "quit"}:
                    break

                if command == "help":
                    print(
                        "Commands:\n"
                        "  info      Read firmware and project information\n"
                        "  battery   Read battery level\n"
                        "  features  Read the raw feature bitmap and enabled bits\n"
                        "  status    Show connection status\n"
                        "  exit      Disconnect and close the console"
                    )
                    continue

                if command == "status":
                    print(f"Connected: {watch.is_connected}")
                    continue

                if command == "battery":
                    level = await watch.get_battery_level()
                    print(f"Battery: {level}%")
                    continue

                if command == "info":
                    print(await watch.get_device_info())
                    continue

                if command == "features":
                    features = await watch.get_features()
                    print(f"Feature ACK: {features.acknowledged}")
                    print(f"Bitmap: {features.hex}")
                    print(f"Enabled bits: {features.enabled_bits}")
                    continue

                print(f"Unknown command: {command}. Type 'help'.")
            except Exception as exc:
                print(f"Command failed: {type(exc).__name__}: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive Orbis Watch console")
    parser.add_argument("address", help="Bluetooth LE address of the watch")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(run_console(args.address))


if __name__ == "__main__":
    main()
