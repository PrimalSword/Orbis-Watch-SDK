from orbis_watch.constants import CommandID
from orbis_watch.protocol import Packet, PacketStreamParser


def test_build_device_info_packet() -> None:
    packet = Packet.build(CommandID.DEVICE_INFO)
    assert packet.to_bytes() == bytes.fromhex("DF 00 05 D8 F3 01 00 00 00")


def test_parse_device_info_response() -> None:
    raw = bytes.fromhex(
        "DF 00 33 A8 F3 01 F3 00 2E "
        "04 56 31 2E 35 "
        "28 45 30 36 42 5F 47 32 38 5F 57 45 5B 47 32 38 5D "
        "5F 52 53 74 79 6C 65 31 5F 32 34 30 78 32 34 30 5F "
        "48 72 79 46 69 6E 65"
    )
    packet = Packet.parse(raw)
    assert packet.command == CommandID.DEVICE_INFO
    assert packet.subcommand == CommandID.DEVICE_INFO
    assert packet.payload.startswith(b"\x04V1.5")


def test_stream_parser_reassembles_chunks() -> None:
    raw = bytes.fromhex("DF 00 05 FE 19 01 00 00 00")
    parser = PacketStreamParser()
    assert parser.feed(raw[:4]) == []
    packets = parser.feed(raw[4:])
    assert len(packets) == 1
    assert packets[0].command == CommandID.GET_FEATURE
