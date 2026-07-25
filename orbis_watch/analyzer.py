from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CaptureSummary:
    records: int
    tx: int
    rx: int
    commands: tuple[tuple[int, int], ...]
    frame_lengths: tuple[tuple[int, int], ...]


def load_capture(path: str | Path) -> list[dict]:
    records: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number}: {exc}") from exc
            records.append(record)
    return records


def summarize_capture(path: str | Path) -> CaptureSummary:
    records = load_capture(path)
    directions = Counter(str(r.get("direction", "")).upper() for r in records)
    commands = Counter(int(r["command"]) for r in records if r.get("command") is not None)
    lengths = Counter(len(bytes.fromhex(str(r.get("hex", "")))) for r in records if r.get("hex"))
    return CaptureSummary(
        records=len(records),
        tx=directions.get("TX", 0),
        rx=directions.get("RX", 0),
        commands=tuple(sorted(commands.items())),
        frame_lengths=tuple(sorted(lengths.items())),
    )


def export_capture_csv(source: str | Path, destination: str | Path) -> Path:
    records = load_capture(source)
    destination = Path(destination)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["line", "timestamp", "direction", "command_hex", "length", "hex"])
        for index, record in enumerate(records, 1):
            raw = bytes.fromhex(str(record.get("hex", ""))) if record.get("hex") else b""
            command = record.get("command")
            writer.writerow([
                index,
                record.get("timestamp", ""),
                record.get("direction", ""),
                f"0x{int(command):02X}" if command is not None else "",
                len(raw),
                raw.hex(" ").upper(),
            ])
    return destination


def generate_markdown_report(source: str | Path, destination: str | Path) -> Path:
    summary = summarize_capture(source)
    records = load_capture(source)
    by_command: dict[int, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("command") is not None:
            by_command[int(record["command"])].append(record)

    lines = [
        "# Orbis Watch Capture Report",
        "",
        f"- Source: `{Path(source)}`",
        f"- Records: {summary.records}",
        f"- TX: {summary.tx}",
        f"- RX: {summary.rx}",
        "",
        "## Commands",
        "",
        "| Command | Frames | Directions | Lengths |",
        "|---:|---:|---|---|",
    ]
    for command, count in summary.commands:
        group = by_command[command]
        directions = ", ".join(sorted({str(r.get("direction", "")) for r in group}))
        lengths = sorted({len(bytes.fromhex(str(r.get("hex", "")))) for r in group if r.get("hex")})
        lines.append(f"| `0x{command:02X}` | {count} | {directions} | {', '.join(map(str, lengths))} |")

    lines.extend(["", "## Frame length distribution", "", "| Length | Count |", "|---:|---:|"])
    for length, count in summary.frame_lengths:
        lines.append(f"| {length} | {count} |")

    destination = Path(destination)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination
