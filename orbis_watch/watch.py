from __future__ import annotations

from .client import OrbisWatchClient
from .constants import BATTERY_LEVEL_UUID, FEATURE_BITMAP_UUID, CommandID
from .models.device_info import DeviceInfo
from .models.feature_set import FeatureSet
from .protocol.packet import Packet


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
        """Ask the watch to acknowledge feature discovery."""
        response = await self._client.request(
            Packet.build(CommandID.GET_FEATURE),
            timeout=10.0,
            accept_ack=True,
        )
        return response.is_ack and response.ack_status == 0x01

    async def get_features(self, *, request_ack: bool = True) -> FeatureSet:
        """Read the complete feature bitmap exposed by the watch.

        GET_FEATURE only returns an acknowledgement on the validated G28. The
        actual capabilities bitmap is read from GATT characteristic 0x2A28.
        """
        acknowledged = await self.request_features() if request_ack else False
        bitmap = await self._client.read_gatt(FEATURE_BITMAP_UUID)
        return FeatureSet.from_bytes(bitmap, acknowledged=acknowledged)
