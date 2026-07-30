from __future__ import annotations

import json
import struct
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator

BTSNOOP_MAGIC = b"btsnoop\x00"
BTSNOOP_HEADER = struct.Struct(">8sII")
BTSNOOP_RECORD = struct.Struct(">IIIIQ")
BTSNOOP_EPOCH_DELTA_US = 0x00DC_DDB3_0F2F_8000
HCI_UART_H4 = 1002
H4_ACL = 0x02
ATT_CID = 0x0004

ATT_NAMES = {
    0x01: "ERROR_RESPONSE",
    0x12: "WRITE_REQUEST",
    0x13: "WRITE_RESPONSE",
    0x16: "PREPARE_WRITE_REQUEST",
    0x17: "PREPARE_WRITE_RESPONSE",
    0x18: "EXECUTE_WRITE_REQUEST",
    0x19: "EXECUTE_WRITE_RESPONSE",
    0x1B: "HANDLE_VALUE_NOTIFICATION",
    0x1D: "HANDLE_VALUE_INDICATION",
    0x1E: "HANDLE_VALUE_CONFIRMATION",
    0x52: "WRITE_COMMAND",
    0xD2: "SIGNED_WRITE_COMMAND",
}


class BtsnoopError(ValueError):
    """Raised when a BTSnoop file is truncated or structurally invalid."""


