"""Перепакування архівів: ZIP <-> TAR / TAR.GZ / TAR.BZ2 / TAR.XZ."""
from __future__ import annotations

import io
import tarfile
import time
import zipfile
from pathlib import Path, PurePosixPath

from core import file_ext, normalize_ext

_TAR_MODES = {"tar": "w", "tar.gz": "w:gz", "tar.bz2": "w:bz2", "tar.xz": "w:xz"}


def _safe_name(name: str) -> str | None:
    """Відкидаємо абсолютні шляхи та '..' (захист від path traversal)."""
    p = PurePosixPath(name.replace("\\", "/"))
    parts = [x for x in p.parts if x not in ("", "/", ".")]
    if not parts or ".." in parts or ":" in parts[0]:
        return None
    return "/".join(parts)


def _iter_source(path: Path):
    """Генерує (ім'я, байти або None для папки, mtime)."""
    ext = normalize_ext(file_ext(path))
    if ext == "zip":
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                name = _safe_name(info.filename)
                if name is None:
                    continue
                if info.is_dir():
                    yield name, None, None
                else:
                    mtime = time.mktime(info.date_time + (0, 0, -1))
                    yield name, zf.read(info), mtime
    else:
        with tarfile.open(path, "r:*") as tf:
            for m in tf.getmembers():
                name = _safe_name(m.name)
                if name is None:
                    continue
                if m.isdir():
                    yield name, None, m.mtime
                elif m.isfile():
                    f = tf.extractfile(m)
                    yield name, f.read() if f else b"", m.mtime


def _count(path: Path) -> int:
    if normalize_ext(file_ext(path)) == "zip":
        with zipfile.ZipFile(path) as zf:
            return len(zf.infolist()) or 1
    with tarfile.open(path, "r:*") as tf:
        return len(tf.getmembers()) or 1


def convert(job, dst: Path, progress) -> None:
    total = _count(job.src)
    target = job.target

    if target == "zip":
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
            for i, (name, data, mtime) in enumerate(_iter_source(job.src)):
                job.check_cancel()
                if data is None:
                    zout.writestr(name.rstrip("/") + "/", b"")
                else:
                    zout.writestr(name, data)
                progress((i + 1) / total)
    else:
        with tarfile.open(dst, _TAR_MODES[target]) as tout:
            for i, (name, data, mtime) in enumerate(_iter_source(job.src)):
                job.check_cancel()
                info = tarfile.TarInfo(name.rstrip("/"))
                if mtime:
                    info.mtime = int(mtime)
                if data is None:
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    tout.addfile(info)
                else:
                    info.size = len(data)
                    info.mode = 0o644
                    tout.addfile(info, io.BytesIO(data))
                progress((i + 1) / total)
