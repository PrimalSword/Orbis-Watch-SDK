from __future__ import annotations

from dataclasses import dataclass


REQUEST_HEADER = 0xDF
RESPONSE_HEADER = 0xFD
PROTOCOL_VERSION = 0x01


def checksum8(data: bytes | bytearray) -> int:
    return sum(data) & 0xFF


@dataclass(frozen=True, slots=True)
class Packet:
    header: int
    checksum: int
    command: int
    version: int
    subcommand: int
    payload: bytes

    @property
    def is_ack(self) -> bool:
        return self.header == RESPONSE_HEADER

    @property
    def is_request(self) -> bool:
        return self.header == REQUEST_HEADER

    @property
    def ack_status(self) -> int | None:
        """Return the status byte of an FD acknowledgement frame, when present."""
        if not self.is_ack or not self.payload:
            return None
        return self.payload[-1]

    def to_bytes(self) -> bytes:
        body_length = len(self.payload) + 5
        data = bytearray(
            [
                self.header,
                (body_length >> 8) & 0xFF,
                body_length & 0xFF,
                self.checksum,
                self.command,
                self.version,
                self.subcommand,
                (len(self.payload) >> 8) & 0xFF,
                len(self.payload) & 0xFF,
            ]
        )
        data.extend(self.payload)
        return bytes(data)

    @classmethod
    def build(
        cls,
        command: int,
        subcommand: int = 0,
        payload: bytes = b"",
        version: int = PROTOCOL_VERSION,
        header: int = REQUEST_HEADER,
    ) -> "Packet":
        body_length = len(payload) + 5
        raw = bytearray(
            [
                header,
                (body_length >> 8) & 0xFF,
                body_length & 0xFF,
                command & 0xFF,
                version & 0xFF,
                subcommand & 0xFF,
                (len(payload) >> 8) & 0xFF,
                len(payload) & 0xFF,
            ]
        )
        raw.extend(payload)
        checksum = checksum8(raw)
        return cls(
            header=header,
            checksum=checksum,
            command=command & 0xFF,
            version=version & 0xFF,
            subcommand=subcommand & 0xFF,
            payload=bytes(payload),
        )

    @classmethod
    def parse(cls, data: bytes) -> "Packet":
        if len(data) < 9:
            raise ValueError("Packet is shorter than the minimum 9-byte frame")

        if data[0] not in (REQUEST_HEADER, RESPONSE_HEADER):
            raise ValueError(f"Unknown packet header: 0x{data[0]:02X}")

        body_length = int.from_bytes(data[1:3], "big")
        expected_total = body_length + 4
        if len(data) != expected_total:
            raise ValueError(
                f"Invalid packet length: expected {expected_total}, received {len(data)}"
            )

        expected_checksum = checksum8(data[:3] + data[4:])
        if data[3] != expected_checksum:
            raise ValueError(
                f"Invalid checksum: expected 0x{expected_checksum:02X}, received 0x{data[3]:02X}"
            )

        # FD acknowledgement frames use bytes 7 and 8 as ACK metadata/status,
        # not as the two-byte payload length field used by DF data frames.
        if data[0] == RESPONSE_HEADER:
            payload = data[7:]
        else:
            payload_length = int.from_bytes(data[7:9], "big")
            payload = data[9:]
            if len(payload) != payload_length:
                raise ValueError(
                    f"Invalid payload length: expected {payload_length}, received {len(payload)}"
                )

        return cls(
            header=data[0],
            checksum=data[3],
            command=data[4],
            version=data[5],
            subcommand=data[6],
            payload=payload,
        )
