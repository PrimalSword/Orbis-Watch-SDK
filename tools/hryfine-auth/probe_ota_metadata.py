from __future__ import annotations

import hashlib
import json
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path


ENDPOINT = "https://ota.lianhezhuli.com/api/hry/get_update"
APP_ID = "oaa648257e8"
SECRET = "ead8ff5fe2f9385b55e6e509cf311a35"
PREFIX = bytes.fromhex("6800A4B0")
PROJECT = "G28"
VERSIONS = ["V0.1", "V1.0", "V1.1", "V1.2", "V1.3", "V1.4", "V1.5"]


def unique_code(version: str) -> str:
    version_bytes = version.encode("utf-8")
    project_bytes = PROJECT.encode("utf-8")
    payload = (
        PREFIX
        + bytes([len(version_bytes)])
        + version_bytes
        + bytes([len(project_bytes)])
        + project_bytes
    )
    return payload.hex().upper()


def signed_params(code: str) -> dict[str, str]:
    params = {
        "appid": APP_ID,
        "bundle_id": "3",
        "lang": "pt",
        "nonce": str(random.SystemRandom().randint(10_000, 1_009_999)),
        "unique_code": code,
        "timestamp": str(int(time.time())),
    }
    canonical = "".join(
        f"{key}={params[key]}&"
        for key in sorted(params)
        if params[key] not in {"", "0"}
    ) + f"key={SECRET}"
    params["sign"] = hashlib.md5(canonical.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
    return params


def request_metadata(version: str) -> dict[str, object]:
    code = unique_code(version)
    params = signed_params(code)
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "HryFine/3.8.9 OrbisOTA-MetadataProbe/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read(4 * 1024 * 1024)
            text = raw.decode("utf-8", errors="replace")
            try:
                payload: object = json.loads(text)
            except json.JSONDecodeError:
                payload = {"raw": text}
            return {
                "version": version,
                "unique_code": code,
                "http_status": response.status,
                "response": payload,
            }
    except Exception as error:  # Preserve evidence without failing the whole matrix.
        return {
            "version": version,
            "unique_code": code,
            "error": f"{type(error).__name__}: {error}",
        }


def main() -> None:
    output = Path("work/ota/metadata-probe.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for version in VERSIONS:
        results.append(request_metadata(version))
        time.sleep(1.0)
    output.write_text(
        json.dumps(
            {
                "endpoint": ENDPOINT,
                "project": PROJECT,
                "prefix_hex": PREFIX.hex().upper(),
                "read_only": True,
                "downloaded_firmware": False,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
