from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter

from .client import OrbisWatchClient, TrafficEvent
from .constants import BATTERY_LEVEL_UUID, FEATURE_BITMAP_UUID, CommandID
from .models.device_info import DeviceInfo
from .models.feature_set import FeatureSet
from .protocol.packet import Packet


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    command: int
    status: str
    elapsed_ms: float
    response: bytes = b""
    error: str = ""


class Watch:
    def __init__(self, address: str, timeout: float = 20.0) -> None:
        self.address = address
        self._client = OrbisWatchClient(address, timeout=timeout)

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    async def connect(self) -> None:
        await self._client.connect()

    async def disconnect(self) -> None:
        await self._client.disconnect()

    async def __aenter__(self) -> "Watch":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.disconnect()

    async def get_device_info(self) -> DeviceInfo:
        response = await self._client.request(
            Packet.build(CommandID.DEVICE_INFO),
            timeout=10.0,
        )
        return DeviceInfo.from_payload(response.payload)

    async def get_battery_level(self) -> int:
        value = await self._client.read_gatt(BATTERY_LEVEL_UUID)
        if len(value) != 1:
            raise ValueError(f"Unexpected battery payload length: {len(value)}")
        return value[0]

    async def request_features(self) -> bool:
        response = await self._client.request(
            Packet.build(CommandID.GET_FEATURE),
            timeout=10.0,
            accept_ack=True,
        )
        return response.is_ack and response.ack_status == 0x01

    async def get_features(self, *, request_ack: bool = True) -> FeatureSet:
        acknowledged = await self.request_features() if request_ack else False
        bitmap = await self._client.read_gatt(FEATURE_BITMAP_UUID)
        return FeatureSet.from_bytes(bitmap, acknowledged=acknowledged)

    async def write_raw(self, data: bytes) -> None:
        await self._client.write_raw(data)

    async def next_traffic(self, timeout: float | None = None) -> TrafficEvent:
        return await self._client.next_traffic(timeout)

    def clear_traffic(self) -> None:
        self._client.clear_traffic()

    def add_traffic_observer(self, observer) -> None:
        self._client.add_traffic_observer(observer)

    def remove_traffic_observer(self, observer) -> None:
        self._client.remove_traffic_observer(observer)

    async def probe_command(self, command: int, timeout: float = 1.5) -> DiscoveryResult:
        started = perf_counter()
        try:
            response = await self._client.request(
                Packet.build(command),
                timeout=timeout,
                accept_ack=True,
                retry_on_timeout=False,
            )
            elapsed = (perf_counter() - started) * 1000
            status = "ACK" if response.is_ack else "DATA"
            if response.is_ack and response.ack_status not in (None, 0x01):
                status = f"ACK_STATUS_{response.ack_status:02X}"
            return DiscoveryResult(
                command=command,
                status=status,
                elapsed_ms=elapsed,
                response=response.to_bytes(),
            )
        except asyncio.TimeoutError:
            return DiscoveryResult(
                command=command,
                status="TIMEOUT",
                elapsed_ms=(perf_counter() - started) * 1000,
            )
        except Exception as exc:
            return DiscoveryResult(
                command=command,
                status="ERROR",
                elapsed_ms=(perf_counter() - started) * 1000,
                error=f"{type(exc).__name__}: {exc}",
            )
