"""Швидка конвертація з контекстного меню провідника: Remold.exe --quick -t webp "файл".

Результат зберігається поруч з оригіналом, налаштування якості беруться з програми.
Невелике вікно з прогресом з'являється в правому нижньому куті, лише якщо конвертація
триває довше ~0.6 с. Коли в провіднику вибрано кілька файлів, Windows запускає окремий
процес на кожен; одночасно конвертують не більше двох (системний семафор), решта чекають.

Вигляд — як у головному вікні: тонкі лінії, помаранчевий акцент, моноширинні цифри,
кольорова мітка типу файлу зліва. Усе малюється на одному Canvas.
"""
from __future__ import annotations

import ctypes
import queue
import subprocess
import threading
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

import core
import store
from i18n import t

MAX_PARALLEL = 2
SHOW_AFTER_MS = 600
DONE_CLOSE_MS = 2600          # скільки показувати «готово» (пауза, поки курсор над вікном)
WIDTH, HEIGHT, MARGIN, GAP = 380, 96, 16, 10   # логічні пікселі (множаться на масштаб екрана)
MAX_SLOTS = 8

# токени з webui/styles.css
LIGHT = {"surface": "#fafaf8", "line": "#c9c6bd", "track": "#e0ded7", "ink": "#18181b", "ink2": "#3c3b37",
         "mute": "#6b6861", "accent": "#e8590c", "accent_ink": "#a8420a", "accent_soft": "#fbe6d8",
         "ok": "#2b7a4b", "err": "#c2382f", "hover": "#efede8"}
DARK = {"surface": "#17171a", "line": "#3b3b42", "track": "#2a2a2f", "ink": "#eceae4", "ink2": "#c9c7c0",
        "mute": "#9a988f", "accent": "#ff7a1f", "accent_ink": "#ffa25c", "accent_soft": "#3a2414",
        "ok": "#5bc88a", "err": "#f06a6a", "hover": "#1f1f23"}
CATEGORY_COLORS = {"image": "#d9822b", "audio": "#3e9e6e", "video": "#4c7bd9",
                   "document": "#9a6bd1", "data": "#b89a2e", "archive": "#8a8780"}

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
WAIT_OBJECT_0, WAIT_ABANDONED = 0x0, 0x80


def _system_dark() -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def _fmt_size(n: int) -> str:
    b, kb, mb, gb = t("units").split(",")
    m = n / 1048576
    if m >= 1024:
        return f"{m / 1024:.1f} {gb}"
    if m >= 10:
        return f"{round(m)} {mb}"
    if m >= 0.1:
        return f"{m:.1f} {mb}"
    return f"{n} {b}" if n < 1024 else f"{round(n / 1024)} {kb}"


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


