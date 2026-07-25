from __future__ import annotations

import argparse
import asyncio
import csv
import json
import shlex
from pathlib import Path
from time import monotonic, perf_counter

from bleak import BleakScanner

from .analyzer import export_capture_csv, generate_markdown_report, summarize_capture
from .client import TrafficEvent
from .protocol.packet import Packet
from .safety import DANGEROUS_COMMANDS, command_is_dangerous, inspect_raw_frame
from .watch import Watch

BANNER = """Orbis Watch Console v0.3-dev
Safe mode is ON. Mutating operations require --unsafe and confirmation.
Type 'help' for commands.
"""


def parse_hex(value: str) -> bytes:
    cleaned = value.lower().replace("0x", "").replace(" ", "").replace(":", "").replace("-", "")
    if not cleaned or len(cleaned) % 2:
        raise ValueError("hex data must contain an even, non-zero number of digits")
    return bytes.fromhex(cleaned)


def ascii_view(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data)


def format_event(event: TrafficEvent, detailed: bool = False) -> str:
    command = f" CMD=0x{event.packet.command:02X}" if event.packet else ""
    line = f"{event.timestamp} {event.direction}{command} {event.hex}"
    return f"{line}\nASCII: {ascii_view(event.data)}" if detailed else line


async def collect(watch: Watch, seconds: float, detailed: bool = False) -> list[TrafficEvent]:
    deadline = monotonic() + max(0.0, seconds)
    events: list[TrafficEvent] = []
    while (remaining := deadline - monotonic()) > 0:
        try:
            event = await watch.next_traffic(timeout=remaining)
        except asyncio.TimeoutError:
            break
        events.append(event)
        print(format_event(event, detailed))
    return events


def confirm(operation: str) -> bool:
    answer = input(f"DANGEROUS: {operation}. Type YES to continue: ")
    return answer == "YES"


async def scan_devices(seconds: float) -> None:
    devices = await BleakScanner.discover(timeout=seconds, return_adv=True)
    for address, pair in sorted(devices.items()):
        device, advertisement = pair
        name = device.name or advertisement.local_name or "(unknown)"
        rssi = getattr(advertisement, "rssi", None)
        suffix = f" RSSI={rssi}" if rssi is not None else ""
        print(f"{address}  {name}{suffix}")


