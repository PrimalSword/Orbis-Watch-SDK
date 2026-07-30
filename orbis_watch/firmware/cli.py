from __future__ import annotations

import argparse
import json
from pathlib import Path

from .btsnoop import handle_statistics, read_att_frames, write_jsonl
from .triage import analyze_firmware, write_json, write_markdown


def _parse_int(value: str) -> int:
    return int(value, 0)


def run_btsnoop(args: argparse.Namespace) -> int:
    frames = read_att_frames(args.input)
    if args.direction:
        frames = [frame for frame in frames if frame.direction == args.direction]
    if args.handle is not None:
        frames = [frame for frame in frames if frame.attribute_handle == args.handle]
    if args.orbis_only:
        frames = [frame for frame in frames if frame.looks_like_orbis]

    count = write_jsonl(frames, args.output)
    print(f"Extracted {count} ATT frames to {Path(args.output).resolve()}")
    print(json.dumps(handle_statistics(frames), indent=2, ensure_ascii=False))

    if args.stream:
        stream = b"".join(frame.value for frame in frames)
        stream_path = Path(args.stream)
        stream_path.parent.mkdir(parents=True, exist_ok=True)
        stream_path.write_bytes(stream)
        print(
            f"Wrote {len(stream)} raw ATT value bytes to {stream_path.resolve()} "
            "(transport stream, not yet a validated firmware image)"
        )
    return 0


def run_triage(args: argparse.Namespace) -> int:
    report = analyze_firmware(args.input)
    print(f"File: {report.path}")
    print(f"Size: {report.size} bytes")
    print(f"SHA-256: {report.sha256}")
    print(f"Entropy: {report.entropy:.4f} bits/byte")
    print(f"Signatures: {len(report.signatures)}")
    print(f"ARM vector candidates: {len(report.arm_vector_candidates)}")
    print(f"Technology hints: {', '.join(report.technology_hints) or 'none'}")

    if args.json:
        write_json(report, args.json)
        print(f"JSON report: {Path(args.json).resolve()}")
    if args.markdown:
        write_markdown(report, args.markdown)
        print(f"Markdown report: {Path(args.markdown).resolve()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orbis-firmware",
        description="Offline BTSnoop extraction and firmware triage for Orbis Watch SDK",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser(
        "btsnoop",
        help="Extract ATT writes and notifications from an Android Bluetooth HCI snoop log",
    )
    capture.add_argument("input", help="Path to btsnoop_hci.log")
    capture.add_argument("--output", default="orbis_att_capture.jsonl", help="Output JSONL path")
    capture.add_argument("--stream", help="Optional concatenated raw ATT value stream")
    capture.add_argument(
        "--handle",
        type=_parse_int,
        help="Filter one ATT attribute handle (for example 0x0012)",
    )
    capture.add_argument("--direction", choices=("TX", "RX"), help="Filter host direction")
    capture.add_argument(
        "--orbis-only",
        action="store_true",
        help="Keep values beginning with DF or FD",
    )
    capture.set_defaults(func=run_btsnoop)

    triage = subparsers.add_parser(
        "triage",
        help="Run static triage on a candidate firmware binary",
    )
    triage.add_argument("input", help="Candidate firmware or transfer stream")
    triage.add_argument("--json", default="firmware_report.json", help="JSON report path")
    triage.add_argument(
        "--markdown",
        default="firmware_report.md",
        help="Markdown report path",
    )
    triage.set_defaults(func=run_triage)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
