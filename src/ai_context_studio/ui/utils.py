import queue
from typing import Callable
import customtkinter as ctk

class UIEventQueue:
    """Coda thread-safe per aggiornamenti UI."""

    def __init__(self, root: ctk.CTk):
        self._root = root
        self._queue: queue.Queue = queue.Queue()
        self._running = True
        self._poll()

    def _poll(self) -> None:
        while not self._queue.empty():
            try:
                callback, args, kwargs = self._queue.get_nowait()
                callback(*args, **kwargs)
            except queue.Empty:
                break
            except Exception as e:
                print(f"UI Error: {e}")

        if self._running:
            self._root.after(50, self._poll)

    def put(self, callback: Callable, *args, **kwargs) -> None:
        self._queue.put((callback, args, kwargs))

    def stop(self) -> None:
        self._running = False
