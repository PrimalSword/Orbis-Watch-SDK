from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

MODULE_PATH = Path(__file__).parents[1] / "windows" / "orbis_g28_recovery_studio" / "ota_protocol.py"
spec = spec_from_file_location("ota_protocol", MODULE_PATH)
assert spec and spec.loader
module = module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_handshake_frame_exact() -> None:
    frame = module.build_request(0x0F, protocol_version=1, payload=b"\x10\x00")
    assert frame.hex().upper() == "D50F010100000000F800021000"
    assert module.validate_request(frame)


def test_identity_frame_exact() -> None:
    frame = module.build_request(0x01, protocol_version=1)
    assert frame.hex().upper() == "D501010100000000D80000"
    assert module.validate_request(frame)


def test_identity_parser() -> None:
    payload = bytes.fromhex("6800A4B00456312E3503473238")
    identity = module.parse_identity(payload)
    assert identity.prefix_hex == "6800A4B0"
    assert identity.version == "V1.5"
    assert identity.project == "G28"
    assert identity.unique_code == "6800A4B00456312E3503473238"


def test_fragmented_d6_response() -> None:
    frame = bytes.fromhex("D60F0101000000000456312E31")
    parser = module.D6StreamParser()
    assert parser.feed(frame[:5]) == []
    assert parser.feed(frame[5:]) == [frame]
    response = module.parse_response(frame)
    assert response.command == 0x0F
    assert response.status == 1
    assert response.payload == b"V1.1"
