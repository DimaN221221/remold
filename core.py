"""Реєстр форматів, визначення типу файлу та диспетчер конвертації."""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# --- Формати ------------------------------------------------------------------

IMAGE_IN = ["png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff", "tif", "ico",
            "heic", "heif", "avif", "tga", "ppm"]
IMAGE_OUT = ["png", "jpg", "webp", "bmp", "gif", "tiff", "ico", "avif", "pdf"]

AUDIO_IN = ["mp3", "wav", "flac", "ogg", "m4a", "aac", "opus", "wma", "aiff",
            "aif", "amr", "ac3", "mka"]
AUDIO_OUT = ["mp3", "wav", "flac", "ogg", "m4a", "opus", "aac", "aiff", "wma"]

VIDEO_IN = ["mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "m4v", "mpeg",
            "mpg", "3gp", "ts", "mts", "m2ts", "ogv"]
VIDEO_OUT = ["mp4", "mkv", "avi", "mov", "webm", "gif"]

DOC_IN = ["pdf", "docx", "txt", "md", "html", "htm"]
DOC_OUT = ["pdf", "docx", "txt", "md", "html"]
PDF_EXTRA_OUT = ["png", "jpg"]  # сторінки PDF -> зображення

DATA_IN = ["csv", "tsv", "json", "xlsx", "xml"]
DATA_OUT = ["csv", "tsv", "json", "xlsx", "xml", "html", "md"]

ARCHIVE_IN = ["zip", "tar", "tar.gz", "tgz", "tar.bz2", "tar.xz"]
ARCHIVE_OUT = ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz"]

# цільові формати, для яких має сенс повзунок якості (стиснення з втратами)
LOSSY_TARGETS = {"jpg", "webp", "avif", "mp3", "ogg", "m4a", "aac", "opus", "wma",
                 "mp4", "mkv", "mov", "webm", "avi"}

CATEGORIES = {
    "image": ("Зображення", IMAGE_IN),
    "audio": ("Аудіо", AUDIO_IN),
    "video": ("Відео", VIDEO_IN),
    "document": ("Документ", DOC_IN),
    "data": ("Дані / таблиці", DATA_IN),
    "archive": ("Архів", ARCHIVE_IN),
}

# Нормалізація синонімів розширень
_ALIASES = {"jpeg": "jpg", "tif": "tiff", "htm": "html", "aif": "aiff",
            "tgz": "tar.gz", "heif": "heic"}


def file_ext(path: str | Path) -> str:
    """Розширення в нижньому регістрі без крапки; враховує .tar.gz тощо."""
    name = Path(path).name.lower()
    for multi in ("tar.gz", "tar.bz2", "tar.xz"):
        if name.endswith("." + multi):
            return multi
    return Path(name).suffix.lstrip(".")


def normalize_ext(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    return _ALIASES.get(ext, ext)


def stem_of(path: str | Path) -> str:
    p = Path(path)
    ext = file_ext(p)
    return p.name[: -(len(ext) + 1)] if ext else p.name


def detect_category(path: str | Path) -> str | None:
    ext = file_ext(path)
    for cat, (_, exts) in CATEGORIES.items():
        if ext in exts:
            return cat
    return None


def target_formats(path: str | Path) -> list[str]:
    """Список форматів, у які можна перетворити файл."""
    cat = detect_category(path)
    src = normalize_ext(file_ext(path))
    if cat == "image":
        return IMAGE_OUT[:]  # той самий формат = стиснення / зміна розміру
    if cat == "audio":
        return AUDIO_OUT[:]
    if cat == "video":
        # відео можна перекодувати або витягти з нього звук
        return VIDEO_OUT + [f for f in AUDIO_OUT if f not in VIDEO_OUT]
    if cat == "document":
        outs = [f for f in DOC_OUT if f != src]
        if src == "pdf":
            outs += PDF_EXTRA_OUT
        return outs
    if cat == "data":
        return [f for f in DATA_OUT if f != src]
    if cat == "archive":
        return [f for f in ARCHIVE_OUT if f != src]
    return []


# --- Налаштування та завдання -------------------------------------------------

@dataclass
class Options:
    image_quality: int = 90          # 1..100
    image_max_size: int = 0          # 0 = без змін, інакше макс. сторона в px
    audio_bitrate: str = "192k"
    video_quality: str = "medium"    # high / medium / low
    video_height: int = 0            # 0 = оригінал
    gif_fps: int = 12
    gif_width: int = 480


class Cancelled(Exception):
    pass


@dataclass
class Job:
    src: Path
    target: str
    out_dir: Path | None = None      # None = поруч з оригіналом
    options: Options = field(default_factory=Options)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    name_template: str = "{назва}"   # див. render_name()

    def check_cancel(self):
        if self.cancel_event.is_set():
            raise Cancelled()


ProgressCb = Callable[[float], None]  # 0.0 .. 1.0


def unique_path(path: Path) -> Path:
    """Не перезаписуємо існуючі файли: name.ext -> name (1).ext ..."""
    if not path.exists():
        return path
    ext = file_ext(path)
    stem = stem_of(path)
    i = 1
    while True:
        candidate = path.with_name(f"{stem} ({i}).{ext}")
        if not candidate.exists():
            return candidate
        i += 1


def render_template(template: str, src: Path, target: str) -> str:
    """Підставляє {назва}, {формат}, {дата} (та англійські {name}, {format}, {date})."""
    import datetime
    values = {
        "назва": stem_of(src), "name": stem_of(src),
        "формат": target, "format": target,
        "дата": datetime.date.today().isoformat(), "date": datetime.date.today().isoformat(),
    }
    out = template
    for key, val in values.items():
        out = out.replace("{" + key + "}", val)
    return out


def render_name(template: str, src: Path, target: str) -> str:
    name = render_template(template or "{назва}", src, target)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name or stem_of(src)


def output_path(job: Job) -> Path:
    out_dir = job.out_dir or job.src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    name = render_name(job.name_template, job.src, job.target)
    return unique_path(out_dir / f"{name}.{job.target}")


def convert(job: Job, progress: ProgressCb | None = None) -> Path:
    """Виконати конвертацію; повертає шлях до результату."""
    progress = progress or (lambda _p: None)
    cat = detect_category(job.src)
    if cat is None:
        from i18n import t
        raise ValueError(t("err.unknown", name=job.src.name))
    if job.target not in target_formats(job.src):
        from i18n import t
        raise ValueError(t("err.unsupported", src=file_ext(job.src).upper(), dst=job.target.upper()))

    dst = output_path(job)
    job.check_cancel()

    # імпортуємо лише потрібний модуль — швидший запуск з контекстного меню
    import importlib
    module = {"image": "images", "audio": "media", "video": "media", "document": "documents",
              "data": "data", "archive": "archives"}[cat]
    handler = importlib.import_module(f"converters.{module}").convert

    try:
        result = handler(job, dst, progress) or dst
    except BaseException:
        # не залишаємо після себе напівзаписаних файлів
        if dst.is_file():
            try:
                dst.unlink()
            except OSError:
                pass
        raise

    progress(1.0)
    return result
