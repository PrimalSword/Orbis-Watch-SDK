from __future__ import annotations

import argparse
import asyncio
import csv
import json
import shlex
from pathlib import Path
from time import monotonic

from .client import TrafficEvent
from .watch import Watch


BANNER = """Orbis Watch Console v0.2
Type 'help' for commands.
"""

# Commands that may alter firmware, settings or watchfaces. Discovery skips them
# unless the operator explicitly supplies --unsafe.
DANGEROUS_COMMANDS = {0x01, 0x02, 0x0F}


def parse_hex(value: str) -> bytes:
    cleaned = value.replace("0x", "").replace(" ", "").replace(":", "").replace("-", "")
    if not cleaned:
        raise ValueError("hexadecimal data is empty")
    if len(cleaned) % 2:
        raise ValueError("hexadecimal data must contain an even number of digits")
    try:
        return bytes.fromhex(cleaned)
    except ValueError as exc:
        raise ValueError(f"invalid hexadecimal data: {value}") from exc


def printable_ascii(data: bytes) -> str:
    return "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in data)


def format_event(event: TrafficEvent, *, detailed: bool = False) -> str:
    command = ""
    if event.packet is not None:
        command = f" CMD=0x{event.packet.command:02X}"
    first = f"{event.timestamp} {event.direction}{command} {event.hex}"
    if not detailed:
        return first
    return f"{first}\nASCII: {printable_ascii(event.data)}"


async def collect_traffic(watch: Watch, seconds: float, *, detailed: bool = False) -> list[TrafficEvent]:
    deadline = monotonic() + max(0.0, seconds)
    events: list[TrafficEvent] = []
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        try:
            event = await watch.next_traffic(timeout=remaining)
        except asyncio.TimeoutError:
            break
        events.append(event)
        print(format_event(event, detailed=detailed))
    return events


