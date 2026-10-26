"""Налаштування та історія Remold (%APPDATA%\\Remold) — спільні для вікна програми
та швидкої конвертації з контекстного меню провідника."""
from __future__ import annotations

import datetime
import json
import os
import shutil
from pathlib import Path

import core

_APPDATA = Path(os.environ.get("APPDATA", Path.home()))
DATA_DIR = _APPDATA / "Remold"
# попередні назви програми, найновіша перша
LEGACY_DIRS = [_APPDATA / "Forma", _APPDATA / "Konvertui"]
SETTINGS_FILE = DATA_DIR / "settings.json"
HISTORY_FILE = DATA_DIR / "history.json"
HISTORY_LIMIT = 300

DEFAULT_SETTINGS = {
    "lang": None,                        # None = як мова Windows
    "theme": None,                       # None = як у системі
    "quality": 80,
    "out_dir": "",                       # "" = поруч з оригіналом
    "name_template": "{name}_{format}",
    "video_height": 0,
    "image_max_size": 0,
    "auto_update": True,
    "last_update_check": 0,
    "rules": {"image": "jpg", "audio": "mp3", "video": "mp4",
              "document": "pdf", "data": "xlsx", "archive": "zip"},
}


def migrate_legacy() -> None:
    """Перенести налаштування й історію з папки під старою назвою програми (Forma, Konvertui)."""
    if DATA_DIR.exists():
        return
    legacy = next((d for d in LEGACY_DIRS if d.exists()), None)
    if legacy is None:
        return
    try:
        shutil.copytree(legacy, DATA_DIR)
    except OSError:
        pass


# якість (10–100) -> бітрейт аудіо, кбіт/с; та сама таблиця використовується для оцінки розміру в UI
BITRATE_STEPS = [(25, 96), (45, 128), (65, 192), (85, 256), (100, 320)]


def bitrate_for(quality: int) -> int:
    return next(kbps for limit, kbps in BITRATE_STEPS if quality <= limit)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path: Path, data) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def load_settings() -> dict:
    migrate_legacy()
    stored = load_json(SETTINGS_FILE, {})
    return {**DEFAULT_SETTINGS, **stored,
            "rules": {**DEFAULT_SETTINGS["rules"], **stored.get("rules", {})}}


def options_from(s: dict) -> core.Options:
    """Налаштування інтерфейсу -> параметри конвертації (повзунок якості керує всім)."""
    q = int(s["quality"])
    return core.Options(
        image_quality=q,
        image_max_size=int(s["image_max_size"]),
        audio_bitrate=f"{bitrate_for(q)}k",
        video_quality="high" if q >= 85 else "medium" if q >= 55 else "low",
        video_height=int(s["video_height"]),
    )


def total_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def history_entry(src: Path, target: str, result: Path) -> dict:
    return {
        "name": src.name,
        "from": core.file_ext(src).upper(),
        "to": target.upper(),
        "srcSize": src.stat().st_size,
        "outSize": total_size(result),
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "path": str(result),
    }


def save_settings(partial: dict) -> dict:
    """Злити зміни з налаштуваннями на диску (їх може змінювати інший процес)."""
    settings = load_settings()
    settings.update({k: v for k, v in partial.items() if k in DEFAULT_SETTINGS})
    save_json(SETTINGS_FILE, settings)
    return settings


def append_history(entry: dict) -> list[dict]:
    """Додати запис на початок історії (перечитує файл — його можуть писати кілька процесів)."""
    history = load_json(HISTORY_FILE, [])
    history.insert(0, entry)
    del history[HISTORY_LIMIT:]
    save_json(HISTORY_FILE, history)
    return history
