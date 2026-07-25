from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    firmware: str
    project: str
    model: str | None = None
    screen_width: int | None = None
    screen_height: int | None = None

    @classmethod
    def from_payload(cls, payload: bytes) -> "DeviceInfo":
        if not payload:
            raise ValueError("Device info payload is empty")

        firmware_length = payload[0]
        firmware_end = 1 + firmware_length
        if len(payload) <= firmware_end:
            raise ValueError("Device info payload is truncated before project length")

        firmware = payload[1:firmware_end].decode("utf-8", errors="replace")
        project_length = payload[firmware_end]
        project_start = firmware_end + 1
        project_end = project_start + project_length
        if len(payload) < project_end:
            raise ValueError("Device info payload is truncated inside project name")

        project = payload[project_start:project_end].decode("utf-8", errors="replace")
        model_match = re.search(r"\[([^\]]+)\]", project)
        screen_match = re.search(r"(\d{2,4})x(\d{2,4})", project)

        return cls(
            firmware=firmware,
            project=project,
            model=model_match.group(1) if model_match else None,
            screen_width=int(screen_match.group(1)) if screen_match else None,
            screen_height=int(screen_match.group(2)) if screen_match else None,
        )
