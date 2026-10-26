"""Аудіо та відео через ffmpeg (бінарник постачається пакетом imageio-ffmpeg)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from core import AUDIO_OUT, Cancelled

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe(src: Path) -> dict:
    """Тривалість, розміри кадру та параметри звуку — з виводу `ffmpeg -i`."""
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(src)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", creationflags=_CREATE_NO_WINDOW)
    out = proc.stderr
    info = {"duration": 0.0, "width": None, "height": None, "sample_rate": None, "channels": None}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", out)
    if m:
        h, mnt, s = m.groups()
        info["duration"] = int(h) * 3600 + int(mnt) * 60 + float(s)
    m = re.search(r"Stream #.*?Video:.*?(\d{2,5})x(\d{2,5})", out)
    if m:
        info["width"], info["height"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"Stream #.*?Audio:.*?(\d+) Hz, ([^,\n]+)", out)
    if m:
        info["sample_rate"] = int(m.group(1))
        layout = m.group(2).strip()
        named = {"mono": 1, "stereo": 2, "2.1": 3, "quad": 4, "5.0": 5, "5.1": 6, "7.1": 8}
        num = re.match(r"(\d+) channels", layout)
        info["channels"] = int(num.group(1)) if num else named.get(layout.split("(")[0], 2)
    return info


def probe_duration(src: Path) -> float:
    """Тривалість у секундах (0, якщо невідомо)."""
    return probe(src)["duration"]


def _audio_args(target: str, bitrate: str) -> list[str]:
    return {
        "mp3":  ["-c:a", "libmp3lame", "-b:a", bitrate],
        "wav":  ["-c:a", "pcm_s16le"],
        "flac": ["-c:a", "flac"],
        "ogg":  ["-c:a", "libvorbis", "-b:a", bitrate],
        "m4a":  ["-c:a", "aac", "-b:a", bitrate],
        "aac":  ["-c:a", "aac", "-b:a", bitrate],
        "opus": ["-c:a", "libopus", "-b:a", bitrate],
        "aiff": ["-c:a", "pcm_s16be"],
        "wma":  ["-c:a", "wmav2", "-b:a", bitrate],
    }[target]


# CRF для x264 / VP9 за рівнем якості
_CRF = {"high": (18, 24), "medium": (23, 32), "low": (28, 40)}


def _video_args(target: str, opts) -> list[str]:
    x264_crf, vp9_crf = _CRF.get(opts.video_quality, _CRF["medium"])
    scale = []
    if opts.video_height:
        # -2: ширина пропорційна і парна (вимога кодеків)
        scale = ["-vf", f"scale=-2:'min({opts.video_height},ih)'"]

    if target in ("mp4", "mov", "mkv"):
        args = scale + ["-c:v", "libx264", "-preset", "medium", "-crf", str(x264_crf),
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", opts.audio_bitrate]
        if target in ("mp4", "mov"):
            args += ["-movflags", "+faststart"]
        return args
    if target == "webm":
        return scale + ["-c:v", "libvpx-vp9", "-crf", str(vp9_crf), "-b:v", "0",
                        "-row-mt", "1", "-deadline", "good", "-cpu-used", "4",
                        "-c:a", "libopus", "-b:a", opts.audio_bitrate]
    if target == "avi":
        q = {"high": 3, "medium": 5, "low": 8}.get(opts.video_quality, 5)
        return scale + ["-c:v", "mpeg4", "-vtag", "xvid", "-q:v", str(q),
                        "-c:a", "libmp3lame", "-b:a", opts.audio_bitrate]
    if target == "gif":
        # двопрохідна палітра в одному графі фільтрів — якісний GIF
        vf = (f"fps={opts.gif_fps},scale={opts.gif_width}:-1:flags=lanczos,"
              "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
        return ["-filter_complex", vf, "-an"]
    raise ValueError(target)


def _codec_args(target: str, opts) -> list[str]:
    if target in AUDIO_OUT:
        return ["-vn"] + _audio_args(target, opts.audio_bitrate)
    return _video_args(target, opts)


_CBR_AUDIO = {"mp3", "m4a", "aac", "ogg", "opus", "wma"}  # розмір ≈ тривалість × бітрейт
_SAMPLE_SECONDS = 3.0


def estimate(src: Path, target: str, opts, info: dict, abort: threading.Event | None = None) -> int | None:
    """Орієнтовний розмір результату в байтах (None — не вдалося оцінити).

    Аудіо з заданим бітрейтом і PCM рахуються за формулою. Для відео, GIF і FLAC
    кодується короткий фрагмент з середини файлу з тими самими налаштуваннями,
    і результат пропорційно переноситься на всю тривалість.
    """
    duration = info.get("duration") or 0.0
    if duration <= 0:
        return None
    if target in _CBR_AUDIO:
        kbps = int(opts.audio_bitrate.rstrip("k"))
        return int(duration * kbps * 1000 / 8)
    if target in ("wav", "aiff") and info.get("sample_rate"):
        return int(duration * info["sample_rate"] * (info.get("channels") or 2) * 2) + 44

    whole = duration <= _SAMPLE_SECONDS * 1.6
    start = 0.0 if whole else min(duration * 0.3, duration - _SAMPLE_SECONDS)
    fd, tmp_name = tempfile.mkstemp(suffix=f".{target}", prefix="konv_est_")
    os.close(fd)
    tmp = Path(tmp_name)
    cmd = [ffmpeg_exe(), "-hide_banner", "-nostdin", "-loglevel", "error", "-y"]
    if not whole:
        cmd += ["-ss", f"{start:.2f}"]
    cmd += ["-i", str(src)]
    if not whole:
        cmd += ["-t", f"{_SAMPLE_SECONDS}"]
    cmd += [*_codec_args(target, opts), str(tmp)]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=_CREATE_NO_WINDOW)
        deadline = time.monotonic() + 90
        while proc.poll() is None:
            if (abort is not None and abort.is_set()) or time.monotonic() > deadline:
                proc.kill()
                proc.wait()
                return None
            time.sleep(0.05)
        if proc.returncode != 0 or not tmp.exists():
            return None
        size = tmp.stat().st_size
        return size if whole else int(size / _SAMPLE_SECONDS * duration)
    finally:
        tmp.unlink(missing_ok=True)


def convert(job, dst: Path, progress) -> None:
    opts = job.options
    duration = probe_duration(job.src)
    codec_args = _codec_args(job.target, opts)

    cmd = [ffmpeg_exe(), "-hide_banner", "-nostdin", "-y", "-i", str(job.src),
           *codec_args, "-progress", "pipe:1", "-nostats", str(dst)]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace",
                            creationflags=_CREATE_NO_WINDOW)

    # stderr читаємо в окремому потоці, щоб буфер не переповнився
    err_lines: list[str] = []
    t = threading.Thread(target=lambda: err_lines.extend(proc.stderr), daemon=True)
    t.start()

    try:
        for line in proc.stdout:
            if job.cancel_event.is_set():
                proc.kill()
                proc.wait()
                raise Cancelled()
            if line.startswith("out_time_us=") and duration > 0:
                try:
                    us = int(line.split("=", 1)[1])
                    progress(min(0.99, us / 1_000_000 / duration))
                except ValueError:
                    pass
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    t.join(timeout=2)

    if job.cancel_event.is_set():
        raise Cancelled()
    if proc.returncode != 0:
        # прибираємо технічні префікси на кшталт "[mp3 @ 000001f989f1ebc0] "
        lines = [re.sub(r"^\[[^\]]+ @ [0-9a-fx]+\]\s*", "", ln) for ln in err_lines[-8:]]
        tail = "".join(lines).strip()
        from i18n import t
        raise RuntimeError(f"{t('err.ffmpeg')}\n{tail}")