async def run_console(address: str) -> None:
    print(BANNER)
    async with Watch(address) as watch:
        print(f"Connected: {watch.is_connected}\nAddress: {address}\n")
        capture_file = None
        capture_observer = None
        history: list[str] = []

        try:
            while True:
                try:
                    raw_line = await asyncio.to_thread(input, "orbis> ")
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if not raw_line.strip():
                    continue
                history.append(raw_line)
                try:
                    parts = shlex.split(raw_line)
                    command = parts[0].lower()

                    if command in {"exit", "quit"}:
                        break
                    if command == "help":
                        print(
                            "Commands:\n"
                            "  info | battery | features | status\n"
                            "  scan [seconds]                 Scan nearby BLE devices\n"
                            "  services                       List GATT services/characteristics\n"
                            "  read <uuid>                    Read any GATT characteristic\n"
                            "  write <uuid> <hex> --unsafe    Arbitrary GATT write with confirmation\n"
                            "  raw <hex> [seconds] [--unsafe] Send exact NUS frame\n"
                            "  packet <cmd> [subcmd]          Build/send safe protocol request\n"
                            "  listen [seconds] | dump [seconds]\n"
                            "  save <file.jsonl> | save stop\n"
                            "  replay <file.jsonl> [--unsafe]\n"
                            "  discover <start> <end> [--unsafe]\n"
                            "  history                        Show console command history\n"
                            "  analyze <capture.jsonl>        Summarize capture\n"
                            "  export <capture> <output.csv>  Export normalized CSV\n"
                            "  report <capture> <output.md>   Generate Markdown report\n"
                            "  benchmark [count]              Measure battery-read latency\n"
                            "  exit"
                        )
                        continue
                    if command == "status":
                        print(f"Connected: {watch.is_connected}\nCapture: {'active' if capture_file else 'inactive'}\nSafety: ON")
                        continue
                    if command == "info":
                        print(await watch.get_device_info())
                        continue
                    if command == "battery":
                        print(f"Battery: {await watch.get_battery_level()}%")
                        continue
                    if command == "features":
                        features = await watch.get_features()
                        print(f"Feature ACK: {features.acknowledged}\nBitmap: {features.hex}\nEnabled bits: {features.enabled_bits}")
                        continue
                    if command == "scan":
                        await scan_devices(float(parts[1]) if len(parts) > 1 else 5.0)
                        continue
                    if command == "services":
                        await watch._client.ensure_connected()
                        for service in watch._client._client.services:
                            print(f"SERVICE {service.uuid} {service.description}")
                            for char in service.characteristics:
                                print(f"  CHAR {char.uuid} [{','.join(char.properties)}] {char.description}")
                        continue
                    if command == "read":
                        if len(parts) != 2:
                            raise ValueError("usage: read <uuid>")
                        data = await watch._client.read_gatt(parts[1])
                        print(f"HEX: {data.hex(' ').upper()}\nASCII: {ascii_view(data)}")
                        continue
                    if command == "write":
                        if len(parts) < 4 or "--unsafe" not in parts:
                            raise ValueError("usage: write <uuid> <hex> --unsafe")
                        data = parse_hex(parts[2])
                        if not confirm(f"write {len(data)} byte(s) to {parts[1]}"):
                            print("Cancelled.")
                            continue
                        await watch._client.ensure_connected()
                        await watch._client._client.write_gatt_char(parts[1], data, response=False)
                        print("Write complete.")
                        continue
                    if command == "raw":
                        if len(parts) < 2:
                            raise ValueError("usage: raw <hex> [seconds] [--unsafe]")
                        data = parse_hex(parts[1])
                        unsafe = "--unsafe" in parts[2:]
                        decision = inspect_raw_frame(data, unsafe=unsafe)
                        if not decision.allowed:
                            raise PermissionError(decision.reason)
                        if unsafe and not confirm(f"send raw frame {data.hex(' ').upper()}"):
                            print("Cancelled.")
                            continue
                        seconds = next((float(p) for p in parts[2:] if p != "--unsafe"), 2.0)
                        watch.clear_traffic()
                        await watch.write_raw(data)
                        print(f"TX: {data.hex(' ').upper()}")
                        await collect(watch, seconds, True)
                        continue
                    if command == "packet":
                        if len(parts) < 2:
                            raise ValueError("usage: packet <cmd> [subcmd]")
                        cmd = int(parts[1], 0)
                        subcmd = int(parts[2], 0) if len(parts) > 2 else 0
                        if command_is_dangerous(cmd):
                            raise PermissionError(f"0x{cmd:02X} blocked: {DANGEROUS_COMMANDS[cmd]}")
                        frame = Packet.build(cmd, subcmd).to_bytes()
                        watch.clear_traffic()
                        await watch.write_raw(frame)
                        print(f"TX: {frame.hex(' ').upper()}")
                        await collect(watch, 2.0, True)
                        continue
                    if command in {"listen", "dump"}:
                        seconds = float(parts[1]) if len(parts) > 1 else 10.0
                        print(f"Listening for {seconds:g} seconds...")
                        await collect(watch, seconds, command == "dump")
                        continue
                    if command == "history":
                        for index, item in enumerate(history, 1):
                            print(f"{index:03}: {item}")
                        continue
                    if command == "save":
                        if len(parts) < 2:
                            raise ValueError("usage: save <file.jsonl> | save stop")
                        if parts[1].lower() == "stop":
                            if capture_observer:
                                watch.remove_traffic_observer(capture_observer)
                            if capture_file:
                                capture_file.close()
                            capture_file = capture_observer = None
                            print("Capture stopped.")
                            continue
                        if capture_observer:
                            watch.remove_traffic_observer(capture_observer)
                        if capture_file:
                            capture_file.close()
                        path = Path(parts[1])
                        path.parent.mkdir(parents=True, exist_ok=True)
                        capture_file = path.open("a", encoding="utf-8")
                        def save_event(event: TrafficEvent) -> None:
                            record = {"timestamp": event.timestamp, "direction": event.direction, "hex": event.data.hex().upper(), "command": event.packet.command if event.packet else None}
                            capture_file.write(json.dumps(record) + "\n")
                            capture_file.flush()
                        capture_observer = save_event
                        watch.add_traffic_observer(capture_observer)
                        print(f"Saving traffic to {path.resolve()}")
                        continue
                    if command == "replay":
                        if len(parts) < 2:
                            raise ValueError("usage: replay <file.jsonl> [--unsafe]")
                        unsafe = "--unsafe" in parts[2:]
                        records = []
                        for line_number, line in enumerate(Path(parts[1]).read_text(encoding="utf-8").splitlines(), 1):
                            if not line.strip():
                                continue
                            record = json.loads(line)
                            if record.get("direction") == "TX":
                                data = parse_hex(record["hex"])
                                decision = inspect_raw_frame(data, unsafe=unsafe)
                                if not decision.allowed:
                                    print(f"line {line_number}: SKIPPED ({decision.reason})")
                                    continue
                                records.append((line_number, data))
                        if unsafe and records and not confirm(f"replay {len(records)} raw TX frame(s)"):
                            print("Cancelled.")
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
                        start, end = int(parts[1], 0), int(parts[2], 0)
                        unsafe = "--unsafe" in parts[3:]
                        if not (0 <= start <= end <= 255):
                            raise ValueError("range must satisfy 0 <= start <= end <= 255")
                        if unsafe and not confirm(f"probe commands 0x{start:02X}..0x{end:02X}, including mutating IDs"):
                            print("Cancelled.")
                            continue
                        output = Path(f"orbis_discovery_{start:02X}_{end:02X}.csv")
                        results = []
                        for cmd in range(start, end + 1):
                            if not unsafe and command_is_dangerous(cmd):
                                print(f"0x{cmd:02X} SKIPPED ({DANGEROUS_COMMANDS[cmd]})")
                                continue
                            result = await watch.probe_command(cmd)
                            results.append(result)
                            detail = result.response.hex(" ").upper() if result.response else result.error
                            print(f"0x{cmd:02X} {result.status:<14} {result.elapsed_ms:8.1f} ms {detail}")
                        with output.open("w", newline="", encoding="utf-8") as handle:
                            writer = csv.writer(handle)
                            writer.writerow(["command_hex", "command", "status", "elapsed_ms", "response_hex", "error"])
                            for result in results:
                                writer.writerow([f"0x{result.command:02X}", result.command, result.status, f"{result.elapsed_ms:.1f}", result.response.hex(" ").upper(), result.error])
                        print(f"Discovery saved to {output.resolve()}")
                        continue
                    if command == "analyze":
                        summary = summarize_capture(parts[1])
                        print(f"Records: {summary.records}\nTX: {summary.tx}\nRX: {summary.rx}\nCommands: {summary.commands}\nLengths: {summary.frame_lengths}")
                        continue
                    if command == "export":
                        print(f"Exported to {export_capture_csv(parts[1], parts[2]).resolve()}")
                        continue
                    if command == "report":
                        print(f"Report written to {generate_markdown_report(parts[1], parts[2]).resolve()}")
                        continue
                    if command == "benchmark":
                        count = int(parts[1]) if len(parts) > 1 else 5
                        samples = []
                        for _ in range(count):
                            started = perf_counter()
                            await watch.get_battery_level()
                            samples.append((perf_counter() - started) * 1000)
                        print(f"Samples: {count} Min: {min(samples):.1f} ms Avg: {sum(samples)/len(samples):.1f} ms Max: {max(samples):.1f} ms")
                        continue
                    print(f"Unknown command: {command}. Type 'help'.")
                except Exception as exc:
                    print(f"Command failed: {type(exc).__name__}: {exc}")
        finally:
            if capture_observer:
                watch.remove_traffic_observer(capture_observer)
            if capture_file:
                capture_file.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orbis Watch reverse-engineering console")
    parser.add_argument("address", help="Bluetooth LE address of the watch")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(run_console(args.address))


if __name__ == "__main__":
    main()
