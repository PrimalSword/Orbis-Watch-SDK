from __future__ import annotations

import asyncio
from collections import defaultdict

from bleak import BleakClient
from bleak.exc import BleakError

from .constants import NUS_NOTIFY_UUID, NUS_WRITE_UUID
from .protocol.packet import Packet
from .protocol.parser import PacketStreamParser


_RETRYABLE_ERRORS = (BleakError, TimeoutError, OSError)


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
        self._connection_lock = asyncio.Lock()

    def _new_client(self) -> BleakClient:
        return BleakClient(self.address, timeout=self.timeout)

    @property
    def is_connected(self) -> bool:
        return bool(self._client.is_connected and self._started)

    async def _dispose_client(self) -> None:
        try:
            if self._started and self._client.is_connected:
                await self._client.stop_notify(NUS_NOTIFY_UUID)
        except Exception:
            pass

        try:
            if self._client.is_connected:
                await self._client.disconnect()
        except Exception:
            pass

        self._started = False

    async def _connect_locked(self) -> None:
        if self.is_connected:
            return

        last_error: Exception | None = None

        for attempt in range(1, self.connect_attempts + 1):
            await self._dispose_client()
            self._client = self._new_client()

            try:
                await self._client.connect()
                await self._client.start_notify(NUS_NOTIFY_UUID, self._on_notify)
                self._started = True
                return
            except _RETRYABLE_ERRORS as exc:
                last_error = exc
                await self._dispose_client()

                if attempt < self.connect_attempts:
                    await asyncio.sleep(self.retry_delay)

        raise BleakError(
            f"Could not connect to watch {self.address} after "
            f"{self.connect_attempts} attempts. Ensure the watch is awake, nearby, "
            "and disconnected from HryFine or other Bluetooth applications."
        ) from last_error

    async def connect(self) -> None:
        async with self._connection_lock:
            await self._connect_locked()

    async def ensure_connected(self) -> None:
        if self.is_connected:
            return

        async with self._connection_lock:
            if not self.is_connected:
                await self._connect_locked()

    async def reconnect(self) -> None:
        async with self._connection_lock:
            await self._dispose_client()
            await self._connect_locked()

    async def disconnect(self) -> None:
        async with self._connection_lock:
            await self._dispose_client()

    async def __aenter__(self) -> "OrbisWatchClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.disconnect()

    def _on_notify(self, _sender: object, data: bytearray) -> None:
        for packet in self._parser.feed(data):
            self._queues[packet.command].put_nowait(packet)

    async def send(self, packet: Packet) -> None:
        await self.ensure_connected()

        try:
            await self._client.write_gatt_char(
                NUS_WRITE_UUID,
                packet.to_bytes(),
                response=False,
            )
        except _RETRYABLE_ERRORS:
            await self.reconnect()
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

        async def perform_request() -> Packet:
            while not queue.empty():
                queue.get_nowait()

            await self.send(packet)

            while True:
                response = await queue.get()
                if accept_ack or not response.is_ack:
                    return response

        try:
            return await asyncio.wait_for(perform_request(), timeout=timeout)
        except (asyncio.TimeoutError, *_RETRYABLE_ERRORS):
            await self.reconnect()
            return await asyncio.wait_for(perform_request(), timeout=timeout)

    async def read_gatt(self, uuid: str) -> bytes:
        await self.ensure_connected()

        try:
            return bytes(await self._client.read_gatt_char(uuid))
        except _RETRYABLE_ERRORS:
            await self.reconnect()
            return bytes(await self._client.read_gatt_char(uuid))
