# -*- coding: utf-8 -*-
"""
Tests for app-level worker shutdown and destroy helpers.

Does not create a CustomTkinter window or start a mainloop.
"""

from __future__ import annotations

from ai_context_studio.app import safe_destroy, shutdown_app_workers


class _Worker:
    def __init__(self) -> None:
        self.calls = 0

    def shutdown(self) -> None:
        self.calls += 1


class _NoShutdown:
    pass


class _Boom:
    def shutdown(self) -> None:
        raise RuntimeError("shutdown failed")


class _CancelOnly:
    def __init__(self) -> None:
        self.cancel_calls = 0

    def cancel(self) -> None:
        self.cancel_calls += 1


class _CancelBoom:
    def cancel(self) -> None:
        raise RuntimeError("cancel failed")


class _CancelAndShutdown:
    def __init__(self) -> None:
        self.order: list[str] = []

    def cancel(self) -> None:
        self.order.append("cancel")

    def shutdown(self) -> None:
        self.order.append("shutdown")


class _DestroyFlag:
    def __init__(self) -> None:
        self.called = False

    def destroy(self) -> None:
        self.called = True


class _DestroyBoom:
    def destroy(self) -> None:
        raise RuntimeError("already destroyed")


class _NoDestroy:
    pass


class TestSafeDestroy:
    """Tests for safe_destroy. Does not instantiate CTk."""

    def test_destroy_exception_does_not_propagate(self) -> None:
        safe_destroy(_DestroyBoom())

    def test_calls_destroy_when_present(self) -> None:
        widget = _DestroyFlag()

        safe_destroy(widget)

        assert widget.called is True

    def test_object_without_destroy_is_noop(self) -> None:
        safe_destroy(_NoDestroy())


class TestShutdownAppWorkers:
    """Tests for shutdown_app_workers."""

    def test_calls_shutdown_when_present(self) -> None:
        worker = _Worker()

        shutdown_app_workers(worker)

        assert worker.calls == 1

    def test_skips_objects_without_shutdown(self) -> None:
        worker = _Worker()

        shutdown_app_workers(_NoShutdown(), worker, None)

        assert worker.calls == 1

    def test_shutdown_exception_does_not_propagate(self) -> None:
        worker = _Worker()

        shutdown_app_workers(_Boom(), worker)

        assert worker.calls == 1

    def test_duplicate_shutdown_objects_called_once_each(self) -> None:
        first = _Worker()
        second = _Worker()

        shutdown_app_workers(first, second)

        assert first.calls == 1
        assert second.calls == 1

    def test_calls_cancel_when_present_without_shutdown(self) -> None:
        worker = _CancelOnly()

        shutdown_app_workers(worker)

        assert worker.cancel_calls == 1

    def test_cancel_exception_does_not_prevent_later_shutdown(self) -> None:
        worker = _Worker()

        shutdown_app_workers(_CancelBoom(), worker)

        assert worker.calls == 1

    def test_calls_cancel_then_shutdown_when_both_present(self) -> None:
        worker = _CancelAndShutdown()

        shutdown_app_workers(worker)

        assert worker.order == ["cancel", "shutdown"]
