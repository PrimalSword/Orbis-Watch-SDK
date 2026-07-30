from __future__ import annotations

import io
import struct

from orbis_watch.firmware.btsnoop import (
    BTSNOOP_EPOCH_DELTA_US,
    BTSNOOP_HEADER,
    BTSNOOP_MAGIC,
    BTSNOOP_RECORD,
    HCI_UART_H4,
    iter_att_frames,
    iter_btsnoop,
)


def _record(packet: bytes, *, flags: int = 0) -> bytes:
    return BTSNOOP_RECORD.pack(
        len(packet),
        len(packet),
        flags,
        0,
        BTSNOOP_EPOCH_DELTA_US,
    ) + packet


def _acl(payload: bytes, *, conn: int = 11, pb: int = 2) -> bytes:
    handle_flags = conn | (pb << 12)
    return b"\x02" + struct.pack("<HH", handle_flags, len(payload)) + payload


def test_extracts_att_value() -> None:
    value = b"example-value"
    att = b"\x52" + struct.pack("<H", 0x0012) + value
    l2cap = struct.pack("<HH", len(att), 0x0004) + att
    blob = BTSNOOP_HEADER.pack(BTSNOOP_MAGIC, 1, HCI_UART_H4) + _record(_acl(l2cap))

    frames = list(iter_att_frames(iter_btsnoop(io.BytesIO(blob))))

    assert len(frames) == 1
    assert frames[0].direction == "TX"
    assert frames[0].attribute_handle == 0x0012
    assert frames[0].value == value


def test_reassembles_fragmented_att_value() -> None:
    value = bytes(range(40))
    att = b"\x1B" + struct.pack("<H", 0x0025) + value
    l2cap = struct.pack("<HH", len(att), 0x0004) + att
    first, rest = l2cap[:17], l2cap[17:]
    blob = (
        BTSNOOP_HEADER.pack(BTSNOOP_MAGIC, 1, HCI_UART_H4)
        + _record(_acl(first, pb=2), flags=1)
        + _record(_acl(rest, pb=1), flags=1)
    )

    frames = list(iter_att_frames(iter_btsnoop(io.BytesIO(blob))))

    assert len(frames) == 1
    assert frames[0].direction == "RX"
    assert frames[0].attribute_handle == 0x0025
    assert frames[0].value == value