@dataclass(frozen=True, slots=True)
class BtsnoopRecord:
    index: int
    original_length: int
    included_length: int
    flags: int
    cumulative_drops: int
    timestamp_us: int
    packet: bytes

    @property
    def direction(self) -> str:
        # Android writes bit 0 for packets received by the host.
        return "RX" if self.flags & 0x01 else "TX"

    @property
    def timestamp(self) -> str | None:
        unix_us = self.timestamp_us - BTSNOOP_EPOCH_DELTA_US
        if unix_us < 0:
            return None
        return datetime.fromtimestamp(unix_us / 1_000_000, tz=timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class AttFrame:
    record_index: int
    timestamp: str | None
    direction: str
    connection_handle: int
    opcode: int
    attribute_handle: int | None
    value: bytes

    @property
    def opcode_name(self) -> str:
        return ATT_NAMES.get(self.opcode, f"UNKNOWN_0x{self.opcode:02X}")

    @property
    def value_hex(self) -> str:
        return self.value.hex(" ").upper()

    @property
    def looks_like_orbis(self) -> bool:
        return bool(self.value and self.value[0] in (0xDF, 0xFD))

    def to_dict(self) -> dict[str, object]:
        return {
            "record_index": self.record_index,
            "timestamp": self.timestamp,
            "direction": self.direction,
            "connection_handle": self.connection_handle,
            "connection_handle_hex": f"0x{self.connection_handle:04X}",
            "opcode": self.opcode,
            "opcode_hex": f"0x{self.opcode:02X}",
            "opcode_name": self.opcode_name,
            "attribute_handle": self.attribute_handle,
            "attribute_handle_hex": (
                f"0x{self.attribute_handle:04X}" if self.attribute_handle is not None else None
            ),
            "value_hex": self.value.hex().upper(),
            "value_length": len(self.value),
            "looks_like_orbis": self.looks_like_orbis,
        }


@dataclass(slots=True)
class _L2capAssembly:
    expected_length: int
    cid: int
    payload: bytearray
    first_record_index: int
    timestamp: str | None
    direction: str


def _read_exact(handle: BinaryIO, size: int) -> bytes:
    data = handle.read(size)
    if len(data) != size:
        raise BtsnoopError(f"Unexpected end of file: needed {size} bytes, got {len(data)}")
    return data


def iter_btsnoop(source: str | Path | BinaryIO) -> Iterator[BtsnoopRecord]:
    close_after = False
    if hasattr(source, "read"):
        handle = source  # type: ignore[assignment]
    else:
        handle = Path(source).open("rb")
        close_after = True

    try:
        magic, version, datalink = BTSNOOP_HEADER.unpack(_read_exact(handle, BTSNOOP_HEADER.size))
        if magic != BTSNOOP_MAGIC:
            raise BtsnoopError("Not a BTSnoop file (invalid magic header)")
        if version != 1:
            raise BtsnoopError(f"Unsupported BTSnoop version: {version}")
        if datalink != HCI_UART_H4:
            raise BtsnoopError(
                f"Unsupported BTSnoop datalink {datalink}; expected HCI UART H4 ({HCI_UART_H4})"
            )

        index = 0
        while True:
            raw_header = handle.read(BTSNOOP_RECORD.size)
            if not raw_header:
                break
            if len(raw_header) != BTSNOOP_RECORD.size:
                raise BtsnoopError("Truncated BTSnoop record header")
            original_length, included_length, flags, drops, timestamp_us = BTSNOOP_RECORD.unpack(
                raw_header
            )
            packet = _read_exact(handle, included_length)
            yield BtsnoopRecord(
                index=index,
                original_length=original_length,
                included_length=included_length,
                flags=flags,
                cumulative_drops=drops,
                timestamp_us=timestamp_us,
                packet=packet,
            )
            index += 1
    finally:
        if close_after:
            handle.close()


def _parse_att(
    record_index: int,
    timestamp: str | None,
    direction: str,
    conn: int,
    pdu: bytes,
) -> AttFrame | None:
    if not pdu:
        return None
    opcode = pdu[0]
    attribute_handle: int | None = None
    value = b""

    if opcode in {0x12, 0x16, 0x17, 0x1B, 0x1D, 0x52, 0xD2}:
        if len(pdu) < 3:
            return None
        attribute_handle = int.from_bytes(pdu[1:3], "little")
        if opcode in {0x16, 0x17}:
            if len(pdu) < 5:
                return None
            value = pdu[5:]
        elif opcode == 0xD2:
            value = pdu[3:-12] if len(pdu) >= 15 else b""
        else:
            value = pdu[3:]

    return AttFrame(
        record_index=record_index,
        timestamp=timestamp,
        direction=direction,
        connection_handle=conn,
        opcode=opcode,
        attribute_handle=attribute_handle,
        value=value,
    )


def iter_att_frames(records: Iterable[BtsnoopRecord]) -> Iterator[AttFrame]:
    assemblies: dict[tuple[str, int], _L2capAssembly] = {}

    for record in records:
        packet = record.packet
        if len(packet) < 5 or packet[0] != H4_ACL:
            continue

        handle_flags, acl_length = struct.unpack_from("<HH", packet, 1)
        conn = handle_flags & 0x0FFF
        pb_flag = (handle_flags >> 12) & 0x03
        acl_payload = packet[5 : 5 + acl_length]
        if len(acl_payload) != acl_length:
            continue

        key = (record.direction, conn)
        if pb_flag in (0x00, 0x02):
            if len(acl_payload) < 4:
                continue
            l2cap_length, cid = struct.unpack_from("<HH", acl_payload, 0)
            assembly = _L2capAssembly(
                expected_length=l2cap_length,
                cid=cid,
                payload=bytearray(acl_payload[4:]),
                first_record_index=record.index,
                timestamp=record.timestamp,
                direction=record.direction,
            )
            assemblies[key] = assembly
        elif pb_flag == 0x01:
            assembly = assemblies.get(key)
            if assembly is None:
                continue
            assembly.payload.extend(acl_payload)
        else:
            continue

        assembly = assemblies.get(key)
        if assembly is None or len(assembly.payload) < assembly.expected_length:
            continue

        pdu = bytes(assembly.payload[: assembly.expected_length])
        del assemblies[key]
        if assembly.cid != ATT_CID:
            continue
        frame = _parse_att(
            assembly.first_record_index,
            assembly.timestamp,
            assembly.direction,
            conn,
            pdu,
        )
        if frame is not None:
            yield frame


def read_att_frames(path: str | Path) -> list[AttFrame]:
    return list(iter_att_frames(iter_btsnoop(path)))


def write_jsonl(frames: Iterable[AttFrame], output: str | Path) -> int:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for frame in frames:
            handle.write(json.dumps(frame.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count


def handle_statistics(frames: Iterable[AttFrame]) -> list[dict[str, object]]:
    stats: dict[tuple[str, int | None], dict[str, int]] = defaultdict(
        lambda: {"frames": 0, "bytes": 0, "orbis_frames": 0}
    )
    for frame in frames:
        key = (frame.direction, frame.attribute_handle)
        bucket = stats[key]
        bucket["frames"] += 1
        bucket["bytes"] += len(frame.value)
        bucket["orbis_frames"] += int(frame.looks_like_orbis)

    result: list[dict[str, object]] = []
    for (direction, attribute_handle), bucket in stats.items():
        result.append(
            {
                "direction": direction,
                "attribute_handle": attribute_handle,
                "attribute_handle_hex": (
                    f"0x{attribute_handle:04X}" if attribute_handle is not None else None
                ),
                **bucket,
            }
        )
    return sorted(result, key=lambda item: (-int(item["bytes"]), str(item["direction"])))
