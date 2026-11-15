"""Одне вікно Remold на користувача.

Коли в провіднику вибрано кілька файлів і натиснуто «Відкрити в Remold…», Windows
запускає окремий процес на кожен файл. Перший процес відкриває іменований канал
(named pipe) і показує вікно; решта знаходять канал, передають свої файли й одразу
завершуються. Так само, якщо вікно вже відкрите, нові файли додаються в його чергу.

Створення каналу з FILE_FLAG_FIRST_PIPE_INSTANCE (так робить multiprocessing) атомарне:
з кількох процесів, що стартували одночасно, сервером стає рівно один.
"""
from __future__ import annotations

import getpass
import threading
from multiprocessing.connection import Client, Listener
from typing import Callable

_AUTHKEY = b"remold-instance-v1"
CONNECT_TIMEOUT = 8.0  # перший процес може ще запускатися


def _address() -> str:
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    safe = "".join(ch if ch.isalnum() else "_" for ch in user)
    return rf"\\.\pipe\Remold-{safe}-window"


class Server:
    """Приймає файли від інших запусків Remold і передає їх у on_paths(list[str])."""

    def __init__(self, listener: Listener):
        self._listener = listener
        self._on_paths: Callable[[list[str]], None] | None = None
        self._pending: list[list[str]] = []
        self._lock = threading.Lock()
        self._closed = False
        threading.Thread(target=self._loop, daemon=True).start()

    def bind(self, on_paths: Callable[[list[str]], None]) -> None:
        """Підключити обробник; файли, що прийшли раніше, віддаються йому одразу."""
        with self._lock:
            self._on_paths = on_paths
            pending, self._pending = self._pending, []
        for paths in pending:
            on_paths(paths)

    def _loop(self) -> None:
        while not self._closed:
            try:
                conn = self._listener.accept()
            except Exception:
                if self._closed:
                    return
                continue
            try:
                with conn:
                    msg = conn.recv()
                    conn.send("ok")
            except Exception:
                continue
            paths = [p for p in (msg.get("paths") or []) if isinstance(p, str)] if isinstance(msg, dict) else []
            with self._lock:
                handler = self._on_paths
                if handler is None:
                    self._pending.append(paths)
                    continue
            try:
                handler(paths)
            except Exception:
                pass

    def close(self) -> None:
        self._closed = True
        try:
            self._listener.close()
        except Exception:
            pass


def acquire(paths: list[str]) -> Server | None:
    """Server, якщо цей процес — перше вікно; None, якщо файли передано вже відкритому."""
    address = _address()
    try:
        return Server(Listener(address, family="AF_PIPE", authkey=_AUTHKEY))
    except OSError:
        pass  # канал уже є: працює інший екземпляр
    if _forward(address, paths):
        return None
    # інший екземпляр саме закривається — пробуємо стати першим ще раз
    try:
        return Server(Listener(address, family="AF_PIPE", authkey=_AUTHKEY))
    except OSError:
        pass
    if _forward(address, paths):
        return None
    # ні канал, ні з'єднання не вдалися — краще окреме вікно, ніж жодного
    return _Standalone()


class _Standalone(Server):
    """Замінник сервера, коли канал недоступний: вікно працює без об'єднання запусків."""

    def __init__(self):  # без потоку й каналу
        self._on_paths = None
        self._pending = []
        self._lock = threading.Lock()
        self._closed = True

    def close(self) -> None:
        pass


def _forward(address: str, paths: list[str]) -> bool:
    _allow_foreground()
    import time
    deadline = time.monotonic() + CONNECT_TIMEOUT
    while True:
        try:
            with Client(address, family="AF_PIPE", authkey=_AUTHKEY) as conn:
                conn.send({"paths": list(paths)})
                return conn.recv() == "ok"
        except (FileNotFoundError, ConnectionRefusedError):
            return False  # каналу немає
        except Exception:
            if time.monotonic() > deadline:
                return False
            time.sleep(0.15)


def _allow_foreground() -> None:
    """Дозволити першому вікну вийти на передній план (інакше Windows лише блимне кнопкою)."""
    try:
        import ctypes
        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
    except (AttributeError, OSError):
        pass
