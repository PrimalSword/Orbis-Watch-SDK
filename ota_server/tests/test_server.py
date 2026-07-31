from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient


def load_server(tmp_path: Path, monkeypatch):
    manifest_dir = tmp_path / "manifests"
    firmware_dir = tmp_path / "firmware"
    manifest_dir.mkdir()
    firmware_dir.mkdir()
    monkeypatch.setenv("ORBIS_OTA_MANIFEST_DIR", str(manifest_dir))
    monkeypatch.setenv("ORBIS_OTA_FIRMWARE_DIR", str(firmware_dir))
    monkeypatch.delenv("ORBIS_OTA_TOKEN", raising=False)

    spec = importlib.util.spec_from_file_location(
        "orbis_ota_server_under_test",
        Path(__file__).parents[1] / "server.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module, manifest_dir, firmware_dir


def test_health_is_read_only(tmp_path, monkeypatch):
    module, _, _ = load_server(tmp_path, monkeypatch)
    client = TestClient(module.app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["transport_authorized"] is False


def test_missing_manifest_returns_no_update(tmp_path, monkeypatch):
    module, _, _ = load_server(tmp_path, monkeypatch)
    client = TestClient(module.app)
    response = client.get(
        "/api/v1/ota/check",
        params={"project": "G28", "current_version": "V1.5"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["update_available"] is False
    assert body["data"]["bin_list"] == []
    assert body["data"]["transport_authorized"] is False


def test_enabled_firmware_is_hashed_and_exposed(tmp_path, monkeypatch):
    module, manifests, firmware = load_server(tmp_path, monkeypatch)
    firmware_bytes = b"orbis-g28-test-firmware"
    (firmware / "G28_V1.6.bin").write_bytes(firmware_bytes)
    (manifests / "G28.json").write_text(
        json.dumps(
            {
                "project": "G28",
                "releases": [
                    {
                        "project": "G28",
                        "version": "V1.6",
                        "filename": "G28_V1.6.bin",
                        "enabled": True,
                        "notes": "fixture",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(module.app)
    response = client.get(
        "/api/v1/ota/check",
        params={"project": "G28", "current_version": "V1.5"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["update_available"] is True
    release = body["data"]["bin_list"][0]
    assert release["project"] == "G28"
    assert release["version"] == "V1.6"
    assert release["file_size"] == len(firmware_bytes)
    assert len(release["md5"]) == 32
    assert len(release["sha256"]) == 64
    assert release["transport_authorized"] is False

    download = client.get("/firmware/G28_V1.6.bin")
    assert download.status_code == 200
    assert download.content == firmware_bytes


def test_disabled_release_never_becomes_available(tmp_path, monkeypatch):
    module, manifests, firmware = load_server(tmp_path, monkeypatch)
    (firmware / "G28_V1.6.bin").write_bytes(b"disabled")
    (manifests / "G28.json").write_text(
        json.dumps(
            {
                "project": "G28",
                "releases": [
                    {
                        "project": "G28",
                        "version": "V1.6",
                        "filename": "G28_V1.6.bin",
                        "enabled": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(module.app)
    body = client.get(
        "/api/v1/ota/check",
        params={"project": "G28", "current_version": "V1.5"},
    ).json()
    assert body["data"]["update_available"] is False
    assert body["data"]["bin_list"] == []
    assert body["data"]["skipped"] == [{"version": "V1.6", "reason": "disabled"}]


def test_path_traversal_is_rejected(tmp_path, monkeypatch):
    module, _, _ = load_server(tmp_path, monkeypatch)
    client = TestClient(module.app)
    response = client.get("/firmware/%2E%2E%2Fsecret.bin")
    assert response.status_code in {400, 404}
