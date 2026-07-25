from __future__ import annotations

import asyncio
from collections import defaultdict

from bleak import BleakClient
from bleak.exc import BleakError

from .constants import NUS_NOTIFY_UUID, NUS_WRITE_UUID
from .protocol.packet import Packet
from .protocol.parser import PacketStreamParser


class OrbisWatchClient:
    def __init__(
        self,
        address: str,
        timeout: float = 20.0,
        connect_attempts: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        self.address = address
        self.timeout = timeout
        self.connect_attempts = max(1, connect_attempts)
        self.retry_delay = max(0.0, retry_delay)
        self._client = self._new_client()
        self._parser = PacketStreamParser()
        self._queues: dict[int, asyncio.Queue[Packet]] = defaultdict(asyncio.Queue)
        self._started = False

    def _new_client(self) -> BleakClient:
        return BleakClient(self.address, timeout=self.timeout)

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    async def connect(self) -> None:
        if self._client.is_connected:
            return

        last_error: Exception | None = None

        for attempt in range(1, self.connect_attempts + 1):
            self._client = self._new_client()

            try:
                await self._client.connect()
                await self._client.start_notify(NUS_NOTIFY_UUID, self._on_notify)
                self._started = True
                return
            except (BleakError, TimeoutError, OSError) as exc:
                last_error = exc
                self._started = False

                try:
                    if self._client.is_connected:
                        await self._client.disconnect()
                except Exception:
                    pass

                if attempt < self.connect_attempts:
                    await asyncio.sleep(self.retry_delay)

        raise BleakError(
            f"Could not connect to watch {self.address} after "
            f"{self.connect_attempts} attempts. Ensure the watch is awake, nearby, "
            "and disconnected from HryFine or other Bluetooth applications."
        ) from last_error

    async def disconnect(self) -> None:
        if self._started and self._client.is_connected:
            try:
                await self._client.stop_notify(NUS_NOTIFY_UUID)
            except BleakError:
                pass
        self._started = False
        if self._client.is_connected:
            await self._client.disconnect()

    async def __aenter__(self) -> "OrbisWatchClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.disconnect()

    def _on_notify(self, _sender: object, data: bytearray) -> None:
        for packet in self._parser.feed(data):
            self._queues[packet.command].put_nowait(packet)

    async def send(self, packet: Packet) -> None:
        if not self._client.is_connected:
            raise RuntimeError("Watch is not connected")

        await self._client.write_gatt_char(
            NUS_WRITE_UUID,
            packet.to_bytes(),
            response=False,
        )

    async def request(
        self,
        packet: Packet,
        *,
        timeout: float = 10.0,
        accept_ack: bool = False,
    ) -> Packet:
        queue = self._queues[packet.command]

        while not queue.empty():
            queue.get_nowait()

        await self.send(packet)

        async def wait_for_matching() -> Packet:
            while True:
                response = await queue.get()
                if accept_ack or not response.is_ack:
                    return response

        return await asyncio.wait_for(wait_for_matching(), timeout=timeout)

    async def read_gatt(self, uuid: str) -> bytes:
        if not self._client.is_connected:
            raise RuntimeError("Watch is not connected")
        return bytes(await self._client.read_gatt_char(uuid))
