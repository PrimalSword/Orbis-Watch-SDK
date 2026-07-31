from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator


APP_VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parent
MANIFEST_DIR = Path(
    os.environ.get("ORBIS_OTA_MANIFEST_DIR", ROOT / "manifests")
).expanduser().resolve()
FIRMWARE_DIR = Path(
    os.environ.get("ORBIS_OTA_FIRMWARE_DIR", ROOT / "firmware")
).expanduser().resolve()
API_TOKEN = os.environ.get("ORBIS_OTA_TOKEN", "").strip()
PROJECT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,180}$")

app = FastAPI(
    title="Orbis Watch OTA Server",
    version=APP_VERSION,
    description=(
        "Catálogo e distribuição verificável de firmware. "
        "Esta versão não autoriza gravação BLE no relógio."
    ),
)


class FirmwareRelease(BaseModel):
    project: str
    version: str = Field(min_length=1, max_length=64)
    filename: str
    enabled: bool = False
    notes: str = Field(default="", max_length=500)
    signature_required: bool | None = None

    @field_validator("project")
    @classmethod
    def validate_project(cls, value: str) -> str:
        if not PROJECT_PATTERN.fullmatch(value):
            raise ValueError("invalid project identifier")
        return value

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if not FILENAME_PATTERN.fullmatch(value):
            raise ValueError("filename must not contain directories or special characters")
        return value


class ProjectManifest(BaseModel):
    project: str
    releases: list[FirmwareRelease] = Field(default_factory=list)

    @field_validator("project")
    @classmethod
    def validate_project(cls, value: str) -> str:
        if not PROJECT_PATTERN.fullmatch(value):
            raise ValueError("invalid project identifier")
        return value


ProjectManifest.model_rebuild()


def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Require a bearer token only when ORBIS_OTA_TOKEN is configured."""
    if not API_TOKEN:
        return
    expected = f"Bearer {API_TOKEN}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=401,
            detail="invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def safe_manifest_path(project: str) -> Path:
    if not PROJECT_PATTERN.fullmatch(project):
        raise HTTPException(status_code=400, detail="invalid project identifier")
    path = (MANIFEST_DIR / f"{project}.json").resolve()
    if path.parent != MANIFEST_DIR:
        raise HTTPException(status_code=400, detail="invalid manifest path")
    return path


def safe_firmware_path(filename: str) -> Path:
    if not FILENAME_PATTERN.fullmatch(filename):
        raise HTTPException(status_code=400, detail="invalid firmware filename")
    path = (FIRMWARE_DIR / filename).resolve()
    if path.parent != FIRMWARE_DIR:
        raise HTTPException(status_code=400, detail="invalid firmware path")
    return path


def load_manifest(project: str) -> ProjectManifest:
    path = safe_manifest_path(project)
    if not path.is_file():
        return ProjectManifest(project=project, releases=[])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = ProjectManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"invalid manifest for project {project}: {error}",
        ) from error
    if manifest.project != project:
        raise HTTPException(status_code=500, detail="manifest project mismatch")
    for release in manifest.releases:
        if release.project != project:
            raise HTTPException(status_code=500, detail="release project mismatch")
    return manifest


def file_hashes(path: Path) -> dict[str, Any]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            md5.update(chunk)
            sha256.update(chunk)
    return {
        "size": size,
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest(),
    }


def resolved_release(release: FirmwareRelease, request: Request) -> dict[str, Any] | None:
    path = safe_firmware_path(release.filename)
    if not path.is_file():
        return None
    hashes = file_hashes(path)
    base_url = str(request.base_url).rstrip("/")
    return {
        "project": release.project,
        "version": release.version,
        "filename": release.filename,
        "file_url": f"{base_url}/firmware/{release.filename}",
        "file_size": hashes["size"],
        "md5": hashes["md5"],
        "sha256": hashes["sha256"],
        "notes": release.notes,
        "signature_required": release.signature_required,
        "transport_authorized": False,
    }


def build_check_response(
    *,
    project: str,
    current_version: str,
    request: Request,
) -> dict[str, Any]:
    manifest = load_manifest(project)
    bins: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for release in manifest.releases:
        if not release.enabled:
            skipped.append({"version": release.version, "reason": "disabled"})
            continue
        if release.version == current_version:
            skipped.append({"version": release.version, "reason": "already_current"})
            continue
        resolved = resolved_release(release, request)
        if resolved is None:
            skipped.append({"version": release.version, "reason": "file_missing"})
            continue
        bins.append(resolved)

    return {
        "code": "ok",
        "msg": "",
        "data": {
            "project": project,
            "current_version": current_version,
            "update_available": bool(bins),
            "bin_list": bins,
            "skipped": skipped,
            "transport_authorized": False,
            "transport_reason": (
                "metadata-and-download-only; BLE firmware writes remain disabled "
                "until the G28 5610 transfer protocol and firmware authenticity are validated"
            ),
        },
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "orbis-watch-ota",
        "version": APP_VERSION,
        "manifest_dir": str(MANIFEST_DIR),
        "firmware_dir": str(FIRMWARE_DIR),
        "auth_enabled": bool(API_TOKEN),
        "transport_authorized": False,
    }


@app.get("/api/v1/ota/check", dependencies=[Depends(require_auth)])
@app.get("/api/ota/check", dependencies=[Depends(require_auth)], include_in_schema=False)
def check_update(
    request: Request,
    project: str = Query(min_length=1, max_length=64),
    current_version: str = Query(default="", max_length=64),
    unique_code: str = Query(default="", max_length=512),
) -> dict[str, Any]:
    # Accepted for client compatibility, but not logged, persisted or used as a secret.
    del unique_code
    return build_check_response(
        project=project,
        current_version=current_version,
        request=request,
    )


@app.get("/api/v1/ota/manifest/{project}", dependencies=[Depends(require_auth)])
def get_manifest(project: str, request: Request) -> dict[str, Any]:
    manifest = load_manifest(project)
    releases: list[dict[str, Any]] = []
    for release in manifest.releases:
        item = release.model_dump()
        resolved = resolved_release(release, request)
        item["file_present"] = resolved is not None
        if resolved is not None:
            item.update(
                {
                    "file_url": resolved["file_url"],
                    "file_size": resolved["file_size"],
                    "md5": resolved["md5"],
                    "sha256": resolved["sha256"],
                }
            )
        item["transport_authorized"] = False
        releases.append(item)
    return {
        "code": "ok",
        "msg": "",
        "data": {
            "project": project,
            "releases": releases,
            "transport_authorized": False,
        },
    }


@app.get("/firmware/{filename}", dependencies=[Depends(require_auth)])
def download_firmware(filename: str) -> FileResponse:
    path = safe_firmware_path(filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="firmware not found")
    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=filename,
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )
