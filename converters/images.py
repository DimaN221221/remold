"""Конвертація зображень через Pillow."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

try:  # підтримка HEIC/HEIF (фото з iPhone)
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

# формати Pillow для кожного розширення
_PIL_FORMAT = {
    "png": "PNG", "jpg": "JPEG", "webp": "WEBP", "bmp": "BMP", "gif": "GIF",
    "tiff": "TIFF", "ico": "ICO", "avif": "AVIF", "pdf": "PDF",
}
# формати без альфа-каналу
_NO_ALPHA = {"jpg", "bmp", "pdf"}
# до скількох пікселів оцінка розміру кодує зображення повністю (інакше — вибірку фрагментів)
_FULL_ESTIMATE_PIXELS = 6_000_000
_TILE = 768


def _prepare(img: Image.Image, target: str, max_size: int) -> Image.Image:
    img = ImageOps.exif_transpose(img)  # правильна орієнтація фото з телефону
    if max_size and max(img.size) > max_size:
        img = img.copy()
        img.thumbnail((max_size, max_size), Image.LANCZOS)

    if target in _NO_ALPHA:
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.split()[-1])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
    elif img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        img = img.convert("RGBA")
    return img


def _save_kwargs(target: str, opts, size: tuple[int, int]) -> dict:
    kwargs: dict = {}
    if target in ("jpg", "webp", "avif"):
        kwargs["quality"] = opts.image_quality
    if target == "jpg":
        kwargs.update(optimize=True, progressive=True)
    if target == "png":
        kwargs["optimize"] = True
    if target == "ico":
        sizes = [(s, s) for s in (16, 32, 48, 64, 128, 256)]
        kwargs["sizes"] = [s for s in sizes if s[0] <= max(size)] or [(16, 16)]
    return kwargs


def convert(job, dst: Path, progress) -> None:
    opts = job.options
    target = job.target
    with Image.open(job.src) as img:
        n_frames = getattr(img, "n_frames", 1)
        save_kwargs = _save_kwargs(target, opts, img.size)

        # анімація (GIF/WebP) зберігається, якщо цільовий формат її підтримує
        if n_frames > 1 and target in ("gif", "webp", "png", "tiff", "pdf"):
            frames = []
            durations = []
            for i, frame in enumerate(ImageSequence.Iterator(img)):
                job.check_cancel()
                frames.append(_prepare(frame.copy(), target, opts.image_max_size))
                durations.append(frame.info.get("duration", 100))
                progress(0.9 * (i + 1) / n_frames)
            extra = {"save_all": True, "append_images": frames[1:]}
            if target in ("gif", "webp", "png"):
                extra.update(duration=durations, loop=img.info.get("loop", 0))
            if target == "png":
                # APNG: кадри мають бути в одному повнокольоровому режимі
                save_kwargs.pop("optimize", None)
                frames = [f.convert("RGBA") for f in frames]
            frames[0].save(dst, _PIL_FORMAT[target], **save_kwargs, **extra)
        else:
            out = _prepare(img, target, opts.image_max_size)
            progress(0.5)
            job.check_cancel()
            out.save(dst, _PIL_FORMAT[target], **save_kwargs)


def info(src: Path) -> tuple[int, int]:
    """Розміри зображення з урахуванням EXIF-повороту (читається лише заголовок)."""
    with Image.open(src) as img:
        w, h = img.size
        orientation = img.getexif().get(0x0112, 1)
    return (h, w) if orientation in (5, 6, 7, 8) else (w, h)


def _encoded_size(img: Image.Image, target: str, opts) -> int:
    buf = io.BytesIO()
    img.save(buf, _PIL_FORMAT[target], **_save_kwargs(target, opts, img.size))
    return buf.tell()


def estimate(src: Path, target: str, opts) -> int:
    """Пробне стиснення в пам'яті з тими самими налаштуваннями, що й під час конвертації.

    Невеликі зображення кодуються повністю. Для великих беремо кілька фрагментів
    у повній роздільності, складаємо їх у мозаїку, кодуємо й переносимо
    «байтів на піксель» на весь кадр.
    """
    with Image.open(src) as img:
        n_frames = getattr(img, "n_frames", 1)
        animated = n_frames > 1 and target in ("gif", "webp", "png", "tiff", "pdf")
        frame = _prepare(img, target, opts.image_max_size)
        w, h = frame.size
        frames = n_frames if animated else 1

        if w * h <= _FULL_ESTIMATE_PIXELS or target == "ico":
            size = _encoded_size(frame, target, opts)
            # кадри анімації схожі між собою; кодувати їх усі заради оцінки задорого
            return size * frames

        # мозаїка 2×2 з фрагментів у різних частинах кадру
        tile = min(_TILE, w // 2, h // 2)
        mosaic = Image.new(frame.mode, (tile * 2, tile * 2))
        for i, (fx, fy) in enumerate(((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))):
            x = int(fx * w - tile / 2)
            y = int(fy * h - tile / 2)
            mosaic.paste(frame.crop((x, y, x + tile, y + tile)), ((i % 2) * tile, (i // 2) * tile))
        if frame.mode == "P":
            mosaic.putpalette(frame.getpalette())
        bytes_per_px = _encoded_size(mosaic, target, opts) / (tile * tile * 4)
        return int(bytes_per_px * w * h) * frames
