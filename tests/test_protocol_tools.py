import json
from pathlib import Path

from orbis_watch.protocol.packet import Packet
from orbis_watch.protocol_tools import decode_frame, diff_captures, filter_records


def test_decode_device_info_request():
    raw = Packet.build(0xF3).to_bytes()
    decoded = decode_frame(raw)
    assert decoded.valid is True
    assert decoded.command == 0xF3
    assert decoded.frame_type == "DATA"
    assert decoded.length == 9


def test_filter_records_by_command_and_direction():
    f3 = Packet.build(0xF3).to_bytes().hex().upper()
    f19 = Packet.build(0x19).to_bytes().hex().upper()
    records = [
        {"direction": "TX", "hex": f3},
        {"direction": "RX", "hex": f19},
    ]
    assert filter_records(records, "tx cmd=0xF3") == [records[0]]
    assert filter_records(records, "rx") == [records[1]]


def test_diff_captures(tmp_path: Path):
    f3 = Packet.build(0xF3).to_bytes().hex().upper()
    f19 = Packet.build(0x19).to_bytes().hex().upper()
    left = tmp_path / "left.jsonl"
    right = tmp_path / "right.jsonl"
    left.write_text(json.dumps({"direction": "TX", "hex": f3}) + "\n", encoding="utf-8")
    right.write_text(
        json.dumps({"direction": "TX", "hex": f3}) + "\n" +
        json.dumps({"direction": "TX", "hex": f19}) + "\n",
        encoding="utf-8",
    )
    result = diff_captures(left, right)
    assert result["right_records"] == 2
    assert result["command_delta"]["0x19"] == 1
