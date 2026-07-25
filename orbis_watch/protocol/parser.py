from __future__ import annotations

from collections.abc import Iterable

from .packet import Packet


class PacketStreamParser:
    """Reassembles HryFine frames delivered across BLE notification chunks."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def reset(self) -> None:
        self._buffer.clear()

    def feed(self, chunk: bytes | bytearray) -> list[Packet]:
        if not chunk:
            return []

        self._buffer.extend(chunk)
        packets: list[Packet] = []

        while True:
            if len(self._buffer) < 3:
                break

            if self._buffer[0] not in (0xDF, 0xFD):
                del self._buffer[0]
                continue

            total_length = int.from_bytes(self._buffer[1:3], "big") + 4
            if total_length < 9:
                del self._buffer[0]
                continue

            if len(self._buffer) < total_length:
                break

            raw = bytes(self._buffer[:total_length])
            del self._buffer[:total_length]
            packets.append(Packet.parse(raw))

        return packets

    def feed_many(self, chunks: Iterable[bytes | bytearray]) -> list[Packet]:
        packets: list[Packet] = []
        for chunk in chunks:
            packets.extend(self.feed(chunk))
        return packets
