"""Пункт «Конвертувати в» у контекстному меню провідника Windows.

Записується в HKCU\\Software\\Classes (права адміністратора не потрібні):

    SystemFileAssociations\\.png\\shell\\Remold      — пункт меню з підменю
    Remold.menu.png\\shell\\NN_fmt\\command            — пункти підменю (JPG, WEBP, …)

Підписи беруться з поточної мови програми; після зміни мови меню перереєстровується.
У Windows 11 класичні пункти показуються в «Показати додаткові параметри» (Shift+F10).
"""
from __future__ import annotations

import sys
from pathlib import Path

import core
from i18n import t

CLASSES = r"Software\Classes"
VERB = "Remold"
MENU_PREFIX = "Remold.menu."
# ключі під попередніми назвами програми — прибираються під час реєстрації
LEGACY = [("Forma", "Forma.menu."), ("Konvertui", "Konvertui.menu.")]

# короткі списки форматів для меню (повний вибір — у вікні програми)
MENU_REMOLDTS = {
    "image": ["jpg", "png", "webp", "avif", "pdf", "ico"],
    "audio": ["mp3", "wav", "flac", "m4a", "ogg"],
    "video": ["mp4", "mkv", "webm", "gif"],
    "document": ["pdf", "docx", "txt", "md", "html"],
    "data": ["xlsx", "csv", "json"],
    "archive": ["zip", "tar.gz"],
}
VIDEO_AUDIO = ["mp3", "wav", "m4a"]  # «лише звук» з відео


def _launcher() -> tuple[str, str]:
    """(команда запуску програми, іконка) — для exe або для запуску з вихідного коду."""
    if getattr(sys, "frozen", False):
        exe = sys.executable
        return f'"{exe}"', f"{exe},0"
    root = Path(__file__).resolve().parent
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = Path(sys.executable)
    return f'"{pythonw}" "{root / "main.py"}"', str(root / "assets" / "icon.ico")


def _extensions() -> list[str]:
    # .tar.gz тощо не реєструємо: меню з'явилося б на всіх .gz-файлах
    return sorted({e for _, exts in core.CATEGORIES.values() for e in exts if "." not in e})


def _menu_items(ext: str) -> list[tuple[str, str, bool]]:
    """[(підпис, цільовий формат або "" для «Відкрити…», роздільник перед пунктом)]"""
    cat = core.detect_category(f"x.{ext}")
    src = core.normalize_ext(ext)
    valid = core.target_formats(f"x.{ext}")
    items = [(f.upper(), f, False) for f in MENU_REMOLDTS[cat] if f != src and f in valid]
    if cat == "video":
        items += [(t("menu.audioOnly", fmt=f.upper()), f, i == 0) for i, f in enumerate(VIDEO_AUDIO)]
    items.append((t("menu.open"), "", True))
    return items


def register() -> None:
    import winreg

    _remove_legacy()
    launcher, icon = _launcher()
    for ext in _extensions():
        menu_key = MENU_PREFIX + ext
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                                rf"{CLASSES}\SystemFileAssociations\.{ext}\shell\{VERB}") as k:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, t("menu.convert"))
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon)
            winreg.SetValueEx(k, "ExtendedSubCommandsKey", 0, winreg.REG_SZ, menu_key)
            # «Player» — пункт видно і коли вибрано більше 15 файлів
            winreg.SetValueEx(k, "MultiSelectModel", 0, winreg.REG_SZ, "Player")

        _delete_tree(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\{menu_key}")
        for i, (label, target, separator) in enumerate(_menu_items(ext)):
            # підключі сортуються за назвою — номер задає порядок у меню
            item = rf"{CLASSES}\{menu_key}\shell\{i:02d}_{target or 'open'}"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, item) as k:
                winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, label)
                if separator:
                    winreg.SetValueEx(k, "CommandFlags", 0, winreg.REG_DWORD, 0x20)  # ECF_SEPARATORBEFORE
                if not target:
                    winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon)
            cmd = f'{launcher} --quick -t {target} "%1"' if target else f'{launcher} "%1"'
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, item + r"\command") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
    _notify_shell()


def unregister() -> None:
    import winreg

    _remove_legacy()
    for ext in _extensions():
        _delete_tree(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\SystemFileAssociations\.{ext}\shell\{VERB}")
        _delete_tree(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\{MENU_PREFIX}{ext}")
    _notify_shell()


def _remove_legacy() -> None:
    import winreg
    for verb, prefix in LEGACY:
        for ext in _extensions():
            _delete_tree(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\SystemFileAssociations\.{ext}\shell\{verb}")
            _delete_tree(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\{prefix}{ext}")


def is_registered() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                       rf"{CLASSES}\SystemFileAssociations\.png\shell\{VERB}"))
        return True
    except OSError:
        return False


def _delete_tree(root, path: str) -> None:
    import winreg
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    child = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _delete_tree(root, rf"{path}\{child}")
        winreg.DeleteKey(root, path)
    except FileNotFoundError:
        pass


def _notify_shell() -> None:
    """Повідомити провідник про зміну асоціацій, щоб меню оновилося без перезапуску."""
    import ctypes
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
