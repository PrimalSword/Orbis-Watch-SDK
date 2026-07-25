from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FeatureSet:
    """Raw feature bitmap exposed by the watch through GATT characteristic 0x2A28.

    Named flags will be added only after each bit position is validated on real
    hardware. Until then, the model preserves the complete bitmap and offers
    deterministic bit-level inspection without guessing protocol semantics.
    """

    raw: bytes
    acknowledged: bool = False

    @classmethod
    def from_bytes(cls, data: bytes, *, acknowledged: bool = False) -> "FeatureSet":
        if not data:
            raise ValueError("Feature bitmap is empty")
        return cls(raw=bytes(data), acknowledged=acknowledged)

    @property
    def hex(self) -> str:
        return self.raw.hex(" ").upper()

    @property
    def bit_count(self) -> int:
        return len(self.raw) * 8

    def supports_bit(self, bit: int) -> bool:
        """Return whether a zero-based, little-endian bit is enabled.

        Bit 0 is the least-significant bit of byte 0, bit 8 is the
        least-significant bit of byte 1, and so on.
        """
        if bit < 0 or bit >= self.bit_count:
            raise IndexError(f"Feature bit {bit} is outside 0..{self.bit_count - 1}")
        byte_index, bit_index = divmod(bit, 8)
        return bool(self.raw[byte_index] & (1 << bit_index))

    @property
    def enabled_bits(self) -> tuple[int, ...]:
        return tuple(bit for bit in range(self.bit_count) if self.supports_bit(bit))

    def __str__(self) -> str:
        return (
            f"FeatureSet(bytes={len(self.raw)}, acknowledged={self.acknowledged}, "
            f"hex='{self.hex}', enabled_bits={self.enabled_bits})"
        )
