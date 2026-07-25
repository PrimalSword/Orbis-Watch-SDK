from __future__ import annotations

from dataclasses import dataclass


# Commands known or strongly suspected to mutate persistent state, firmware,
# settings, or watchfaces. They are blocked unless the operator explicitly
# enables unsafe mode and confirms the exact operation.
DANGEROUS_COMMANDS: dict[int, str] = {
    0x01: "OTA / firmware transfer",
    0x02: "device settings",
    0x0F: "watchface transfer",
}

# Raw frames are treated conservatively. Only DF protocol requests are accepted
# by default; malformed or non-DF traffic requires unsafe mode.


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    allowed: bool
    reason: str = ""
    command: int | None = None


def inspect_raw_frame(data: bytes, *, unsafe: bool = False) -> SafetyDecision:
    if not data:
        return SafetyDecision(False, "empty frame")
    if unsafe:
        command = data[4] if len(data) > 4 else None
        return SafetyDecision(True, command=command)
    if len(data) < 9:
        return SafetyDecision(False, "frame shorter than 9 bytes; use --unsafe to override")
    if data[0] != 0xDF:
        return SafetyDecision(False, "only DF request frames are allowed in safe mode")
    command = data[4]
    if command in DANGEROUS_COMMANDS:
        return SafetyDecision(False, f"command 0x{command:02X} is blocked: {DANGEROUS_COMMANDS[command]}", command)
    return SafetyDecision(True, command=command)


def command_is_dangerous(command: int) -> bool:
    return command in DANGEROUS_COMMANDS
