"""Список змін Remold (changelog.json): що змінилося між версіями.

Один файл — для трьох місць:
* вікно «Що нового» в програмі (desktop.py → webui);
* опис релізу на GitHub:  python changelog.py --release-notes 2.1.0 > notes.md
* попередній перегляд оновлення: програма завантажує changelog.json з тегу нової версії.

Формат запису (найновіша версія перша):
    {"version": "2.1.0", "date": "2026-11-15",
     "changes": [{"type": "new" | "improved" | "fix", "uk": "…", "en": "…"}]}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import version

FILE_NAME = "changelog.json"
TYPES = ("new", "improved", "fix")


def _path() -> Path:
    # у зібраному exe (PyInstaller) дані лежать у sys._MEIPASS
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / FILE_NAME


def _clean(entries) -> list[dict]:
    """Залишити лише коректні записи (файл з мережі не повинен зламати інтерфейс)."""
    out = []
    if not isinstance(entries, list):
        return out
    for e in entries:
        if not isinstance(e, dict) or not isinstance(e.get("version"), str):
            continue
        changes = []
        for c in e.get("changes") or []:
            if isinstance(c, dict) and (isinstance(c.get("uk"), str) or isinstance(c.get("en"), str)):
                changes.append({"type": c.get("type") if c.get("type") in TYPES else "improved",
                                "uk": c.get("uk") or c.get("en"), "en": c.get("en") or c.get("uk")})
        out.append({"version": e["version"].lstrip("vV"), "date": str(e.get("date") or ""), "changes": changes})
    return out


def load() -> list[dict]:
    try:
        return _clean(json.loads(_path().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return []


def fetch_remote(ver: str) -> list[dict]:
    """Записи, новіші за поточну версію, з changelog.json у тезі v<ver> на GitHub."""
    import urllib.request
    from updater import parse_version

    url = f"https://raw.githubusercontent.com/{version.REPO}/v{ver.lstrip('vV')}/{FILE_NAME}"
    req = urllib.request.Request(url, headers={"User-Agent": f"{version.APP_NAME}/{version.__version__}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        entries = _clean(json.loads(resp.read().decode("utf-8")))
    current = parse_version(version.__version__)
    return [e for e in entries if parse_version(e["version"]) > current]


HEADINGS = {
    "uk": {"new": "Нове", "improved": "Покращено", "fix": "Виправлено"},
    "en": {"new": "New", "improved": "Improved", "fix": "Fixed"},
}


def release_notes(ver: str) -> str:
    """Опис релізу на GitHub у Markdown: англійською, а нижче — українською."""
    entry = next((e for e in load() if e["version"] == ver.lstrip("vV")), None)
    if entry is None:
        raise SystemExit(f"changelog.json has no entry for {ver}")
    parts = []
    for lang, title in (("en", "What's new"), ("uk", "Що нового")):
        parts.append(f"## {title}\n")
        for kind in TYPES:
            items = [c[lang] for c in entry["changes"] if c["type"] == kind]
            if items:
                parts.append(f"**{HEADINGS[lang][kind]}**\n")
                parts += [f"- {text}" for text in items]
                parts.append("")
    return "\n".join(parts).rstrip() + "\n"


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--release-notes":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(release_notes(sys.argv[2]))
    else:
        raise SystemExit("usage: python changelog.py --release-notes <version>")
