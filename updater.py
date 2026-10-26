"""Оновлення Remold.

* Зібрана програма (exe) оновлюється з GitHub Releases: завантажується архів
  version.RELEASE_ASSET, перевіряється його SHA-256 (файл «<архів>.sha256» у тому ж релізі),
  архів розпаковується в тимчасову папку, а після закриття програми невеликий .cmd-скрипт
  копіює нові файли поверх папки з exe і (за потреби) запускає нову версію.
* Запуск з вихідного коду в git-клоні оновлюється через `git pull --ff-only`;
  зміни діють після перезапуску.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

import i18n
import version

CHECK_INTERVAL = 6 * 3600          # автоматична перевірка не частіше
API_LATEST = f"https://api.github.com/repos/{version.REPO}/releases/latest"
FROZEN = getattr(sys, "frozen", False)
APP_ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
STAGE_ROOT = Path(tempfile.gettempdir()) / "remold-update"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_release: dict = {}                 # дані останнього знайденого релізу
_staged: Path | None = None         # розпакована нова версія, чекає на встановлення


class UpdateError(Exception):
    pass


def source() -> str:
    if FROZEN:
        return "release"
    if (APP_ROOT / ".git").exists() and shutil.which("git"):
        return "git"
    return "none"


def parse_version(text: str) -> tuple[int, ...]:
    parts = []
    for p in text.strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts + [0] * (3 - len(parts)))


def _git(*args: str, timeout: int = 60) -> str:
    proc = subprocess.run(["git", "-C", str(APP_ROOT), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, creationflags=_NO_WINDOW)
    if proc.returncode != 0:
        raise UpdateError((proc.stderr or proc.stdout).strip().splitlines()[-1] if (proc.stderr or proc.stdout).strip()
                          else f"git {' '.join(args)}: {proc.returncode}")
    return proc.stdout.strip()


def _http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": f"{version.APP_NAME}/{version.__version__}",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --- перевірка --------------------------------------------------------------------

def check() -> dict:
    """{"source", "available", "latest"} або UpdateError / OSError."""
    src = source()
    if src == "release":
        data = _http_json(API_LATEST)
        tag = data.get("tag_name", "")
        assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
        _release.clear()
        _release.update(tag=tag, zip=assets.get(version.RELEASE_ASSET),
                        sha=assets.get(version.RELEASE_ASSET + ".sha256"))
        newer = parse_version(tag) > parse_version(version.__version__)
        return {"source": src, "available": newer, "latest": tag.lstrip("vV")}
    if src == "git":
        _git("fetch", "--quiet")
        try:
            behind = int(_git("rev-list", "--count", "HEAD..@{u}") or 0)
        except UpdateError:
            behind = 0  # гілка без upstream
        latest = _git("log", "-1", "--format=%h", "@{u}") if behind else _git("log", "-1", "--format=%h")
        return {"source": src, "available": behind > 0, "latest": latest}
    return {"source": src, "available": False, "latest": version.__version__}


# --- завантаження / встановлення ------------------------------------------------------

def download(progress=None) -> dict:
    """Підготувати оновлення. Для exe — завантажити й розпакувати; для git — git pull."""
    global _staged
    src = source()
    if src == "git":
        if _git("status", "--porcelain", "--untracked-files=no"):
            raise UpdateError(i18n.t("upd.dirty"))
        _git("pull", "--ff-only", timeout=180)
        return {"ready": True, "latest": _git("log", "-1", "--format=%h")}
    if src != "release":
        raise UpdateError(i18n.t("upd.notGit"))

    if not _release:
        check()
    if not _release.get("zip"):
        raise UpdateError(i18n.t("upd.noAsset", asset=version.RELEASE_ASSET))
    tag = _release["tag"].lstrip("vV")
    shutil.rmtree(STAGE_ROOT, ignore_errors=True)
    STAGE_ROOT.mkdir(parents=True)
    archive = STAGE_ROOT / version.RELEASE_ASSET

    req = urllib.request.Request(_release["zip"], headers={"User-Agent": version.APP_NAME})
    digest = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=30) as resp, open(archive, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(1 << 16):
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)

    if _release.get("sha"):
        req = urllib.request.Request(_release["sha"], headers={"User-Agent": version.APP_NAME})
        with urllib.request.urlopen(req, timeout=15) as resp:
            expected = resp.read().decode("ascii", "replace").split()[0].lower()
        if expected != digest.hexdigest():
            shutil.rmtree(STAGE_ROOT, ignore_errors=True)
            raise UpdateError("SHA-256 mismatch")

    target = STAGE_ROOT / "new"
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():  # захист від шляхів на кшталт ../../
            if name.startswith(("/", "\\")) or ".." in Path(name).parts:
                raise UpdateError(f"unsafe path in archive: {name}")
        zf.extractall(target)
    exe_name = f"{version.APP_NAME}.exe"
    found = next((p.parent for p in target.rglob(exe_name)), None)
    if found is None:
        raise UpdateError(f"{exe_name} not found in the archive")
    _staged = found
    return {"ready": True, "latest": tag}


def staged() -> bool:
    return _staged is not None


def apply_on_exit(restart: bool) -> None:
    """Запустити встановлення, яке дочекається закриття програми й скопіює нову версію."""
    if source() == "git":
        if restart:
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            subprocess.Popen([str(pythonw if pythonw.exists() else sys.executable), str(APP_ROOT / "main.py")],
                             cwd=str(APP_ROOT), creationflags=_NO_WINDOW)
        return
    if _staged is None:
        return
    # Встановлює сама нова версія: її exe лежить у тимчасовій папці, тож не заблокований
    # копіюванням. Жодних cmd/консолей — раніше скрипт з `tasklist | find` без консолі
    # відкривав порожнє вікно find і зависав.
    helper = _staged / f"{version.APP_NAME}.exe"
    args = [str(helper), "--apply-update", str(_staged), "--target", str(APP_ROOT), "--wait-pid", str(os.getpid())]
    if restart:
        args.append("--restart")
    subprocess.Popen(args, cwd=str(STAGE_ROOT), close_fds=True,
                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008)  # DETACHED_PROCESS


def _log(text: str) -> None:
    try:
        with open(STAGE_ROOT.parent / "remold-update.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
    except OSError:
        pass


def apply_staged(src: Path, dst: Path, wait_pid: int, restart: bool) -> int:
    """Режим `--apply-update`: дочекатися закриття старої програми, скопіювати нові файли
    поверх папки з exe й за потреби запустити оновлену програму."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x00100000, False, wait_pid)  # SYNCHRONIZE
    if handle:
        kernel32.WaitForSingleObject(handle, 120_000)
        kernel32.CloseHandle(handle)

    failed = []
    for file in src.rglob("*"):
        if not file.is_file():
            continue
        target = dst / file.relative_to(src)
        for attempt in range(40):  # файли можуть ще кілька секунд бути зайняті антивірусом тощо
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
                break
            except OSError as exc:
                if attempt == 39:
                    failed.append(f"{target}: {exc}")
                time.sleep(0.25)
    _log(f"applied {src} -> {dst}: {'ok' if not failed else f'{len(failed)} failed'}")
    for line in failed[:20]:
        _log("  " + line)

    if restart:
        exe = dst / f"{version.APP_NAME}.exe"
        subprocess.Popen([str(exe)], cwd=str(dst), close_fds=True,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008)
    return 1 if failed else 0


def cleanup_stale() -> None:
    """Прибрати тимчасову папку попереднього оновлення (після того, як воно встановилось)."""
    if FROZEN and STAGE_ROOT.exists() and _staged is None:
        shutil.rmtree(STAGE_ROOT, ignore_errors=True)


def due(settings: dict) -> bool:
    """Чи час для автоматичної перевірки."""
    return (settings.get("auto_update", True) and source() != "none"
            and time.time() - float(settings.get("last_update_check") or 0) >= CHECK_INTERVAL)
