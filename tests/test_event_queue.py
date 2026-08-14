# -*- coding: utf-8 -*-
"""
Tests for UIEventQueue that do not require a real Tk window.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

import pytest

from ai_context_studio.ui.event_queue import UIEventQueue


class FakeRoot:
    """Minimal stand-in for a Tk/CTk root.

    ``after`` records scheduled polls and does not invoke them, so
    ``UIEventQueue.__init__`` cannot recurse infinitely.
    """

    def __init__(self) -> None:
        self.scheduled: list[tuple[int, Callable[..., Any]]] = []

    def after(self, ms: int, callback: Callable[..., Any]) -> None:
        self.scheduled.append((ms, callback))


class TestUIEventQueue:
    """Tests for thread-safe UI event queue polling."""

    def test_init_schedules_poll_without_recursing(self) -> None:
        """Constructing the queue should schedule one after() poll, not loop."""
        root = FakeRoot()
        eq = UIEventQueue(root)

        assert eq._running is True
        assert len(root.scheduled) == 1
        delay, callback = root.scheduled[0]
        assert delay == 50
        assert callback == eq._poll

    def test_put_queues_callback_executed_on_poll(self) -> None:
        """put() should queue a callback; _poll() executes it."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        called: list[int] = []

        eq.put(called.append, 1)

        assert called == []
        eq._poll()
        assert called == [1]

    def test_put_with_no_extra_args(self) -> None:
        """put(callback) with no args or kwargs should still execute on poll."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        called: list[bool] = []

        def mark() -> None:
            called.append(True)

        eq.put(mark)
        assert called == []
        eq._poll()
        assert called == [True]

    def test_put_passes_args_and_kwargs(self) -> None:
        """Queued callbacks should receive positional and keyword arguments."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        seen: list[tuple[Any, ...]] = []

        def record(a: int, b: int, *, flag: bool) -> None:
            seen.append((a, b, flag))

        eq.put(record, 10, 20, flag=True)
        eq._poll()

        assert seen == [(10, 20, True)]

    def test_put_kwargs_only(self) -> None:
        """put(callback, **kwargs) with no positional args should still execute."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        seen: list[dict[str, Any]] = []

        def record(*, name: str, count: int) -> None:
            seen.append({"name": name, "count": count})

        eq.put(record, name="alpha", count=3)
        assert seen == []
        eq._poll()
        assert seen == [{"name": "alpha", "count": 3}]

    def test_put_fifo_order(self) -> None:
        """Multiple put()s should execute in FIFO order on a single poll."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        order: list[str] = []

        eq.put(order.append, "a")
        eq.put(order.append, "b")
        eq.put(order.append, "c")
        eq._poll()

        assert order == ["a", "b", "c"]

    def test_subsequent_poll_drains_remaining_items(self) -> None:
        """Items queued after one drain should run on the next _poll()."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        seen: list[int] = []

        eq.put(seen.append, 1)
        eq._poll()
        assert seen == [1]
        assert eq._queue.empty()

        eq.put(seen.append, 2)
        eq.put(seen.append, 3)
        eq._poll()

        assert seen == [1, 2, 3]
        assert eq._queue.empty()

    def test_stop_prevents_reschedule(self) -> None:
        """stop() should set _running False so further polls do not reschedule."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        assert len(root.scheduled) == 1

        eq.stop()

        assert eq._running is False
        eq._poll()
        assert len(root.scheduled) == 1

    def test_poll_reschedules_while_running(self) -> None:
        """While running, each _poll() should schedule the next after()."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        assert len(root.scheduled) == 1

        eq._poll()

        assert len(root.scheduled) == 2
        assert root.scheduled[1] == (50, eq._poll)

    def test_callback_exception_does_not_crash_poll(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Callback exceptions should be logged; remaining callbacks still run."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        order: list[str] = []

        def boom() -> None:
            raise RuntimeError("boom")

        eq.put(order.append, "before")
        eq.put(boom)
        eq.put(order.append, "after")

        with caplog.at_level(logging.ERROR, logger="ai_context_studio.ui.event_queue"):
            eq._poll()

        assert order == ["before", "after"]
        assert "Error executing queued callback" in caplog.text
        assert "boom" in caplog.text

    def test_poll_empty_queue_is_noop(self) -> None:
        """Polling with nothing queued should not raise and should reschedule."""
        root = FakeRoot()
        eq = UIEventQueue(root)

        eq._poll()
        eq._poll()

        assert eq._queue.empty()
        assert len(root.scheduled) == 3

    def test_put_from_worker_then_drain_on_ui_thread(self) -> None:
        """put() on a worker thread must be visible to a later UI-thread drain."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        results: list[int] = []
        done = threading.Event()

        def worker() -> None:
            eq.put(results.append, 7)
            eq.put(results.append, 8)
            done.set()

        thread = threading.Thread(target=worker, name="event-queue-worker")
        thread.start()
        assert done.wait(timeout=2.0)
        thread.join(timeout=2.0)
        assert not thread.is_alive()

        assert results == []
        eq._poll()
        assert results == [7, 8]
        assert eq._queue.empty()

    def test_put_after_stop_is_ignored(self) -> None:
        """put() after stop() must not enqueue; a later _poll must not run it."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        called: list[int] = []

        eq.stop()
        eq.put(called.append, 1)

        assert eq._queue.empty()
        eq._poll()
        assert called == []

    def test_put_before_stop_still_executes_on_poll(self) -> None:
        """Callbacks queued before stop() must still run on a subsequent _poll."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        called: list[int] = []

        eq.put(called.append, 1)
        eq.stop()

        assert not eq._queue.empty()
        eq._poll()
        assert called == [1]
        assert eq._queue.empty()

    def test_stop_is_idempotent(self) -> None:
        """Calling stop() more than once must stay stopped and keep ignoring put()."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        called: list[int] = []

        eq.stop()
        eq.stop()
        eq.stop()

        assert eq._running is False
        eq.put(called.append, 1)
        assert eq._queue.empty()
        eq._poll()
        assert called == []
        assert len(root.scheduled) == 1

    def test_poll_after_failure_stops_without_raising(self) -> None:
        """Destroyed-root after() must not raise; polling must stop."""
        root = FakeRoot()
        eq = UIEventQueue(root)
        assert eq._running is True
        assert len(root.scheduled) == 1

        def boom_after(_ms: int, _callback: Callable[..., Any]) -> None:
            raise RuntimeError('invalid command name "."')

        root.after = boom_after  # type: ignore[method-assign]

        eq._poll()

        assert eq._running is False

        after_calls: list[int] = []

        def counting_after(ms: int, _callback: Callable[..., Any]) -> None:
            after_calls.append(ms)
            raise RuntimeError("should not be called")

        root.after = counting_after  # type: ignore[method-assign]
        eq._poll()
        assert after_calls == []
        assert len(root.scheduled) == 1
