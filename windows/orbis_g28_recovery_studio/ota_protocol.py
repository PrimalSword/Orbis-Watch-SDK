from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


READ_ONLY_COMMANDS = frozenset({0x01, 0x0F})
WRITE_CLASS_COMMANDS = frozenset({0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0E})

COMMAND_NAMES = {
    0x01: "OTA identity",
    0x02: "block checksum",
    0x03: "partition table",
    0x04: "code partition",
    0x05: "audio partition",
    0x06: "character partition",
    0x07: "picture partition",
    0x08: "default parameters",
    0x09: "dial/watchface partition",
    0x0A: "total checksum",
    0x0B: "MTU",
    0x0C: "package configuration",
    0x0D: "frame total",
    0x0E: "finalize/reboot",
    0x0F: "protocol version",
}


@dataclass(frozen=True, slots=True)
class OtaResponse:
    command: int
    version: int
    status: int
    block: int
    fragment: int
    payload: bytes
    raw: bytes

    @property
    def command_name(self) -> str:
        return COMMAND_NAMES.get(self.command, f"unknown 0x{self.command:02X}")

    @property
    def success(self) -> bool:
        return self.status == 1


@dataclass(frozen=True, slots=True)
class OtaIdentity:
    unique_code: str
    prefix_hex: str
    version: str
    project: str


@dataclass(frozen=True, slots=True)
class TrafficRecord:
    direction: str
    payload_hex: str
    note: str = ""
    timestamp: str = ""

    @classmethod
    def now(cls, direction: str, payload: bytes, note: str = "") -> "TrafficRecord":
        return cls(
            direction=direction,
            payload_hex=payload.hex(" ").upper(),
            note=note,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


def build_request(
    command: int,
    *,
    protocol_version: int = 1,
    block: int = 0,
    fragment: int = 0,
    payload: bytes = b"",
) -> bytes:
    """Exact reconstruction of HryFine Cus5610CommandUtils.generalSendBytes."""
    if not 0 <= command <= 0xFF:
        raise ValueError("command must fit in one byte")
    if not 0 <= protocol_version <= 0xFF:
        raise ValueError("protocol_version must fit in one byte")
    if not 0 <= block <= 0xFFFF:
        raise ValueError("block must fit in two bytes")
    if not 0 <= fragment <= 0xFF:
        raise ValueError("fragment must fit in one byte")
    if len(payload) > 0xFFFF:
        raise ValueError("payload is too large")

    frame = bytearray(11 + len(payload))
    frame[0] = 0xD5
    frame[1] = command
    frame[2] = 0x01
    frame[3] = protocol_version
    frame[4] = (block >> 8) & 0xFF
    frame[5] = block & 0xFF
    frame[6] = fragment
    frame[9] = (len(payload) >> 8) & 0xFF
    frame[10] = len(payload) & 0xFF
    frame[11:] = payload

    checksum = sum(value for index, value in enumerate(frame) if index not in (7, 8)) & 0xFFFF
    frame[7] = (checksum >> 8) & 0xFF
    frame[8] = checksum & 0xFF
    return bytes(frame)


def validate_request(frame: bytes) -> bool:
    if len(frame) < 11 or frame[0] != 0xD5:
        return False
    payload_length = (frame[9] << 8) | frame[10]
    if len(frame) != 11 + payload_length:
        return False
    expected = (frame[7] << 8) | frame[8]
    actual = sum(value for index, value in enumerate(frame) if index not in (7, 8)) & 0xFFFF
    return expected == actual


def parse_response(frame: bytes) -> OtaResponse:
    if len(frame) < 9:
        raise ValueError("D6 response shorter than 9 bytes")
    if frame[0] != 0xD6:
        raise ValueError("response does not start with D6")
    payload_length = frame[8]
    expected_length = 9 + payload_length
    if len(frame) != expected_length:
        raise ValueError(f"D6 response length mismatch: expected {expected_length}, got {len(frame)}")
    return OtaResponse(
        command=frame[1],
        version=frame[2],
        status=frame[3],
        block=(frame[4] << 8) | frame[5],
        fragment=(frame[6] << 8) | frame[7],
        payload=bytes(frame[9:]),
        raw=bytes(frame),
    )


def parse_identity(payload: bytes) -> OtaIdentity:
    unique_code = payload.hex().upper()
    if len(payload) < 6:
        return OtaIdentity(unique_code, payload[:4].hex().upper(), "", "")

    prefix = payload[:4].hex().upper()
    version_len = payload[4]
    cursor = 5
    if cursor + version_len > len(payload):
        return OtaIdentity(unique_code, prefix, "", "")
    version = payload[cursor : cursor + version_len].decode("utf-8", errors="replace")
    cursor += version_len

    if cursor >= len(payload):
        return OtaIdentity(unique_code, prefix, version, "")
    project_len = payload[cursor]
    cursor += 1
    if cursor + project_len > len(payload):
        return OtaIdentity(unique_code, prefix, version, "")
    project = payload[cursor : cursor + project_len].decode("utf-8", errors="replace")
    return OtaIdentity(unique_code, prefix, version, project)


class D6StreamParser:
    """Reassembles fragmented D6 notifications without interpreting write semantics."""

    def __init__(self, max_frame_size: int = 4096) -> None:
        self._buffer = bytearray()
        self._expected = 0
        self.max_frame_size = max_frame_size

    def reset(self) -> None:
        self._buffer.clear()
        self._expected = 0

    def feed(self, chunk: bytes) -> list[bytes]:
        frames: list[bytes] = []
        if not chunk:
            return frames

        self._buffer.extend(chunk)
        while self._buffer:
            if self._buffer[0] != 0xD6:
                try:
                    next_header = self._buffer.index(0xD6, 1)
                except ValueError:
                    self.reset()
                    return frames
                del self._buffer[:next_header]

            if len(self._buffer) < 9:
                return frames

            self._expected = 9 + self._buffer[8]
            if self._expected < 9 or self._expected > self.max_frame_size:
                del self._buffer[0]
                self._expected = 0
                continue
            if len(self._buffer) < self._expected:
                return frames

            frames.append(bytes(self._buffer[: self._expected]))
            del self._buffer[: self._expected]
            self._expected = 0
        return frames


def parse_hex(text: str) -> bytes:
    compact = "".join(character for character in text if character not in " \t\r\n:-_")
    if not compact:
        return b""
    if len(compact) % 2:
        raise ValueError("hexadecimal input must contain an even number of digits")
    return bytes.fromhex(compact)


def format_hex(data: Iterable[int]) -> str:
    return bytes(data).hex(" ").upper()