async def run_console(address: str) -> None:
    print(BANNER)

    async with Watch(address) as watch:
        print(f"Connected: {watch.is_connected}")
        print(f"Address: {address}\n")

        capture_file = None
        capture_observer = None

        try:
            while True:
                try:
                    raw_line = await asyncio.to_thread(input, "orbis> ")
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                try:
                    parts = shlex.split(raw_line)
                except ValueError as exc:
                    print(f"Parse error: {exc}")
                    continue

                if not parts:
                    continue

                command = parts[0].lower()

                try:
                    if command in {"exit", "quit"}:
                        break

                    if command == "help":
                        print(
                            "Commands:\n"
                            "  info                         Read firmware and project information\n"
                            "  battery                      Read battery level\n"
                            "  features                     Read feature bitmap and enabled bits\n"
                            "  status                       Show connection status\n"
                            "  raw <hex> [seconds]          Send an exact BLE frame and collect replies\n"
                            "  listen [seconds]             Print BLE traffic (default: 10 seconds)\n"
                            "  dump [seconds]               Print traffic in hex and ASCII\n"
                            "  save <file.jsonl>            Start saving TX/RX traffic\n"
                            "  save stop                    Stop saving traffic\n"
                            "  replay <file.jsonl>          Replay TX frames from a capture\n"
                            "  discover <start> <end>       Probe safe command IDs and write CSV\n"
                            "  discover <start> <end> --unsafe  Include mutating commands\n"
                            "  exit                         Disconnect and close the console"
                        )
                        continue

                    if command == "status":
                        print(f"Connected: {watch.is_connected}")
                        print(f"Capture: {'active' if capture_file else 'inactive'}")
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

                    if command == "raw":
                        if len(parts) < 2:
                            raise ValueError("usage: raw <hex> [seconds]")
                        data = parse_hex(parts[1])
                        seconds = float(parts[2]) if len(parts) > 2 else 2.0
                        watch.clear_traffic()
                        await watch.write_raw(data)
                        print(f"TX: {data.hex(' ').upper()}")
                        await collect_traffic(watch, seconds, detailed=True)
                        continue

                    if command in {"listen", "dump"}:
                        seconds = float(parts[1]) if len(parts) > 1 else 10.0
                        print(f"Listening for {seconds:g} seconds...")
                        await collect_traffic(watch, seconds, detailed=command == "dump")
                        continue

                    if command == "save":
                        if len(parts) < 2:
                            raise ValueError("usage: save <file.jsonl> | save stop")
                        if parts[1].lower() == "stop":
                            if capture_observer is not None:
                                watch.remove_traffic_observer(capture_observer)
                            if capture_file is not None:
                                capture_file.close()
                            capture_file = None
                            capture_observer = None
                            print("Capture stopped.")
                            continue

                        if capture_observer is not None:
                            watch.remove_traffic_observer(capture_observer)
                        if capture_file is not None:
                            capture_file.close()

                        path = Path(parts[1])
                        path.parent.mkdir(parents=True, exist_ok=True)
                        capture_file = path.open("a", encoding="utf-8")

                        def save_event(event: TrafficEvent) -> None:
                            assert capture_file is not None
                            record = {
                                "timestamp": event.timestamp,
                                "direction": event.direction,
                                "hex": event.data.hex().upper(),
                                "command": event.packet.command if event.packet else None,
                            }
                            capture_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                            capture_file.flush()

                        capture_observer = save_event
                        watch.add_traffic_observer(capture_observer)
                        print(f"Saving traffic to {path.resolve()}")
                        continue

                    if command == "replay":
                        if len(parts) != 2:
                            raise ValueError("usage: replay <file.jsonl>")
                        path = Path(parts[1])
                        records = []
                        with path.open("r", encoding="utf-8") as handle:
                            for line_number, line in enumerate(handle, 1):
                                if not line.strip():
                                    continue
                                record = json.loads(line)
                                if record.get("direction") == "TX":
                                    records.append((line_number, parse_hex(record["hex"])))
                        if not records:
                            print("No TX frames found.")
                            continue
                        for index, (line_number, data) in enumerate(records, 1):
                            await watch.write_raw(data)
                            print(f"[{index}/{len(records)}] line {line_number}: {data.hex(' ').upper()}")
                            await asyncio.sleep(0.15)
                        print("Replay complete.")
                        continue

                    if command == "discover":
                        if len(parts) < 3:
                            raise ValueError("usage: discover <start> <end> [--unsafe]")
                        start = int(parts[1], 0)
                        end = int(parts[2], 0)
                        unsafe = "--unsafe" in parts[3:]
                        if not (0 <= start <= end <= 0xFF):
                            raise ValueError("command range must satisfy 0 <= start <= end <= 255")

                        output = Path(f"orbis_discovery_{start:02X}_{end:02X}.csv")
                        results = []
                        for cmd in range(start, end + 1):
                            if not unsafe and cmd in DANGEROUS_COMMANDS:
                                print(f"0x{cmd:02X} SKIPPED (potentially mutating)")
                                continue
                            result = await watch.probe_command(cmd)
                            results.append(result)
                            detail = result.response.hex(" ").upper() if result.response else result.error
                            print(f"0x{cmd:02X} {result.status:<14} {result.elapsed_ms:8.1f} ms {detail}")

                        with output.open("w", newline="", encoding="utf-8") as handle:
                            writer = csv.writer(handle)
                            writer.writerow(["command_hex", "command", "status", "elapsed_ms", "response_hex", "error"])
                            for result in results:
                                writer.writerow([
                                    f"0x{result.command:02X}",
                                    result.command,
                                    result.status,
                                    f"{result.elapsed_ms:.1f}",
                                    result.response.hex(" ").upper(),
                                    result.error,
                                ])
                        print(f"Discovery saved to {output.resolve()}")
                        continue

                    print(f"Unknown command: {command}. Type 'help'.")
                except Exception as exc:
                    print(f"Command failed: {type(exc).__name__}: {exc}")
        finally:
            if capture_observer is not None:
                watch.remove_traffic_observer(capture_observer)
            if capture_file is not None:
                capture_file.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive Orbis Watch console")
    parser.add_argument("address", help="Bluetooth LE address of the watch")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(run_console(args.address))


if __name__ == "__main__":
    main()
