"""Remold — точка входу.

    python main.py                         # графічний інтерфейс
    python main.py --register-menu         # «Конвертувати в» у контекстному меню провідника
    python main.py --quick -t webp a.png   # швидка конвертація поруч з оригіналом (з меню)
    python main.py file1 file2             # GUI з уже доданими файлами
    python main.py video.mp4 -t mp3        # конвертація з командного рядка
    python main.py *.png -t webp -o out    # результати в папку out
    python main.py --formats photo.heic    # куди можна перетворити файл
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# дозволяє запуск з будь-якої поточної папки
sys.path.insert(0, str(Path(__file__).resolve().parent))

import core  # noqa: E402
import version  # noqa: E402


def _cli(args) -> int:
    opts = core.Options(image_quality=args.quality, audio_bitrate=args.bitrate,
                        video_quality=args.video_quality, video_height=args.height)
    out_dir = Path(args.out) if args.out else None
    failed = 0
    for raw in args.inputs:
        src = Path(raw)
        if not src.is_file():
            print(f"✗ {raw}: file not found")
            failed += 1
            continue
        job = core.Job(src, core.normalize_ext(args.to), out_dir, opts)

        def show(p, name=src.name):
            print(f"\r  {name}: {int(p * 100):3d}%", end="", flush=True)

        try:
            result = core.convert(job, show)
            print(f"\r✓ {src.name} → {result}")
        except Exception as exc:
            print(f"\r✗ {src.name}: {exc}")
            failed += 1
    return 1 if failed else 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="Remold", description=f"Remold {version.__version__}: convert images, "
                                     "audio, video, documents, spreadsheets and archives")
    parser.add_argument("inputs", nargs="*", help="input files")
    parser.add_argument("-t", "--to", help="target format (mp3, png, pdf, xlsx, …); without it the app window opens")
    parser.add_argument("-o", "--out", help="output folder (default: next to the original)")
    parser.add_argument("--quality", type=int, default=90, help="image quality 1-100")
    parser.add_argument("--bitrate", default="192k", help="audio bitrate, e.g. 320k")
    parser.add_argument("--video-quality", default="medium", choices=["high", "medium", "low"])
    parser.add_argument("--height", type=int, default=0, help="video height, e.g. 720 (0 = original)")
    parser.add_argument("--formats", action="store_true", help="list target formats for the given files")
    parser.add_argument("--quick", action="store_true",
                        help="convert next to the original with a small progress window (used by the Explorer menu)")
    parser.add_argument("--register-menu", action="store_true", help="add “Convert to” to the Explorer context menu")
    parser.add_argument("--unregister-menu", action="store_true", help="remove it from the Explorer context menu")
    args = parser.parse_args()

    if args.register_menu or args.unregister_menu:
        import shell_menu
        shell_menu.register() if args.register_menu else shell_menu.unregister()
        print("Explorer menu", "registered" if args.register_menu else "removed")
        return 0

    if args.quick and args.to:
        import quick
        return quick.run(args.inputs, args.to)

    if args.formats:
        for raw in args.inputs:
            cat = core.detect_category(raw)
            fmts = core.target_formats(raw)
            name = cat or "unknown"
            print(f"{Path(raw).name} [{name}] → {', '.join(fmts) or '—'}")
        return 0

    if args.to:
        return _cli(args)

    import desktop
    desktop.run(args.inputs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
