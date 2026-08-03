from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from bleak import BleakClient, BleakScanner

from ota_protocol import D6StreamParser, OtaResponse, TrafficRecord, parse_response

BOOT_PROFILES = (
    (
        "G28 observed 18A8",
        "000018a8-0000-1000-8000-00805f9b34fb",
        "00002aa9-0000-1000-8000-00805f9b34fb",
        "00002aa8-0000-1000-8000-00805f9b34fb",
    ),
    (
        "HryFine 5610 proprietary",
        "6e40ff01-b5a3-f393-e0a9-e50e24dcca9e",
        "6e40ff02-b5a3-f393-e0a9-e50e24dcca9e",
        "6e40ff03-b5a3-f393-e0a9-e50e24dcca9e",
    ),
)


@dataclass(frozen=True, slots=True)
class ScannedDevice:
    name: str
    address: str
    rssi: int | None

    @property
    def label(self) -> str:
        signal = "?" if self.rssi is None else str(self.rssi)
        return f"{self.name or '(sem nome)'} | {self.address} | RSSI {signal}"


class G28BootLink:
    def __init__(
        self,
        on_log: Callable[[str], None],
        on_traffic: Callable[[TrafficRecord], None],
        on_response: Callable[[OtaResponse], None],
    ) -> None:
        self.on_log = on_log
        self.on_traffic = on_traffic
        self.on_response = on_response
        self.client: BleakClient | None = None
        self.write_uuid = ""
        self.notify_uuid = ""
        self.profile_name = ""
        self.parser = D6StreamParser()

    @property
    def connected(self) -> bool:
        return bool(self.client and self.client.is_connected)

    async def scan(self, timeout: float = 7.0) -> list[ScannedDevice]:
        self.on_log(f"Escaneando BLE por {timeout:.0f} segundos...")
        discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)
        devices: list[ScannedDevice] = []
        for _, pair in discovered.items():
            device, advertisement = pair
            name = advertisement.local_name or device.name or ""
            address = device.address
            rssi = getattr(advertisement, "rssi", None)
            if "G28" in name.upper() or address.upper().endswith(":02") or "OTA" in name.upper():
                devices.append(ScannedDevice(name=name, address=address, rssi=rssi))
        devices.sort(key=lambda item: ("G28" not in item.name.upper(), -(item.rssi or -999)))
        self.on_log(f"Escaneamento concluído: {len(devices)} candidato(s) G28/OTA.")
        return devices

    async def connect(self, address: str) -> str:
        await self.disconnect()
        self.parser.reset()
        self.on_log(f"Conectando a {address}...")
        self.client = BleakClient(address, timeout=25.0, disconnected_callback=self._on_disconnect)
        await self.client.connect()
        self.on_log("BLE conectado. Inspecionando serviços GATT...")

        services = self.client.services
        available = {str(service.uuid).lower(): service for service in services}
        chosen = None
        for profile in BOOT_PROFILES:
            profile_name, service_uuid, write_uuid, notify_uuid = profile
            service = available.get(service_uuid.lower())
            if service is None:
                continue
            characteristic_uuids = {str(characteristic.uuid).lower() for characteristic in service.characteristics}
            if write_uuid.lower() in characteristic_uuids and notify_uuid.lower() in characteristic_uuids:
                chosen = profile
                break
        if chosen is None:
            await self.disconnect()
            exposed = ", ".join(sorted(available))
            raise RuntimeError(f"Nenhum transporte OTA conhecido foi encontrado. Serviços: {exposed}")

        self.profile_name, _, self.write_uuid, self.notify_uuid = chosen
        await self.client.start_notify(self.notify_uuid, self._notification)
        self.on_log(f"Transporte confirmado: {self.profile_name}")
        self.on_log(f"TX {self.write_uuid} | RX {self.notify_uuid}")
        return self.profile_name

    async def disconnect(self) -> None:
        client = self.client
        self.client = None
        if not client:
            return
        try:
            if client.is_connected and self.notify_uuid:
                try:
                    await client.stop_notify(self.notify_uuid)
                except Exception:
                    pass
            if client.is_connected:
                await client.disconnect()
        finally:
            self.write_uuid = ""
            self.notify_uuid = ""
            self.profile_name = ""
            self.parser.reset()
            self.on_log("BLE desconectado.")

    async def send_read_only(self, frame: bytes, note: str) -> None:
        if not self.client or not self.client.is_connected or not self.write_uuid:
            raise RuntimeError("Relógio OTA não está conectado")
        self.on_traffic(TrafficRecord.now("TX", frame, note))
        self.on_log(f"TX {note}: {frame.hex(' ').upper()}")
        await self.client.write_gatt_char(self.write_uuid, frame, response=False)

    def _notification(self, _characteristic, data: bytearray) -> None:
        raw = bytes(data)
        self.on_traffic(TrafficRecord.now("RX", raw, "BLE notification"))
        self.on_log(f"RX chunk: {raw.hex(' ').upper()}")
        for frame in self.parser.feed(raw):
            try:
                response = parse_response(frame)
            except ValueError as error:
                self.on_log(f"Resposta D6 inválida: {error}")
                continue
            self.on_response(response)

    def _on_disconnect(self, _client: BleakClient) -> None:
        self.on_log("O relógio encerrou a conexão BLE.")
