from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field

from .protocol.packet import Packet


@dataclass(slots=True)
class EmulatorState:
    firmware: str = "V1.5"
    project: str = "E06B_G28_WE[G28]_RStyle1_240x240_HryFine"
    battery: int = 100
    feature_bitmap: bytes = bytes.fromhex(
        "AA CE E1 82 DF F6 FC 38 00 00 00 00 00 00 D0 66 40 08 DF 90 00 00 00 40 00 00"
    )
    request_count: int = 0
    unknown_commands: set[int] = field(default_factory=set)


class G28ProtocolEmulator:
    """Offline protocol twin used for parser/client tests.

    This is intentionally transport-neutral. It does not impersonate a BLE peripheral;
    instead it exposes the exact HryFine request/response behavior through TCP so tests
    can be performed safely without the physical watch.
    """

    def __init__(self, state: EmulatorState | None = None) -> None:
        self.state = state or EmulatorState()

    def handle(self, raw: bytes) -> list[bytes]:
        request = Packet.parse(raw)
        self.state.request_count += 1
        command = request.command

        if command == 0xF3:
            payload = bytes([len(self.state.firmware)]) + self.state.firmware.encode("ascii")
            payload += bytes([len(self.state.project)]) + self.state.project.encode("ascii")
            data = Packet.build(command, subcommand=command, payload=payload, header=0xDF).to_bytes()
            ack = Packet.build(command, version=0, payload=b"\x09\x01", header=0xFD).to_bytes()
            return [data, ack]

        if command in {0x18, 0x19, 0x1A}:
            return [Packet.build(command, version=0, payload=b"\x00\x02\x09\x01", header=0xFD).to_bytes()]

        self.state.unknown_commands.add(command)
        return [Packet.build(command, version=0, payload=b"\x00\x02\x09\x00", header=0xFD).to_bytes()]


async def serve(host: str, port: int) -> None:
    emulator = G28ProtocolEmulator()

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        print(f"Client connected: {peer}")
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                try:
                    raw = bytes.fromhex(line.decode("ascii").strip())
                    responses = emulator.handle(raw)
                    for response in responses:
                        writer.write(response.hex(" ").upper().encode("ascii") + b"\n")
                    await writer.drain()
                except Exception as exc:
                    writer.write(f"ERROR {type(exc).__name__}: {exc}\n".encode("utf-8"))
                    await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"Client disconnected: {peer}")

    server = await asyncio.start_server(handle_client, host, port)
    addresses = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"Orbis G28 Emulator listening on {addresses}")
    print("Send one hexadecimal frame per line. Ctrl+C to stop.")
    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline G28 protocol emulator")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    try:
        asyncio.run(serve(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
