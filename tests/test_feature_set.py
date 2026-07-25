import pytest

from orbis_watch.models.feature_set import FeatureSet


def test_feature_set_decodes_little_endian_bits() -> None:
    features = FeatureSet.from_bytes(bytes([0b10000001, 0b00000010]), acknowledged=True)

    assert features.acknowledged is True
    assert features.hex == "81 02"
    assert features.bit_count == 16
    assert features.enabled_bits == (0, 7, 9)
    assert features.supports_bit(0) is True
    assert features.supports_bit(1) is False
    assert features.supports_bit(9) is True


def test_feature_set_rejects_empty_bitmap() -> None:
    with pytest.raises(ValueError, match="empty"):
        FeatureSet.from_bytes(b"")


def test_feature_set_rejects_out_of_range_bit() -> None:
    features = FeatureSet.from_bytes(b"\x01")

    with pytest.raises(IndexError):
        features.supports_bit(8)
