from __future__ import annotations

from orbis_watch.firmware.triage import analyze_firmware, shannon_entropy


def test_triage_detects_vector_and_signatures(tmp_path) -> None:
    data = bytearray(0x400)
    data[0:4] = (0x20002000).to_bytes(4, "little")
    data[4:8] = (0x08000101).to_bytes(4, "little")
    data[0x100:0x108] = b"\x89PNG\r\n\x1a\n"
    data[0x200:0x20C] = b"FreeRTOS v10"
    path = tmp_path / "candidate.bin"
    path.write_bytes(data)

    report = analyze_firmware(path)

    assert report.size == 0x400
    assert any(hit.name == "PNG" and hit.offset == 0x100 for hit in report.signatures)
    assert report.arm_vector_candidates[0].offset == 0
    assert "FreeRTOS" in report.technology_hints
    assert len(report.sha256) == 64


def test_entropy_boundaries() -> None:
    assert shannon_entropy(b"") == 0.0
    assert shannon_entropy(b"\x00" * 128) == 0.0
    assert 7.9 < shannon_entropy(bytes(range(256))) <= 8.0
