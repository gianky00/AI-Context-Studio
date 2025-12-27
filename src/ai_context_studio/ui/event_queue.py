# -*- coding: utf-8 -*-
"""
Thread-safe event queue for UI updates.

Allows background threads to safely schedule UI updates
in the main thread.
"""

from __future__ import annotations

import logging
import queue
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Import CTk only when needed (may not be available)
try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    CTK_AVAILABLE = False


class UIEventQueue:
    """
    Thread-safe queue for UI event handling.

    Allows background threads to safely queue callbacks
    that will be executed in the main UI thread.

    Attributes:
        _root: The root CTk window
        _queue: Thread-safe queue for callbacks
        _running: Whether the queue is active
    """

    def __init__(self, root: Any) -> None:
        """
        Initialize the event queue.

        Args:
            root: The root CTk/Tk window.
        """
        self._root = root
        self._queue: queue.Queue[
            tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]
        ] = queue.Queue()
        self._running = True
        self._poll()

    def _poll(self) -> None:
        """Poll the queue and execute pending callbacks."""
        while not self._queue.empty():
            try:
                callback, args, kwargs = self._queue.get_nowait()
                callback(*args, **kwargs)
            except queue.Empty:
                break
            except Exception as e:
                logger.error("Error executing queued callback: %s", e)

        if self._running:
            self._root.after(50, self._poll)

    def put(
        self,
        callback: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> None:
        """
        Queue a callback for execution in the UI thread.

        Args:
            callback: Function to call.
            *args: Positional arguments to pass.
            **kwargs: Keyword arguments to pass.
        """
        self._queue.put((callback, args, kwargs))

    def stop(self) -> None:
        """Stop the event queue polling."""
        self._running = False
        logger.debug("Event queue stopped")
