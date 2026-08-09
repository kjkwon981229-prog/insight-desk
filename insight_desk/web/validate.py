from __future__ import annotations

import json
import re
from pathlib import Path

REQUIRED_FILES = (
    "index.html",
    "latest/index.html",
    "archive/index.html",
    "data/latest.json",
    "assets/css/style.css",
    "manifest.webmanifest",
    "assets/icons/icon-192.png",
    "assets/icons/icon-512.png",
    "assets/icons/apple-touch-icon.png",
    "assets/icons/favicon.png",
)
_LOCAL_HREF = re.compile(r'href=["\']([^"\'#]+)["\']')


def validate_artifact(site_dir: Path, *, secrets: tuple[str, ...] = ()) -> tuple[str, ...]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        path = site_dir / relative
        if not path.is_file():
            errors.append(f"missing required file: {relative}")
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".ico"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"not valid UTF-8: {relative}")
            continue
        for secret in secrets:
            if secret and secret in text:
                errors.append(f"secret detected in artifact: {relative}")
        if relative.endswith(".html"):
            if "charset=\"utf-8\"" not in text.lower():
                errors.append(f"missing UTF-8 declaration: {relative}")
            if "width=device-width" not in text:
                errors.append(f"missing mobile viewport: {relative}")
            for marker in (
                "rel=\"manifest\"",
                "rel=\"icon\"",
                "rel=\"apple-touch-icon\"",
                "theme-color",
                "apple-mobile-web-app-capable",
            ):
                if marker not in text:
                    errors.append(f"missing PWA head contract ({marker}): {relative}")

    manifest_path = site_dir / "manifest.webmanifest"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for key, expected in (("display", "standalone"), ("name", "Insight Desk"), ("short_name", "Insight Desk")):
                if manifest.get(key) != expected:
                    errors.append(f"invalid manifest {key}: {expected}")
            if manifest.get("x-icon-status") != "APPROVED_CANDIDATE_5_EXTRACTED":
                errors.append("manifest icon provenance is not the approved Candidate 5 asset")
            icons = manifest.get("icons")
            if not isinstance(icons, list) or not icons:
                errors.append("manifest icons are missing")
            else:
                for icon in icons:
                    if not isinstance(icon, dict) or not isinstance(icon.get("src"), str):
                        errors.append("manifest icon entry is invalid")
                        continue
                    icon_path = site_dir / icon["src"]
                    if not icon_path.is_file():
                        errors.append(f"missing manifest icon: {icon['src']}")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            errors.append("invalid manifest.webmanifest")

    for html_path in site_dir.rglob("*.html"):
        try:
            html_text = html_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(marker in html_text for marker in ("/workspace/", "/home/runner/", "\\workspace\\")):
            errors.append(f"local filesystem path exposed: {html_path.relative_to(site_dir)}")
        for href in _LOCAL_HREF.findall(html_text):
            if href.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            target = (html_path.parent / href).resolve()
            if site_dir.resolve() not in target.parents and target != site_dir.resolve():
                errors.append(f"local link escapes artifact: {href}")
            elif not target.exists():
                errors.append(f"broken local link: {href}")
    css_path = site_dir / "assets/css/style.css"
    if css_path.is_file():
        css = css_path.read_text(encoding="utf-8")
        if "overflow-x: hidden" not in css or "max-width" not in css:
            errors.append("mobile overflow guard is missing")
    return tuple(errors)