def _dpi_aware() -> None:
    """Чіткий текст на екранах з масштабуванням 125–200% (інакше Windows розмиває вікно)."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


class QuickWindow:
    def __init__(self, src: Path, target: str, settings: dict):
        self.src, self.target = src, target
        self.settings = settings
        self.category = core.detect_category(src) or "archive"
        self.cancel_event = threading.Event()
        self.events: queue.Queue = queue.Queue()
        self.finished = False
        self.exit_code = 0
        self.result: Path | None = None
        self.progress = 0.0
        self.hovered = False
        self.close_job = None
        self.anim_job = None
        self.anim_x = 0.0

        theme = settings.get("theme") or ("dark" if _system_dark() else "light")
        self.c = DARK if theme == "dark" else LIGHT
        self.slot, self.slot_handle = _take_slot()

        _dpi_aware()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(t("quick.title"))
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.k = self.root.winfo_fpixels("1i") / 96  # масштаб екрана
        self.w, self.h = self.px(WIDTH), self.px(HEIGHT)

        mono = "Cascadia Mono" if "Cascadia Mono" in tkfont.families(self.root) else "Consolas"
        self.f_caps = tkfont.Font(self.root, family=mono, size=7, weight="bold")
        self.f_name = tkfont.Font(self.root, family="Segoe UI Semibold", size=10)
        self.f_mono = tkfont.Font(self.root, family=mono, size=8)
        self.f_chip = tkfont.Font(self.root, family=mono, size=8, weight="bold")
        self.f_link = tkfont.Font(self.root, family="Segoe UI", size=9, underline=True)
        self._build()

    def px(self, v: float) -> int:
        return round(v * self.k)

    # --- вигляд --------------------------------------------------------------

    def _build(self):
        c, px, w, h = self.c, self.px, self.w, self.h
        cv = self.cv = tk.Canvas(self.root, width=w, height=h, bg=c["surface"], highlightthickness=0, bd=0)
        cv.pack()
        cv.create_rectangle(0, 0, w - 1, h - 1, outline=c["line"], width=1)
        # кольорова мітка типу файлу — як у рядках черги
        cv.create_rectangle(1, 1, px(3), h - 1, fill=CATEGORY_COLORS.get(self.category, c["mute"]), width=0)

        # логотип і назва програми
        x0, y0, s = px(18), px(13), px(12)
        u = s / 24
        cv.create_polygon(self._mark_points(x0, y0, u), fill=c["accent"], outline="", smooth=False)
        cv.create_rectangle(x0 + 7 * u, y0 + 11 * u, x0 + 13 * u, y0 + 17 * u, fill=c["surface"], width=0)
        cv.create_text(x0 + s + px(8), y0 + s / 2, text="REMOLD", anchor="w", fill=c["mute"], font=self.f_caps)

        # кнопка × (скасувати / закрити)
        bx, by, bs = w - px(30), px(8), px(22)
        self.btn_bg = cv.create_rectangle(bx, by, bx + bs, by + bs, fill=c["surface"], width=0, tags="btn")
        m = px(7)
        for a, b in (((bx + m, by + m), (bx + bs - m, by + bs - m)), ((bx + bs - m, by + m), (bx + m, by + bs - m))):
            cv.create_line(*a, *b, fill=c["mute"], width=max(1, px(1.4)), capstyle="round", tags=("btn", "btn_x"))
        cv.tag_bind("btn", "<Enter>", lambda _e: cv.itemconfig(self.btn_bg, fill=c["hover"]))
        cv.tag_bind("btn", "<Leave>", lambda _e: cv.itemconfig(self.btn_bg, fill=c["surface"]))
        cv.tag_bind("btn", "<Button-1>", lambda _e: self._on_close_click())

        # назва файлу + чип цільового формату
        chip_text = f"→ {self.target.upper()}"
        chip_w = self.f_chip.measure(chip_text) + px(14)
        chip_h = px(20)
        cx1, cy = w - px(16), px(46)
        cv.create_rectangle(cx1 - chip_w, cy - chip_h / 2, cx1, cy + chip_h / 2, fill=c["accent_soft"], width=0)
        cv.create_text(cx1 - chip_w / 2, cy, text=chip_text, fill=c["accent_ink"], font=self.f_chip)
        name_max = (cx1 - chip_w - px(12)) - px(18)
        cv.create_text(px(18), cy, text=self._ellipsize(self.src.name, self.f_name, name_max),
                       anchor="w", fill=c["ink"], font=self.f_name)

        # рядок стану + посилання «Показати в папці»
        self.status = cv.create_text(px(18), px(72), anchor="w", fill=c["mute"], font=self.f_mono,
                                     text=self._status_line(t("quick.queued")))
        self.link = cv.create_text(w - px(16), px(72), anchor="e", fill=c["accent_ink"], font=self.f_link,
                                   text=t("quick.reveal"), state="hidden", tags="link")
        cv.tag_bind("link", "<Button-1>", lambda _e: self._reveal())
        cv.tag_bind("link", "<Enter>", lambda _e: cv.config(cursor="hand2"))
        cv.tag_bind("link", "<Leave>", lambda _e: cv.config(cursor=""))

        # смуга прогресу по нижньому краю
        bh = max(2, px(2))
        self.bar_y = (h - 1 - bh, h - 1)
        cv.create_rectangle(1, self.bar_y[0], w - 1, self.bar_y[1], fill=c["track"], width=0)
        self.fill = cv.create_rectangle(1, self.bar_y[0], 1, self.bar_y[1], fill=c["accent"], width=0)

        self.root.bind("<Enter>", lambda _e: self._set_hover(True))
        self.root.bind("<Leave>", lambda _e: self._set_hover(False))

    @staticmethod
    def _mark_points(x0: float, y0: float, u: float) -> list[float]:
        """Логотип: квадрат, правий верхній кут якого — дуга радіуса 8.5 (як у webui)."""
        import math
        pts = [x0 + 3 * u, y0 + 3 * u, x0 + 12.5 * u, y0 + 3 * u]
        cx, cy, r = x0 + 12.5 * u, y0 + 11.5 * u, 8.5 * u
        for i in range(1, 12):
            a = -math.pi / 2 + (math.pi / 2) * i / 12
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
        pts += [x0 + 21 * u, y0 + 11.5 * u, x0 + 21 * u, y0 + 21 * u, x0 + 3 * u, y0 + 21 * u]
        return pts

    @staticmethod
    def _ellipsize(text: str, font: tkfont.Font, max_w: int, keep_ext: bool = True) -> str:
        """Обрізати текст під ширину. Для імені файлу — з середини, зберігши кінець і
        розширення (very_long_na…me.mp4); для звичайного тексту — з кінця."""
        if font.measure(text) <= max_w:
            return text
        tail = ""
        if keep_ext:
            stem, dot, ext = text.rpartition(".")
            if dot and 0 < len(ext) <= 5:
                text, tail = stem, dot + ext
            keep = min(4, len(text) // 3)
            start, end = text[:len(text) - keep], text[len(text) - keep:]
        else:
            start, end = text, ""
        while start and font.measure(start + "…" + end + tail) > max_w:
            start = start[:-1]
        return start + "…" + end + tail

    def _status_line(self, state: str) -> str:
        return f"{core.file_ext(self.src).upper()} → {self.target.upper()}  ·  {state}"

    def _set_status(self, text: str, color: str | None = None):
        self.cv.itemconfig(self.status, text=text, fill=color or self.c["mute"])

    def _set_bar(self, p: float, color: str):
        self._stop_anim()
        x1 = 1 + (self.w - 2) * max(0.0, min(1.0, p))
        self.cv.coords(self.fill, 1, self.bar_y[0], x1, self.bar_y[1])
        self.cv.itemconfig(self.fill, fill=color)

    def _animate_waiting(self):
        """Поки файл чекає черги — сегмент, що біжить смугою (видно, що програма жива)."""
        seg = self.w * 0.22
        self.anim_x = (self.anim_x + self.px(4)) % (self.w + seg)
        x = self.anim_x - seg
        self.cv.coords(self.fill, max(1, x), self.bar_y[0], min(self.w - 1, x + seg), self.bar_y[1])
        self.anim_job = self.root.after(16, self._animate_waiting)

    def _stop_anim(self):
        if self.anim_job:
            self.root.after_cancel(self.anim_job)
            self.anim_job = None

    # --- робота --------------------------------------------------------------

    def run(self) -> int:
        threading.Thread(target=self._work, daemon=True).start()
        self._animate_waiting()
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
                self.events.put(("started", None))
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
                if kind == "started":
                    self._set_status(self._status_line(t("quick.starting")))
                    self._set_bar(0.0, self.c["accent"])
                elif kind == "progress":
                    self.progress = data
                    self._set_status(self._status_line(f"{int(data * 100)}%"), self.c["ink2"])
                    self._set_bar(data, self.c["accent"])
                elif kind == "done":
                    self.result = Path(data)
                    self._finish_done()
                elif kind == "cancelled":
                    self._finish(self._status_line(t("quick.cancelled")), self.c["mute"], close_ms=700)
                elif kind == "error":
                    self.exit_code = 1
                    text = self._ellipsize(f"✗ {self._error_reason(data)}", self.f_mono,
                                           self.w - self.px(34), keep_ext=False)
                    self._finish(text, self.c["err"], close_ms=None)
                    self._show()  # про помилку повідомляємо завжди
        except queue.Empty:
            pass
        if not self.finished:
            self.root.after(80, self._poll)

    @staticmethod
    def _error_reason(message: str) -> str:
        """Найінформативніший рядок помилки: у ffmpeg перший рядок — лише заголовок «… failed:»,
        а причина в останньому."""
        lines = [ln.strip() for ln in message.strip().splitlines() if ln.strip()]
        if not lines:
            return t("quick.error")
        if len(lines) > 1 and lines[0].endswith(":"):
            return lines[-1]
        return lines[0]

    def _finish_done(self):
        before = self.src.stat().st_size
        after = store.total_size(self.result) if self.result.exists() else 0
        change = ""
        if before and after:
            ratio = after / before
            pct = round((1 - ratio) * 100)
            change = f"×{round(ratio)}" if ratio >= 10 else (f"−{pct}%" if pct > 0 else f"+{-pct}%" if pct < 0 else "0%")
        text = f"✓ {_fmt_size(before)} → {_fmt_size(after)}" + (f"  ·  {change}" if change else "")
        self._finish(text, self.c["ok"], close_ms=DONE_CLOSE_MS)
        self.cv.itemconfig(self.link, state="normal")

    def _finish(self, text: str, color: str, close_ms: int | None):
        self.finished = True
        self._set_status(text, color)
        self._set_bar(1.0, color)
        if close_ms is not None:
            # швидка конвертація без показаного вікна — просто виходимо
            self._schedule_close(close_ms if self.root.state() != "withdrawn" else 0)

    def _schedule_close(self, ms: int):
        if self.close_job:
            self.root.after_cancel(self.close_job)
        self.close_job = self.root.after(ms, self._close) if ms >= 0 else None

    def _set_hover(self, on: bool):
        """Поки курсор над вікном, «готово» не зникає — можна натиснути «Показати в папці»."""
        self.hovered = on
        if self.finished and self.exit_code == 0 and self.result is not None:
            if on and self.close_job:
                self.root.after_cancel(self.close_job)
                self.close_job = None
            elif not on:
                self._schedule_close(1200)

    def _close(self):
        self._fade(1.0, -0.2, self.root.destroy)

    def _fade(self, alpha: float, step: float, then=None):
        alpha = max(0.0, min(1.0, alpha + step))
        try:
            self.root.attributes("-alpha", alpha)
        except tk.TclError:
            return
        if (step < 0 and alpha > 0) or (step > 0 and alpha < 1):
            self.root.after(16, self._fade, alpha, step, then)
        elif then:
            then()

    def _reveal(self):
        if self.result and self.result.exists():
            subprocess.Popen(["explorer", "/select,", str(self.result)])
        self._schedule_close(0)

    def _slot_xy(self, slot: int) -> tuple[int, int]:
        x = self.root.winfo_screenwidth() - self.w - self.px(MARGIN)
        y = self.root.winfo_screenheight() - (self.h + self.px(GAP)) * (slot + 1) - self.px(48)  # над панеллю задач
        return x, y

    def _show(self):
        if self.finished and self.exit_code == 0:
            return
        if self.root.state() == "withdrawn":
            x, y = self._slot_xy(self.slot)
            self.root.geometry(f"{self.w}x{self.h}+{x + self.px(14)}+{y}")
            self.root.attributes("-alpha", 0.0)
            self.root.deiconify()
            self._round_corners()
            self._fade(0.0, 0.2)
            self._slide_x(x + self.px(14), x)

    def _round_corners(self):
        """Заокруглені кути у Windows 11 (у Windows 10 виклик просто нічого не змінює)."""
        try:
            hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            pref = ctypes.c_int(3)  # DWMWCP_ROUNDSMALL
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        except (AttributeError, OSError):
            pass

    def _slide_x(self, x_from: int, x_to: int, step: int = 0, steps: int = 8):
        _, y = self._slot_xy(self.slot)
        k = (step + 1) / steps
        x = round(x_from + (x_to - x_from) * (1 - (1 - k) ** 3))
        self.root.geometry(f"+{x}+{y}")
        if step + 1 < steps:
            self.root.after(16, self._slide_x, x_from, x_to, step + 1, steps)

    def _compact(self):
        """Коли вікно нижче закрилось, займаємо його місце — без дірок у стопці."""
        if self.slot > 0:
            slot, handle = _take_slot(below=self.slot)
            if handle:
                if self.slot_handle:
                    kernel32.ReleaseMutex(self.slot_handle)
                    kernel32.CloseHandle(self.slot_handle)
                old_y = self._slot_xy(self.slot)[1]
                self.slot, self.slot_handle = slot, handle
                if self.root.state() != "withdrawn":
                    self._slide_y(old_y, self._slot_xy(slot)[1])
        self.root.after(300, self._compact)

    def _slide_y(self, y_from: int, y_to: int, step: int = 0, steps: int = 10):
        x, _ = self._slot_xy(self.slot)
        k = (step + 1) / steps
        y = round(y_from + (y_to - y_from) * (1 - (1 - k) ** 3))  # ease-out
        self.root.geometry(f"+{x}+{y}")
        if step + 1 < steps:
            self.root.after(16, self._slide_y, y_from, y_to, step + 1, steps)

    def _on_close_click(self):
        if self.finished:
            self._schedule_close(0)
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
    user32.MessageBoxW(None, text, "Remold", 0x30 | 0x10000 | 0x40000)
