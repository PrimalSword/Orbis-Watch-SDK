from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from .protocol.packet import Packet


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    raw_hex: str
    valid: bool
    frame_type: str
    command: int | None
    subcommand: int | None
    payload_hex: str
    payload_ascii: str
    length: int
    checksum: int | None
    ack_status: int | None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        value = asdict(self)
        if self.command is not None:
            value["command_hex"] = f"0x{self.command:02X}"
        if self.subcommand is not None:
            value["subcommand_hex"] = f"0x{self.subcommand:02X}"
        return value


def printable_ascii(data: bytes) -> str:
    return "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in data)


def decode_frame(data: bytes) -> DecodedFrame:
    notes: list[str] = []
    try:
        packet = Packet.parse(data)
    except Exception as exc:
        return DecodedFrame(
            raw_hex=data.hex(" ").upper(), valid=False, frame_type="MALFORMED",
            command=None, subcommand=None, payload_hex="", payload_ascii="",
            length=len(data), checksum=data[3] if len(data) > 3 else None,
            ack_status=None, notes=(f"{type(exc).__name__}: {exc}",),
        )

    payload = packet.payload
    frame_type = "ACK" if packet.is_ack else "DATA"
    if packet.command == 0xF3 and not packet.is_ack:
        notes.append("DEVICE_INFO response")
    elif packet.command == 0x19:
        notes.append("GET_FEATURE")
    elif packet.command == 0x1A:
        notes.append("GET_FUNCTION")
    if payload and all(32 <= byte <= 126 for byte in payload):
        notes.append("Printable ASCII payload")

    return DecodedFrame(
        raw_hex=data.hex(" ").upper(), valid=True, frame_type=frame_type,
        command=packet.command, subcommand=packet.subcommand,
        payload_hex=payload.hex(" ").upper(), payload_ascii=printable_ascii(payload),
        length=len(data), checksum=packet.checksum, ack_status=packet.ack_status,
        notes=tuple(notes),
    )


def decode_hex(value: str) -> DecodedFrame:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", value)
    if not cleaned or len(cleaned) % 2:
        raise ValueError("Hex data must contain an even number of digits")
    return decode_frame(bytes.fromhex(cleaned))


def load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            record["_line"] = line_number
            records.append(record)
    return records


def filter_records(records: list[dict], expression: str) -> list[dict]:
    expression = expression.strip()
    if not expression:
        return records
    terms = expression.lower().split()
    result: list[dict] = []
    for record in records:
        raw = bytes.fromhex(record.get("hex", "")) if record.get("hex") else b""
        decoded = decode_frame(raw) if raw else None
        matched = True
        for term in terms:
            if term in {"tx", "rx"}:
                matched &= record.get("direction", "").lower() == term
            elif term in {"ack", "data", "malformed"}:
                matched &= decoded is not None and decoded.frame_type.lower() == term
            elif term.startswith("cmd="):
                target = int(term.split("=", 1)[1], 0)
                matched &= decoded is not None and decoded.command == target
            elif term.startswith("len>"):
                matched &= len(raw) > int(term[4:], 0)
            elif term.startswith("len<"):
                matched &= len(raw) < int(term[4:], 0)
            else:
                matched &= term in record.get("hex", "").lower()
            if not matched:
                break
        if matched:
            result.append(record)
    return result


def diff_captures(left: Path, right: Path) -> dict:
    left_records = load_jsonl(left)
    right_records = load_jsonl(right)
    left_hex = Counter(r.get("hex", "") for r in left_records if r.get("hex"))
    right_hex = Counter(r.get("hex", "") for r in right_records if r.get("hex"))

    def commands(records: list[dict]) -> Counter:
        values: Counter = Counter()
        for record in records:
            raw_hex = record.get("hex", "")
            if not raw_hex:
                continue
            decoded = decode_frame(bytes.fromhex(raw_hex))
            if decoded.command is not None:
                values[f"0x{decoded.command:02X}"] += 1
        return values

    left_commands = commands(left_records)
    right_commands = commands(right_records)
    return {
        "left": str(left.resolve()),
        "right": str(right.resolve()),
        "left_records": len(left_records),
        "right_records": len(right_records),
        "new_frames": [{"hex": key, "count": count} for key, count in (right_hex - left_hex).most_common()],
        "removed_frames": [{"hex": key, "count": count} for key, count in (left_hex - right_hex).most_common()],
        "command_delta": {
            key: right_commands[key] - left_commands[key]
            for key in sorted(set(left_commands) | set(right_commands))
            if right_commands[key] != left_commands[key]
        },
    }
