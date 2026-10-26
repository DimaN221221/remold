"""Швидка конвертація з контекстного меню провідника: Remold.exe --quick -t webp "файл".

Результат зберігається поруч з оригіналом, налаштування якості беруться з програми.
Невелике вікно з прогресом з'являється в правому нижньому куті, лише якщо конвертація
триває довше ~0.6 с. Коли в провіднику вибрано кілька файлів, Windows запускає окремий
процес на кожен; одночасно конвертують не більше двох (системний семафор), решта чекають.
"""
from __future__ import annotations

import ctypes
import queue
import threading
import tkinter as tk
from pathlib import Path

import core
import store
from i18n import t

MAX_PARALLEL = 2
SHOW_AFTER_MS = 600
WIDTH, HEIGHT, MARGIN = 360, 112, 16

LIGHT = {"bg": "#fbfaf8", "card": "#ffffff", "line": "#dcdad3", "ink": "#1d1c1a", "mute": "#6b675e",
         "acc": "#2f5fd0", "ok": "#2f8a4d", "err": "#d64545", "dash": "#b9b5aa"}
DARK = {"bg": "#1b1d1f", "card": "#232628", "line": "#2d3033", "ink": "#ecebe6", "mute": "#9a9da1",
        "acc": "#4a7ae8", "ok": "#5fcf85", "err": "#d64545", "dash": "#4a4e52"}

kernel32 = ctypes.windll.kernel32
WAIT_OBJECT_0, WAIT_ABANDONED = 0x0, 0x80


def _system_dark() -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


MAX_SLOTS = 8


def _try_slot(slot: int) -> int:
    """Зайняти позицію вікна; м'ютекс існує, поки його тримає процес. 0 — позиція зайнята."""
    handle = kernel32.CreateMutexW(None, True, f"Local\\Remold.quick.slot{slot}")
    if handle and kernel32.GetLastError() != 183:  # ERROR_ALREADY_EXISTS
        return handle
    if handle:
        kernel32.CloseHandle(handle)
    return 0


def _take_slot(below: int = MAX_SLOTS) -> tuple[int, int]:
    """Найнижча вільна позиція (щоб вікна кількох процесів не накладались) та її м'ютекс."""
    for slot in range(below):
        handle = _try_slot(slot)
        if handle:
            return slot, handle
    return (0, 0) if below == MAX_SLOTS else (-1, 0)


