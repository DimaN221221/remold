"""Рядки, які показує Python-частина (меню провідника, віконце швидкої конвертації, помилки)."""
from __future__ import annotations

STRINGS = {
    "uk": {
        "menu.convert": "Конвертувати в",
        "menu.audioOnly": "{fmt} — лише звук",
        "menu.open": "Відкрити в Remold…",
        "quick.title": "Remold — швидка конвертація",
        "quick.queued": "у черзі…",
        "quick.starting": "підготовка…",
        "quick.done": "готово",
        "quick.cancelled": "скасовано",
        "quick.cancel": "Скасувати",
        "quick.close": "Закрити",
        "quick.error": "помилка",
        "quick.reveal": "Показати в папці",
        "units": "Б,КБ,МБ,ГБ",
        "err.unknown": "Невідомий формат файлу: {name}",
        "err.unsupported": "{src} → {dst} не підтримується",
        "err.ffmpeg": "ffmpeg завершився з помилкою:",
        "dlg.supported": "Усі підтримувані",
        "dlg.all": "Усі файли",
        "upd.noAsset": "у релізі немає файлу {asset}",
        "upd.notGit": "це не git-репозиторій",
        "upd.dirty": "у робочій копії є незбережені зміни",
    },
    "en": {
        "menu.convert": "Convert to",
        "menu.audioOnly": "{fmt} — audio only",
        "menu.open": "Open in Remold…",
        "quick.title": "Remold — quick convert",
        "quick.queued": "waiting…",
        "quick.starting": "starting…",
        "quick.done": "done",
        "quick.cancelled": "cancelled",
        "quick.cancel": "Cancel",
        "quick.close": "Close",
        "quick.error": "failed",
        "quick.reveal": "Show in folder",
        "units": "B,KB,MB,GB",
        "err.unknown": "Unknown file format: {name}",
        "err.unsupported": "{src} → {dst} is not supported",
        "err.ffmpeg": "ffmpeg failed:",
        "dlg.supported": "All supported",
        "dlg.all": "All files",
        "upd.noAsset": "the release has no {asset} file",
        "upd.notGit": "not a git repository",
        "upd.dirty": "the working copy has uncommitted changes",
    },
}

_lang: str | None = None


def system_lang() -> str:
    """Українська, якщо мова Windows українська, інакше англійська."""
    try:
        import ctypes
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "uk" if (lang_id & 0x3FF) == 0x22 else "en"
    except (AttributeError, OSError):
        import locale
        return "uk" if (locale.getlocale()[0] or "").lower().startswith(("uk", "ukrainian")) else "en"


def current() -> str:
    global _lang
    if _lang is None:
        import store
        _lang = store.load_settings().get("lang") or system_lang()
    return _lang


def set_lang(lang: str | None) -> None:
    global _lang
    _lang = lang or system_lang()


def t(key: str, **params) -> str:
    text = STRINGS.get(current(), STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    for k, v in params.items():
        text = text.replace("{" + k + "}", str(v))
    return text
