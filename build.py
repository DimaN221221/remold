"""Збірка Remold у Windows-програму (PyInstaller).

    python build.py            # папка dist\\Remold\\ з Remold.exe (швидкий запуск)
    python build.py --zip      # те саме + dist\\Remold-windows-x64.zip і .sha256 для GitHub Releases
    python build.py --onefile  # один файл dist\\Remold.exe (зручно передавати, запуск повільніший)
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import version

ROOT = Path(__file__).resolve().parent
ICON = ROOT / "assets" / "icon.ico"
NAME = version.APP_NAME


def make_icon() -> None:
    """Іконка з логотипа: помаранчева «форма» — квадрат, що переходить у дугу, з вирізом."""
    from PIL import Image, ImageDraw

    size = 1024  # малюємо з запасом і зменшуємо — згладжені краї
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = size / 24  # координати як у SVG-логотипі (viewBox 0 0 24 24)
    orange = "#e8590c"
    # квадрат 3..21 з правим верхнім кутом-дугою радіуса 8.5
    d.rectangle((3 * u, 11.5 * u, 21 * u, 21 * u), fill=orange)
    d.rectangle((3 * u, 3 * u, 12.5 * u, 21 * u), fill=orange)
    d.pieslice((4 * u, 3 * u, 21 * u, 20 * u), 270, 360, fill=orange)
    d.rectangle((7 * u, 11 * u, 13 * u, 17 * u), fill=(0, 0, 0, 0))
    ICON.parent.mkdir(exist_ok=True)
    img.resize((256, 256), Image.LANCZOS).save(
        ICON, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def make_zip() -> Path:
    """Архів для GitHub Releases + файл з SHA-256 (його перевіряє оновлювач)."""
    base = ROOT / "dist" / version.RELEASE_ASSET.removesuffix(".zip")
    archive = Path(shutil.make_archive(str(base), "zip", root_dir=ROOT / "dist", base_dir=NAME))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + ".sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return archive


def main() -> None:
    import PyInstaller.__main__

    onefile = "--onefile" in sys.argv
    if not ICON.exists() or "--icon" in sys.argv:
        make_icon()

    sep = ";"  # роздільник src;dest для --add-data у Windows
    args = [
        str(ROOT / "main.py"),
        "--name", NAME,
        "--icon", str(ICON),
        "--windowed",
        "--noconfirm",
        "--clean",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--add-data", f"{ROOT / 'webui'}{sep}webui",
        "--add-data", f"{ROOT / 'assets'}{sep}assets",
        # модулі, які імпортуються динамічно
        "--hidden-import", "desktop",
        "--hidden-import", "quick",
        "--hidden-import", "shell_menu",
        "--hidden-import", "store",
        "--hidden-import", "updater",
        "--hidden-import", "i18n",
        "--collect-submodules", "converters",
        "--collect-all", "pillow_heif",
        "--collect-all", "pymupdf",
        # не потрібні програмі, але PyInstaller тягне їх через залежності
        "--exclude-module", "numpy",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pandas",
        "--exclude-module", "PyInstaller",
    ]
    args.append("--onefile" if onefile else "--onedir")
    PyInstaller.__main__.run(args)
    shutil.rmtree(ROOT / "build", ignore_errors=True)  # проміжні файли PyInstaller
    print("\nГотово:", ROOT / "dist" / (f"{NAME}.exe" if onefile else f"{NAME}\\{NAME}.exe"))
    if "--zip" in sys.argv and not onefile:
        print("Архів для релізу:", make_zip())


if __name__ == "__main__":
    main()
