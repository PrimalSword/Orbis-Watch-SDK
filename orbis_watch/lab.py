from __future__ import annotations

import argparse
import asyncio
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter

from .protocol.packet import Packet
from .watch import Watch

DANGEROUS_COMMANDS = {0x01, 0x02, 0x0F}


@dataclass(slots=True)
class Probe:
    command: int
    subcommand: int
    payload_hex: str
    status: str
    elapsed_ms: float
    response_hex: str = ""
    error: str = ""


def load_capture(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
            record["_line"] = line_number
            records.append(record)
    return records


def analyze_capture(path: Path) -> dict:
    records = load_capture(path)
    directions = Counter(r.get("direction", "UNKNOWN") for r in records)
    commands = Counter(r.get("command") for r in records if r.get("command") is not None)
    lengths = Counter(len(bytes.fromhex(r.get("hex", ""))) for r in records if r.get("hex"))
    exact = Counter(r.get("hex", "") for r in records if r.get("hex"))
    ack = 0
    data = 0
    malformed = 0
    per_command: dict[int, Counter] = defaultdict(Counter)

    for record in records:
        raw_hex = record.get("hex", "")
        try:
            raw = bytes.fromhex(raw_hex)
            packet = Packet.parse(raw) if raw and raw[0] in (0xDF, 0xFD) else None
        except Exception:
            malformed += 1
            continue
        if packet is None:
            continue
        kind = "ACK" if packet.header == 0xFD else "DATA"
        if kind == "ACK":
            ack += 1
        else:
            data += 1
        per_command[packet.command][kind] += 1
        per_command[packet.command][f"LEN_{len(raw)}"] += 1

    return {
        "path": str(path.resolve()),
        "records": len(records),
        "directions": dict(directions),
        "commands": {f"0x{k:02X}": v for k, v in sorted(commands.items())},
        "lengths": dict(sorted(lengths.items())),
        "ack_frames": ack,
        "data_frames": data,
        "malformed": malformed,
        "duplicates": [{"hex": value, "count": count} for value, count in exact.most_common(10) if count > 1],
        "per_command": {f"0x{k:02X}": dict(v) for k, v in sorted(per_command.items())},
    }


def write_report(analysis: dict, output: Path) -> None:
    lines = [
        "# Orbis Watch Capture Report",
        "",
        f"Source: `{analysis['path']}`",
        "",
        f"- Records: {analysis['records']}",
        f"- ACK frames: {analysis['ack_frames']}",
        f"- Data frames: {analysis['data_frames']}",
        f"- Malformed/unparsed: {analysis['malformed']}",
        "",
        "## Directions",
        "",
    ]
    for key, value in analysis["directions"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Commands", ""])
    for key, value in analysis["commands"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Per-command classification", ""])
    for key, value in analysis["per_command"].items():
        lines.append(f"### {key}")
        for metric, count in value.items():
            lines.append(f"- {metric}: {count}")
        lines.append("")
    if analysis["duplicates"]:
        lines.extend(["## Repeated frames", ""])
        for item in analysis["duplicates"]:
            lines.append(f"- {item['count']}x `{item['hex']}`")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def crawl(address: str, start: int, end: int, sub_start: int, sub_end: int,
                timeout: float, output: Path, unsafe: bool) -> None:
    if not (0 <= start <= end <= 0xFF and 0 <= sub_start <= sub_end <= 0xFF):
        raise ValueError("Ranges must stay between 0 and 255")

    probes: list[Probe] = []
    async with Watch(address) as watch:
        for command in range(start, end + 1):
            if command in DANGEROUS_COMMANDS and not unsafe:
                print(f"0x{command:02X}: skipped by safety policy")
                continue
            for subcommand in range(sub_start, sub_end + 1):
                started = perf_counter()
                try:
                    response = await watch._client.request(
                        Packet.build(command, subcommand=subcommand),
                        timeout=timeout,
                        accept_ack=True,
                        retry_on_timeout=False,
                    )
                    elapsed = (perf_counter() - started) * 1000
                    status = "ACK" if response.is_ack else "DATA"
                    response_hex = response.to_bytes().hex(" ").upper()
                    print(f"0x{command:02X}/0x{subcommand:02X} {status:<7} {elapsed:7.1f} ms")
                    probes.append(Probe(command, subcommand, "", status, elapsed, response_hex))
                except asyncio.TimeoutError:
                    elapsed = (perf_counter() - started) * 1000
                    print(f"0x{command:02X}/0x{subcommand:02X} TIMEOUT {elapsed:7.1f} ms")
                    probes.append(Probe(command, subcommand, "", "TIMEOUT", elapsed))
                except Exception as exc:
                    elapsed = (perf_counter() - started) * 1000
                    error = f"{type(exc).__name__}: {exc}"
                    print(f"0x{command:02X}/0x{subcommand:02X} ERROR {error}")
                    probes.append(Probe(command, subcommand, "", "ERROR", elapsed, error=error))

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["command_hex", "subcommand_hex", "status", "elapsed_ms", "response_hex", "error"])
        for item in probes:
            writer.writerow([
                f"0x{item.command:02X}", f"0x{item.subcommand:02X}", item.status,
                f"{item.elapsed_ms:.1f}", item.response_hex, item.error,
            ])

    latencies = [p.elapsed_ms for p in probes if p.status not in {"TIMEOUT", "ERROR"}]
    print(f"Saved: {output.resolve()}")
    if latencies:
        print(f"Responsive probes: {len(latencies)}; average latency: {mean(latencies):.1f} ms")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orbis Watch research laboratory")
    sub = parser.add_subparsers(dest="action", required=True)

    analyze = sub.add_parser("analyze", help="Analyze a JSONL capture")
    analyze.add_argument("capture", type=Path)
    analyze.add_argument("--report", type=Path)

    crawler = sub.add_parser("crawl", help="Safely crawl command/subcommand ranges")
    crawler.add_argument("address")
    crawler.add_argument("start", type=lambda value: int(value, 0))
    crawler.add_argument("end", type=lambda value: int(value, 0))
    crawler.add_argument("--sub-start", type=lambda value: int(value, 0), default=0)
    crawler.add_argument("--sub-end", type=lambda value: int(value, 0), default=0)
    crawler.add_argument("--timeout", type=float, default=1.2)
    crawler.add_argument("--output", type=Path, default=Path("orbis_crawl.csv"))
    crawler.add_argument("--unsafe", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.action == "analyze":
        result = analyze_capture(args.capture)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.report:
            write_report(result, args.report)
            print(f"Report: {args.report.resolve()}")
        return
    asyncio.run(crawl(args.address, args.start, args.end, args.sub_start, args.sub_end,
                      args.timeout, args.output, args.unsafe))


if __name__ == "__main__":
    main()
