from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SignatureHit:
    name: str
    offset: int


@dataclass(frozen=True, slots=True)
class ArmVectorCandidate:
    offset: int
    initial_sp: int
    reset_vector: int


@dataclass(frozen=True, slots=True)
class FirmwareReport:
    path: str
    size: int
    sha256: str
    entropy: float
    signatures: tuple[SignatureHit, ...]
    arm_vector_candidates: tuple[ArmVectorCandidate, ...]
    technology_hints: tuple[str, ...]
    strings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_SIGNATURES: tuple[tuple[str, bytes], ...] = (
    ("ELF", b"\x7fELF"),
    ("ZIP", b"PK\x03\x04"),
    ("GZIP", b"\x1f\x8b\x08"),
    ("PNG", b"\x89PNG\r\n\x1a\n"),
    ("JPEG", b"\xff\xd8\xff"),
    ("LZ4_FRAME", b"\x04\x22\x4d\x18"),
    ("LZ4_LEGACY", b"\x02\x21\x4c\x18"),
    ("SQUASHFS_LE", b"hsqs"),
    ("SQUASHFS_BE", b"sqsh"),
    ("UF2", b"UF2\n"),
    ("ANDROID_BOOT_IMAGE", b"ANDROID!"),
    ("U_BOOT_UIMAGE", b"\x27\x05\x19\x56"),
)

_HINTS: tuple[tuple[str, tuple[bytes, ...]], ...] = (
    ("FreeRTOS", (b"FreeRTOS", b"vTaskStartScheduler")),
    ("Zephyr", (b"Zephyr", b"ZEPHYR")),
    ("RT-Thread", (b"RT-Thread", b"rt_thread")),
    ("LVGL", (b"LVGL", b"lv_obj_", b"lv_disp_")),
    ("Nordic/nRF", (b"Nordic", b"nRF", b"SoftDevice")),
    ("JieLi/JL", (b"JieLi", b"Jieli", b"JL_AC", b"JL701")),
    ("Realtek", (b"Realtek", b"RTL87", b"Ameba")),
    ("BES", (b"Bestechnic", b"BES2", b"BES3")),
    ("Actions", (b"Actions Semi", b"ATS3")),
    ("Tuya", (b"Tuya", b"TUYA")),
)


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for value in data:
        counts[value] += 1
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in counts if count)


def find_signatures(data: bytes, *, max_hits_per_type: int = 16) -> tuple[SignatureHit, ...]:
    hits: list[SignatureHit] = []
    for name, magic in _SIGNATURES:
        start = 0
        found = 0
        while found < max_hits_per_type:
            offset = data.find(magic, start)
            if offset < 0:
                break
            hits.append(SignatureHit(name=name, offset=offset))
            start = offset + 1
            found += 1
    return tuple(sorted(hits, key=lambda hit: (hit.offset, hit.name)))


def find_arm_vector_candidates(data: bytes, *, scan_limit: int = 1 << 20) -> tuple[ArmVectorCandidate, ...]:
    candidates: list[ArmVectorCandidate] = []
    upper = min(len(data) - 8, scan_limit)
    if upper < 0:
        return ()

    # Vector tables usually begin at aligned image/partition boundaries. Scan
    # 0x100-byte boundaries to avoid producing thousands of weak matches.
    for offset in range(0, upper + 1, 0x100):
        initial_sp = int.from_bytes(data[offset : offset + 4], "little")
        reset_vector = int.from_bytes(data[offset + 4 : offset + 8], "little")
        sp_plausible = 0x2000_0000 <= initial_sp < 0x4000_0000 and initial_sp % 4 == 0
        reset_plausible = bool(reset_vector & 1) and (
            0x0000_0001 <= reset_vector < 0x2000_0000
            or 0x0800_0001 <= reset_vector < 0x1000_0000
        )
        if sp_plausible and reset_plausible:
            candidates.append(
                ArmVectorCandidate(
                    offset=offset,
                    initial_sp=initial_sp,
                    reset_vector=reset_vector,
                )
            )
    return tuple(candidates[:64])


def extract_ascii_strings(data: bytes, *, minimum: int = 6, limit: int = 200) -> tuple[str, ...]:
    pattern = re.compile(rb"[\x20-\x7e]{%d,}" % minimum)
    strings: list[str] = []
    for match in pattern.finditer(data):
        value = match.group().decode("ascii", errors="replace")
        strings.append(value[:240])
        if len(strings) >= limit:
            break
    return tuple(strings)


def technology_hints(data: bytes) -> tuple[str, ...]:
    lower = data.lower()
    found: list[str] = []
    for name, needles in _HINTS:
        if any(needle.lower() in lower for needle in needles):
            found.append(name)
    return tuple(found)


def analyze_firmware(path: str | Path) -> FirmwareReport:
    source = Path(path)
    data = source.read_bytes()
    return FirmwareReport(
        path=str(source.resolve()),
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        entropy=shannon_entropy(data),
        signatures=find_signatures(data),
        arm_vector_candidates=find_arm_vector_candidates(data),
        technology_hints=technology_hints(data),
        strings=extract_ascii_strings(data),
    )


def write_json(report: FirmwareReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown(report: FirmwareReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Firmware triage report",
        "",
        f"- File: `{report.path}`",
        f"- Size: `{report.size}` bytes",
        f"- SHA-256: `{report.sha256}`",
        f"- Shannon entropy: `{report.entropy:.4f}` bits/byte",
        "",
        "## Signatures",
        "",
    ]
    if report.signatures:
        lines.extend(f"- `{hit.name}` at `0x{hit.offset:X}`" for hit in report.signatures)
    else:
        lines.append("No known file signatures detected.")

    lines.extend(["", "## ARM Cortex-M vector-table candidates", ""])
    if report.arm_vector_candidates:
        lines.extend(
            f"- offset `0x{item.offset:X}`: SP=`0x{item.initial_sp:08X}`, reset=`0x{item.reset_vector:08X}`"
            for item in report.arm_vector_candidates
        )
    else:
        lines.append("No plausible vector table detected by the conservative heuristic.")

    lines.extend(["", "## Technology strings (hints only)", ""])
    if report.technology_hints:
        lines.extend(f"- {hint}" for hint in report.technology_hints)
    else:
        lines.append("No known RTOS/vendor/UI-library strings detected.")

    lines.extend(["", "## Printable strings", ""])
    if report.strings:
        for value in report.strings:
            safe_value = value.replace("`", "'")
            lines.append(f"- `{safe_value}`")
    else:
        lines.append("No printable ASCII strings found.")

    lines.extend(
        [
            "",
            "> This is static triage, not proof of processor family, firmware validity, or flashability.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")
