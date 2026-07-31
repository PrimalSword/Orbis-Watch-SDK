from __future__ import annotations

import html
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
MAX_APK_BYTES = 160 * 1024 * 1024
TARGETS = {
    "3.5.2": [
        "https://hryfine.apk.watch/3.5.2",
        "https://apkcombo.com/hryfine/com.lianhezhuli.hyfit/download/phone-3.5.2-apk",
        "https://d.apkpure.net/b/APK/com.lianhezhuli.hyfit?version=3.5.2",
    ],
    "3.7.0": [
        "https://hryfine.apk.watch/3.7.0",
        "https://apkcombo.com/hryfine/com.lianhezhuli.hyfit/download/phone-3.7.0-apk",
        "https://d.apkpure.net/b/APK/com.lianhezhuli.hyfit?version=3.7.0",
    ],
}


def request(url: str, *, referer: str | None = None) -> urllib.request.Request:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/vnd.android.package-archive,application/octet-stream;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    return urllib.request.Request(url, headers=headers)


def fetch(url: str, *, referer: str | None = None, limit: int = MAX_APK_BYTES) -> tuple[str, bytes, str]:
    context = ssl.create_default_context()
    with urllib.request.urlopen(request(url, referer=referer), timeout=45, context=context) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError(f"response exceeds {limit} bytes")
        return response.geturl(), data, response.headers.get("Content-Type", "")


def is_apk(data: bytes) -> bool:
    if len(data) < 4 or data[:2] != b"PK":
        return False
    try:
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
            return "AndroidManifest.xml" in names and any(name.startswith("classes") and name.endswith(".dex") for name in names)
    except zipfile.BadZipFile:
        return False


def candidate_links(page_url: str, body: bytes) -> list[str]:
    text = html.unescape(body.decode("utf-8", errors="replace"))
    text = text.replace("\\/", "/")
    raw: list[str] = []
    patterns = [
        r'''(?:href|src|data-url|data-download|data-link)\s*=\s*["']([^"']+)["']''',
        r'''https?://[^\s"'<>]+''',
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            raw.append(match if isinstance(match, str) else match[0])

    links: list[str] = []
    seen: set[str] = set()
    for item in raw:
        item = item.strip().replace("&amp;", "&")
        if not item or item.startswith(("javascript:", "mailto:", "#")):
            continue
        absolute = urllib.parse.urljoin(page_url, item)
        lower = absolute.lower()
        if not any(token in lower for token in ("apk", "download", "cdn", "file")):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)

    def score(url: str) -> tuple[int, int]:
        lower = url.lower()
        value = 0
        if lower.endswith(".apk") or ".apk?" in lower:
            value += 100
        if "download.apkcombo" in lower or "download.apkpure" in lower or "cdn" in lower:
            value += 50
        if "/download" in lower:
            value += 20
        if "facebook" in lower or "google" in lower or "twitter" in lower:
            value -= 100
        return (-value, len(url))

    return sorted(links, key=score)


def resolve_version(version: str, output_dir: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "requested_version": version,
        "sources": [],
        "downloaded": False,
    }
    attempts: list[dict[str, object]] = []
    page_dir = output_dir / "pages" / version
    page_dir.mkdir(parents=True, exist_ok=True)

    for source_index, source_url in enumerate(TARGETS[version]):
        source_record: dict[str, object] = {"url": source_url}
        attempts.append(source_record)
        try:
            final_url, body, content_type = fetch(source_url)
            source_record.update(
                {
                    "final_url": final_url,
                    "content_type": content_type,
                    "bytes": len(body),
                }
            )
        except Exception as error:
            source_record["error"] = f"{type(error).__name__}: {error}"
            continue

        if is_apk(body):
            apk_path = output_dir / f"HryFine-{version}.apk"
            apk_path.write_bytes(body)
            source_record["resolved_as_apk"] = True
            result.update(
                {
                    "downloaded": True,
                    "apk_path": str(apk_path),
                    "resolved_url": final_url,
                    "source_url": source_url,
                }
            )
            break

        page_path = page_dir / f"source-{source_index}.html"
        page_path.write_bytes(body)
        source_record["page_path"] = str(page_path)
        links = candidate_links(final_url, body)
        source_record["candidate_count"] = len(links)
        source_record["candidate_preview"] = links[:20]

        for candidate in links[:60]:
            candidate_record: dict[str, object] = {"candidate": candidate}
            source_record.setdefault("candidate_attempts", []).append(candidate_record)
            try:
                candidate_final, candidate_body, candidate_type = fetch(
                    candidate,
                    referer=final_url,
                )
                candidate_record.update(
                    {
                        "final_url": candidate_final,
                        "content_type": candidate_type,
                        "bytes": len(candidate_body),
                    }
                )
            except Exception as error:
                candidate_record["error"] = f"{type(error).__name__}: {error}"
                continue
            if not is_apk(candidate_body):
                continue
            apk_path = output_dir / f"HryFine-{version}.apk"
            apk_path.write_bytes(candidate_body)
            candidate_record["resolved_as_apk"] = True
            result.update(
                {
                    "downloaded": True,
                    "apk_path": str(apk_path),
                    "resolved_url": candidate_final,
                    "source_url": source_url,
                }
            )
            break

        if result["downloaded"]:
            break

    result["sources"] = attempts
    return result


def main() -> int:
    output_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "work/history").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [resolve_version(version, output_dir) for version in TARGETS]
    report = {
        "read_only": True,
        "targets": list(TARGETS),
        "results": results,
    }
    report_path = output_dir / "resolve-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
