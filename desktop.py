"""Remold — десктопний інтерфейс (HTML/CSS у нативному вікні через pywebview).

Python тримає чергу файлів і виконує конвертацію; інтерфейс у webui/ лише
показує стан і викликає методи Api через window.pywebview.api.
"""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import webview
from webview.dom import DOMEventHandler

import core
import i18n
import shell_menu
import store
import updater
import version

# у зібраному exe (PyInstaller) ресурси лежать у sys._MEIPASS
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
WEBUI = APP_DIR / "webui" / "index.html"
ICON = APP_DIR / "assets" / "icon.ico"

# формати для правил на екрані «Пакетна обробка» (назви типів перекладає інтерфейс)
RULE_REMOLDTS = {
    "image": core.IMAGE_OUT,
    "audio": core.AUDIO_OUT,
    "video": core.VIDEO_OUT + ["mp3", "wav", "flac", "m4a"],
    "document": core.DOC_OUT,
    "data": core.DATA_OUT,
    "archive": core.ARCHIVE_OUT,
}


def reveal(path: Path) -> None:
    if not path.exists():
        path = path.parent
    if os.name == "nt":
        if path.is_dir():
            os.startfile(path)
        else:
            subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path if path.is_dir() else path.parent)])


class Api:
    """Методи цього класу доступні з JavaScript як window.pywebview.api.*"""

    def __init__(self):
        self._window = None
        self._items: dict[int, dict] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._running = False
        self._est_abort = threading.Event()
        self._settings = store.load_settings()
        self._history: list[dict] = store.load_json(store.HISTORY_FILE, [])
        self._update: dict = {"source": updater.source()}

    # --- службове -------------------------------------------------------------

    def _attach(self, window):
        self._window = window

    def _push(self, kind: str, payload) -> None:
        """Надіслати подію в інтерфейс."""
        if self._window is None:
            return
        js = f"window.app && window.app.onEvent({json.dumps(kind)}, {json.dumps(payload, ensure_ascii=False)})"
        try:
            self._window.evaluate_js(js)
        except Exception:
            pass

    def _public(self, item: dict) -> dict:
        return {k: v for k, v in item.items() if not k.startswith("_")}

    def _default_target(self, path: Path, category: str, formats: list[str]) -> str:
        rule = self._settings["rules"].get(category)
        if rule in formats:
            return rule
        src = core.normalize_ext(core.file_ext(path))
        return next((f for f in formats if f != src), formats[0])

    # --- виклики з інтерфейсу -------------------------------------------------

    def init(self) -> dict:
        return {
            "settings": self._settings,
            "history": self._history,
            "items": [self._public(it) for it in self._items.values()],
            "categories": {c: {"formats": fmts} for c, fmts in RULE_REMOLDTS.items()},
            "lossy": sorted(core.LOSSY_TARGETS),
            "audioRemoldts": core.AUDIO_OUT,
            "bitrates": store.BITRATE_STEPS,
            "running": self._running,
            "shellMenu": shell_menu.is_registered(),
            "lang": i18n.current(),
            "version": version.__version__,
            "repoUrl": version.REPO_URL,
            "update": self._update,
        }

    def pick_files(self) -> dict:
        exts = sorted({e for _, lst in core.CATEGORIES.values() for e in lst if "." not in e})
        types = (i18n.t("dlg.supported") + " (" + ";".join(f"*.{e}" for e in exts + ["tar.gz", "tar.bz2", "tar.xz"]) + ")",
                 i18n.t("dlg.all") + " (*.*)")
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True,
                                                file_types=types) or []
        return self.add_paths(list(paths))

    def add_paths(self, paths: list[str]) -> dict:
        files: list[Path] = []
        for raw in paths:
            p = Path(raw)
            if p.is_dir():
                files += sorted(f for f in p.rglob("*") if f.is_file() and core.detect_category(f))
            elif p.is_file():
                files.append(p)

        added, skipped = [], []
        with self._lock:
            known = {it["_resolved"] for it in self._items.values()}
            for f in files:
                key = str(f.resolve()).lower()
                if key in known:
                    continue
                category = core.detect_category(f)
                formats = core.target_formats(f) if category else []
                if not formats:
                    skipped.append(f.name)
                    continue
                item = {
                    "id": next(self._ids), "name": f.name, "path": str(f),
                    "category": category, "ext": core.file_ext(f).replace("tar.", "t").upper()[:4],
                    "size": f.stat().st_size, "formats": formats,
                    "target": self._default_target(f, category, formats),
                    "status": "waiting", "progress": 0.0, "error": "", "result": None,
                    "resultSize": None, "duration": None, "width": None, "height": None,
                    "_resolved": key,
                }
                self._items[item["id"]] = item
                known.add(key)
                added.append(self._public(item))

        probe = [it["id"] for it in added if it["category"] in ("audio", "video", "image")]
        if probe:
            threading.Thread(target=self._probe, args=(probe,), daemon=True).start()
        return {"added": added, "skipped": skipped}

    def _probe(self, ids: list[int]) -> None:
        """Тривалість і розміри кадру — для панелі та оцінки розміру результату."""
        from converters import images, media
        for item_id in ids:
            item = self._items.get(item_id)
            if not item:
                continue
            meta = {"id": item_id}
            try:
                if item["category"] == "image":
                    meta["width"], meta["height"] = images.info(Path(item["path"]))
                else:
                    info = media.probe(Path(item["path"]))
                    item["_media"] = info
                    meta.update(duration=info["duration"], width=info["width"], height=info["height"])
            except Exception:
                meta["duration"] = 0  # 0 = не вдалося визначити
            item.update({k: v for k, v in meta.items() if k != "id"})
            self._push("meta", meta)

    def estimate(self, item_id: int, target: str, params: dict) -> dict:
        """Орієнтовний розмір результату: пробне стиснення з поточними налаштуваннями.

        Новий запит перериває попередню пробу (наприклад, під час руху повзунка).
        """
        from converters import images, media
        item = self._items.get(item_id)
        if not item or target not in item["formats"]:
            return {"bytes": None}
        self._est_abort.set()
        abort = self._est_abort = threading.Event()
        opts = store.options_from({**self._settings, **params})
        src = Path(item["path"])
        try:
            if item["category"] == "image":
                return {"bytes": images.estimate(src, target, opts)}
            if item["category"] in ("audio", "video"):
                info = item.get("_media") or media.probe(src)
                item["_media"] = info
                return {"bytes": media.estimate(src, target, opts, info, abort)}
        except Exception:
            pass
        return {"bytes": None}

    def set_target(self, item_id: int, target: str) -> None:
        item = self._items.get(item_id)
        if item and target in item["formats"] and item["status"] != "running":
            item["target"] = target
            if item["status"] != "waiting":
                item.update(status="waiting", progress=0.0, error="", result=None, resultSize=None)

    def apply_rules(self, rules: dict) -> list[dict]:
        """Застосувати правила «Пакетної обробки» до файлів черги, що ще не оброблені."""
        self.save_settings({"rules": rules})
        for item in self._items.values():
            fmt = rules.get(item["category"])
            if item["status"] in ("waiting", "error", "cancelled") and fmt in item["formats"]:
                item["target"] = fmt
        return [self._public(it) for it in self._items.values()]

    def remove(self, item_id: int) -> None:
        item = self._items.get(item_id)
        if item and item["status"] != "running":
            del self._items[item_id]

    def clear(self) -> None:
        if not self._running:
            self._items.clear()

    def save_settings(self, partial: dict) -> dict:
        for key, value in partial.items():
            if key in store.DEFAULT_SETTINGS:
                self._settings[key] = value
        store.save_json(store.SETTINGS_FILE, self._settings)
        if "lang" in partial:
            i18n.set_lang(partial["lang"])
            if shell_menu.is_registered():
                try:
                    shell_menu.register()  # підписи в меню провідника — новою мовою
                except OSError:
                    pass
        return self._settings

    # --- оновлення ------------------------------------------------------------

    def check_updates(self) -> dict:
        try:
            res = updater.check()
            self._update.update(res, error="")
        except Exception as exc:  # мережа, GitHub API, git
            self._update.update(error=str(exc) or exc.__class__.__name__, available=False)
        self.save_settings({"last_update_check": time.time()})
        return self._update

    def install_update(self) -> dict:
        try:
            self._update.update(updater.download(), available=False, error="")
        except Exception as exc:
            self._update.update(error=str(exc) or exc.__class__.__name__)
        return self._update

    def restart_to_update(self) -> None:
        updater.apply_on_exit(restart=True)
        self._update["applied"] = True
        if self._window is not None:
            self._window.destroy()

    def _auto_update(self) -> None:
        """Фонова перевірка під час запуску (якщо ввімкнено «Оновлювати автоматично»)."""
        if not updater.due(self._settings):
            return
        res = self.check_updates()
        if res.get("available") and not res.get("error"):
            self.install_update()
        self._push("update", self._update)

    def open_repo(self) -> None:
        import webbrowser
        webbrowser.open(version.REPO_URL)

    def set_shell_menu(self, enabled: bool) -> dict:
        """Увімкнути / вимкнути пункт «Конвертувати в» у контекстному меню провідника."""
        try:
            shell_menu.register() if enabled else shell_menu.unregister()
            return {"ok": True, "enabled": shell_menu.is_registered()}
        except OSError as exc:
            return {"ok": False, "enabled": shell_menu.is_registered(), "error": str(exc)}

    def choose_out_dir(self) -> str | None:
        start = self._settings["out_dir"] or str(Path.home())
        res = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=start)
        if res:
            folder = res[0] if isinstance(res, (list, tuple)) else res
            self.save_settings({"out_dir": folder})
            return folder
        return None

    def reveal_item(self, item_id: int) -> None:
        item = self._items.get(item_id)
        if item:
            reveal(Path(item["result"] or item["path"]))

    def reveal_path(self, path: str) -> None:
        reveal(Path(path))

    def clear_history(self) -> None:
        self._history = []
        store.save_json(store.HISTORY_FILE, self._history)

    # --- конвертація ----------------------------------------------------------

    def start(self, ids: list[int] | None = None) -> bool:
        if self._running:
            return False
        if ids is None:
            todo = [it for it in self._items.values() if it["status"] != "done"]
        else:
            todo = [self._items[i] for i in ids if i in self._items]
        if not todo:
            return False

        s = self._settings
        options = store.options_from(s)
        out_dir = None
        if s["out_dir"]:
            out_dir = Path(core.render_template(s["out_dir"], Path("x"), "x"))

        self._cancel = threading.Event()
        self._running = True
        for it in todo:
            it.update(status="queued", progress=0.0, error="", result=None, resultSize=None)
            self._push("item", self._public(it))
        self._push("running", True)

        jobs = [(it, core.Job(Path(it["path"]), it["target"], out_dir, options, self._cancel,
                              s["name_template"])) for it in todo]
        threading.Thread(target=self._run_all, args=(jobs,), daemon=True).start()
        return True

    def _run_all(self, jobs):
        workers = max(1, min(3, (os.cpu_count() or 2) // 2))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(self._run_one, jobs))
        self._running = False
        self._push("running", False)

    def _run_one(self, pair):
        item, job = pair
        if self._cancel.is_set():
            item.update(status="cancelled", progress=0.0)
            self._push("item", self._public(item))
            return
        item.update(status="running", progress=0.0)
        self._push("item", self._public(item))

        last = [0.0, 0.0]  # прогрес і час останнього надсилання

        def on_progress(p: float):
            now = time.monotonic()
            if p - last[0] >= 0.01 and now - last[1] >= 0.12:
                last[:] = [p, now]
                item["progress"] = p
                self._push("progress", {"id": item["id"], "progress": p})

        try:
            result = core.convert(job, on_progress)
            item.update(status="done", progress=1.0, result=str(result), resultSize=store.total_size(result))
            self._add_history(job, result)
        except core.Cancelled:
            item.update(status="cancelled", progress=0.0)
        except Exception as exc:
            item.update(status="error", error=str(exc) or exc.__class__.__name__)
        self._push("item", self._public(item))

    def _add_history(self, job: core.Job, result: Path):
        entry = store.history_entry(job.src, job.target, result)
        with self._lock:
            # файл перечитується: туди ж пише швидка конвертація з контекстного меню
            self._history = store.append_history(entry)
        self._push("history", entry)

    def cancel(self) -> None:
        self._cancel.set()

    def is_running(self) -> bool:
        return self._running


def _on_start(window, api: Api):
    _bind_drop(window, api)
    threading.Timer(2.0, updater.cleanup_stale).start()  # залишки щойно встановленого оновлення
    threading.Timer(3.0, api._auto_update).start()


def _bind_drop(window, api: Api):
    """Перетягування файлів з провідника: pywebview додає повний шлях у pywebviewFullPath."""
    def on_drop(event):
        files = event.get("dataTransfer", {}).get("files", [])
        paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
        if paths:
            api._push("dropped", api.add_paths(paths))

    def ignore(_event):
        pass

    window.dom.document.events.dragenter += DOMEventHandler(ignore, True, True)
    window.dom.document.events.dragover += DOMEventHandler(ignore, True, True, debounce=500)
    window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)


def run(initial_paths: list[str] | None = None) -> None:
    api = Api()
    if initial_paths:
        api.add_paths(initial_paths)
    dark = api._settings["theme"] == "dark"
    window = webview.create_window(
        version.APP_NAME, str(WEBUI), js_api=api,
        width=1180, height=740, min_size=(980, 620),
        background_color="#111113" if dark else "#f2f1ed",
    )
    api._attach(window)

    def on_closing():
        if api.is_running():
            api.cancel()
        # завантажене автоматично оновлення встановлюється після закриття програми
        if updater.staged() and not api._update.get("applied"):
            updater.apply_on_exit(restart=False)
        return True

    window.events.closing += on_closing
    webview.start(_on_start, (window, api), icon=str(ICON) if ICON.exists() else None)