class QuickWindow:
    def __init__(self, src: Path, target: str, settings: dict):
        self.src, self.target = src, target
        self.settings = settings
        self.cancel_event = threading.Event()
        self.events: queue.Queue = queue.Queue()
        self.finished = False
        self.exit_code = 0

        theme = settings.get("theme") or ("dark" if _system_dark() else "light")
        self.c = DARK if theme == "dark" else LIGHT
        self.slot, self.slot_handle = _take_slot()

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(t("quick.title"))
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=self.c["line"])  # 1px рамка
        self._build()

    def _build(self):
        c = self.c
        box = tk.Frame(self.root, bg=c["bg"], padx=16, pady=12)
        box.pack(fill="both", expand=True, padx=1, pady=1)

        top = tk.Frame(box, bg=c["bg"])
        top.pack(fill="x")
        tk.Label(top, text="⇄", bg=c["acc"], fg="white", font=("Consolas", 10, "bold"),
                 width=2).pack(side="left")
        tk.Label(top, text="  REMOLD", bg=c["bg"], fg=c["mute"],
                 font=("Consolas", 8, "bold")).pack(side="left")
        self.close_btn = tk.Label(top, text=t("quick.cancel"), bg=c["bg"], fg=c["mute"], cursor="hand2",
                                  font=("Segoe UI", 9, "underline"))
        self.close_btn.pack(side="right")
        self.close_btn.bind("<Button-1>", lambda _e: self._on_close_click())

        name = self.src.name if len(self.src.name) <= 44 else self.src.name[:41] + "…"
        tk.Label(box, text=name, bg=c["bg"], fg=c["ink"], anchor="w",
                 font=("Segoe UI", 10, "bold")).pack(fill="x", pady=(8, 0))
        self.status = tk.Label(box, text=t("quick.queued", fmt=self.target.upper()), bg=c["bg"],
                               fg=c["mute"], anchor="w", font=("Segoe UI", 9))
        self.status.pack(fill="x")

        self.bar = tk.Canvas(box, height=4, bg=c["line"], highlightthickness=0, bd=0)
        self.bar.pack(fill="x", pady=(8, 0))
        self.fill = self.bar.create_rectangle(0, 0, 0, 4, fill=c["acc"], width=0)

    # --- робота --------------------------------------------------------------

    def run(self) -> int:
        threading.Thread(target=self._work, daemon=True).start()
        self.root.after(SHOW_AFTER_MS, self._show)
        self.root.after(80, self._poll)
        self.root.after(300, self._compact)
        self.root.mainloop()
        if self.slot_handle:
            kernel32.ReleaseMutex(self.slot_handle)
            kernel32.CloseHandle(self.slot_handle)
        return self.exit_code

    def _work(self):
        sem = kernel32.CreateSemaphoreW(None, MAX_PARALLEL, MAX_PARALLEL, "Local\\Remold.quick")
        try:
            while True:  # чекаємо своєї черги, але реагуємо на «Скасувати»
                if self.cancel_event.is_set():
                    raise core.Cancelled()
                if kernel32.WaitForSingleObject(sem, 200) in (WAIT_OBJECT_0, WAIT_ABANDONED):
                    break
            try:
                self.events.put(("progress", 0.0))
                job = core.Job(self.src, self.target, None, store.options_from(self.settings),
                               self.cancel_event, "{name}")
                result = core.convert(job, lambda p: self.events.put(("progress", p)))
                try:
                    store.append_history(store.history_entry(self.src, self.target, result))
                except OSError:
                    pass
                self.events.put(("done", result))
            finally:
                kernel32.ReleaseSemaphore(sem, 1, None)
        except core.Cancelled:
            self.events.put(("cancelled", None))
        except Exception as exc:
            self.events.put(("error", str(exc) or exc.__class__.__name__))
        finally:
            kernel32.CloseHandle(sem)

    def _poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "progress":
                    self.status.config(text=t("quick.progress", fmt=self.target.upper(), p=int(data * 100)))
                    self._set_bar(data, self.c["acc"])
                elif kind == "done":
                    self._finish(t("quick.done", name=Path(data).name), self.c["ok"], close_ms=1400)
                elif kind == "cancelled":
                    self._finish(t("quick.cancelled"), self.c["mute"], close_ms=600)
                elif kind == "error":
                    self.exit_code = 1
                    first = data.strip().splitlines()[0] if data.strip() else t("quick.error")
                    self._finish(f"✗ {first[:80]}", self.c["err"], close_ms=None)
                    self._show()  # про помилку повідомляємо завжди
        except queue.Empty:
            pass
        if not self.finished:
            self.root.after(80, self._poll)

    def _set_bar(self, p: float, color: str):
        w = self.bar.winfo_width() or WIDTH
        self.bar.coords(self.fill, 0, 0, int(w * max(0.0, min(1.0, p))), 4)
        self.bar.itemconfig(self.fill, fill=color)

    def _finish(self, text: str, color: str, close_ms: int | None):
        self.finished = True
        self.status.config(text=text, fg=color)
        self._set_bar(1.0, color)
        self.close_btn.config(text=t("quick.close"))
        if close_ms is not None:
            # швидка конвертація без показаного вікна — просто виходимо
            delay = close_ms if self.root.state() != "withdrawn" else 0
            self.root.after(delay, self.root.destroy)

    def _slot_y(self, slot: int) -> int:
        return self.root.winfo_screenheight() - (HEIGHT + MARGIN) * (slot + 1) - 48  # над панеллю задач

    def _show(self):
        if self.finished and self.exit_code == 0:
            return
        if self.root.state() == "withdrawn":
            x = self.root.winfo_screenwidth() - WIDTH - MARGIN
            self.root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{self._slot_y(self.slot)}")
            self.root.deiconify()

    def _compact(self):
        """Коли вікно нижче закрилось, займаємо його місце — без дірок у стопці."""
        if self.slot > 0:
            slot, handle = _take_slot(below=self.slot)
            if handle:
                if self.slot_handle:
                    kernel32.ReleaseMutex(self.slot_handle)
                    kernel32.CloseHandle(self.slot_handle)
                old_y = self._slot_y(self.slot)
                self.slot, self.slot_handle = slot, handle
                if self.root.state() != "withdrawn":
                    self._slide(old_y, self._slot_y(slot))
        self.root.after(300, self._compact)

    def _slide(self, y_from: int, y_to: int, step: int = 0, steps: int = 8):
        x = self.root.winfo_screenwidth() - WIDTH - MARGIN
        t = (step + 1) / steps
        y = round(y_from + (y_to - y_from) * (1 - (1 - t) ** 3))  # ease-out
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")
        if step + 1 < steps:
            self.root.after(16, self._slide, y_from, y_to, step + 1, steps)

    def _on_close_click(self):
        if self.finished:
            self.root.destroy()
        else:
            self.cancel_event.set()


def run(paths: list[str], target: str) -> int:
    settings = store.load_settings()
    code = 0
    for raw in paths:
        src = Path(raw).resolve()
        if not src.is_file():
            continue
        target = core.normalize_ext(target)
        if target not in core.target_formats(src):
            _message(f"{src.name}: " + t("err.unsupported", src=core.file_ext(src).upper(), dst=target.upper()))
            code = 1
            continue
        code |= QuickWindow(src, target, settings).run()
    return code


def _message(text: str) -> None:
    # MB_ICONWARNING | MB_SETFOREGROUND | MB_TOPMOST
    ctypes.windll.user32.MessageBoxW(None, text, "Remold", 0x30 | 0x10000 | 0x40000)
