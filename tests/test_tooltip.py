# -*- coding: utf-8 -*-
"""
Tests for ToolTip that do not require a visible Tk window or mainloop.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import pytest

from ai_context_studio.ui import tooltip as tooltip_mod
from ai_context_studio.ui.tooltip import (
    ToolTip,
    add_tooltip,
    cancel_pending_show,
    compute_tooltip_position,
)


class FakeWidget:
    """Stand-in for a Tk widget. ``after`` records callbacks and never fires them."""

    def __init__(self) -> None:
        self.bindings: list[tuple[str, Any]] = []
        self.after_calls: list[tuple[int, Callable[..., Any], str]] = []
        self.cancelled_ids: list[str] = []
        self._seq = 0
        self._pending: dict[str, Callable[..., Any]] = {}
        self.fail_after = False

    def bind(self, sequence: str, func: Any) -> None:
        self.bindings.append((sequence, func))

    def after(self, ms: int, func: Callable[..., Any]) -> str:
        if self.fail_after:
            raise RuntimeError("invalid command")
        self._seq += 1
        handle = f"after-{self._seq}"
        self.after_calls.append((ms, func, handle))
        self._pending[handle] = func
        return handle

    def after_cancel(self, handle: str) -> None:
        self.cancelled_ids.append(handle)
        self._pending.pop(handle, None)

    def fire_after(self, handle: Optional[str] = None) -> None:
        """Invoke a recorded callback only when a test opts in."""
        if handle is None:
            handle = self.after_calls[-1][2]
        func = self._pending.pop(handle)
        func()


class FakeWindow:
    """Minimal tooltip window with a destroy() hook."""

    def __init__(self, *, fail_destroy: bool = False) -> None:
        self.destroyed = False
        self._fail_destroy = fail_destroy

    def destroy(self) -> None:
        if self._fail_destroy:
            raise RuntimeError("already destroyed")
        self.destroyed = True


class TestAddTooltipAndConstruction:
    """Construction and bind() wiring."""

    def test_add_tooltip_returns_tooltip(self) -> None:
        widget = FakeWidget()
        tip = add_tooltip(widget, "Help text")

        assert isinstance(tip, ToolTip)
        assert tip.widget is widget
        assert tip.text == "Help text"
        assert tip.delay == 500
        assert tip.tooltip_window is None
        assert tip.scheduled_id is None

    def test_add_tooltip_passes_custom_delay(self) -> None:
        widget = FakeWidget()
        tip = add_tooltip(widget, "Later", delay=1200)

        assert tip.delay == 1200

    def test_construction_binds_enter_leave_and_click(self) -> None:
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint")

        sequences = [seq for seq, _ in widget.bindings]
        assert sequences == ["<Enter>", "<Leave>", "<Button-1>"]

        callbacks = dict(widget.bindings)
        assert callbacks["<Enter>"] == tip._on_enter
        assert callbacks["<Leave>"] == tip._on_leave
        assert callbacks["<Button-1>"] == tip._on_leave


class TestDelayShowHide:
    """Hover delay, cancel, and hide without Tk mainloop."""

    def test_enter_schedules_show_after_delay(self) -> None:
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint", delay=750)

        tip._on_enter()

        assert len(widget.after_calls) == 1
        ms, callback, handle = widget.after_calls[0]
        assert ms == 750
        assert callback == tip._show_tooltip
        assert tip.scheduled_id == handle
        assert handle in widget._pending

    def test_leave_cancels_pending_show(self) -> None:
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint")

        tip._on_enter()
        handle = tip.scheduled_id
        tip._on_leave()

        assert handle in widget.cancelled_ids
        assert tip.scheduled_id is None
        assert handle not in widget._pending
        assert tip.tooltip_window is None

    def test_leave_with_no_pending_job_is_noop_and_second_leave_is_safe(self) -> None:
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint")

        tip._on_leave()
        tip._on_leave()

        assert widget.cancelled_ids == []
        assert widget.after_calls == []
        assert tip.scheduled_id is None
        assert tip.tooltip_window is None

    def test_leave_hides_existing_window(self) -> None:
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint")
        window = FakeWindow()
        tip.tooltip_window = window  # type: ignore[assignment]

        tip._on_leave()

        assert window.destroyed is True
        assert tip.tooltip_window is None

    def test_hide_tooltip_noop_when_no_window(self) -> None:
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint")

        tip._hide_tooltip()

        assert tip.tooltip_window is None

    def test_hide_tooltip_swallows_destroy_errors(self) -> None:
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint")
        tip.tooltip_window = FakeWindow(fail_destroy=True)  # type: ignore[assignment]

        tip._hide_tooltip()

        assert tip.tooltip_window is None

    def test_show_tooltip_noop_if_already_visible(self) -> None:
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint")
        existing = FakeWindow()
        tip.tooltip_window = existing  # type: ignore[assignment]

        tip._show_tooltip()

        assert tip.tooltip_window is existing
        assert existing.destroyed is False

    def test_show_tooltip_swallows_toplevel_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint")

        def boom(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("no display")

        monkeypatch.setattr(tooltip_mod.tk, "Toplevel", boom)
        tip._show_tooltip()

        assert tip.tooltip_window is None

    def test_enter_then_manual_fire_uses_patched_toplevel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Firing the scheduled callback must not create a real Tk window."""
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint", delay=100)

        def fake_toplevel(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("refuse real window")

        monkeypatch.setattr(tooltip_mod.tk, "Toplevel", fake_toplevel)
        tip._on_enter()
        widget.fire_after()

        assert tip.tooltip_window is None

    def test_reenter_cancels_previous_pending_show(self) -> None:
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint", delay=400)

        tip._on_enter()
        first = tip.scheduled_id
        tip._on_enter()
        second = tip.scheduled_id

        assert first is not None
        assert second is not None
        assert first != second
        assert first in widget.cancelled_ids
        assert first not in widget._pending
        assert second in widget._pending
        assert tip.scheduled_id == second
        assert widget.after_calls[0][0] == 400
        assert widget.after_calls[1][0] == 400

    def test_enter_swallows_after_errors(self) -> None:
        """Destroyed widgets raise TclError from after(); hover-enter must not crash."""
        widget = FakeWidget()
        tip = ToolTip(widget, "Hint")

        tip._on_enter()
        first = tip.scheduled_id
        widget.fail_after = True

        tip._on_enter()

        assert first is not None
        assert first in widget.cancelled_ids
        assert tip.scheduled_id is None


class TestCancelPendingShow:
    """Pure cancel helper — no Tk widgets or Toplevel."""

    def test_cancels_when_id_is_present(self) -> None:
        cancelled: list[str] = []

        cancel_pending_show("after-1", cancelled.append)

        assert cancelled == ["after-1"]

    def test_noop_when_id_is_none(self) -> None:
        cancelled: list[str] = []

        cancel_pending_show(None, cancelled.append)

        assert cancelled == []

    def test_treats_empty_string_as_pending(self) -> None:
        cancelled: list[str] = []

        cancel_pending_show("", cancelled.append)

        assert cancelled == [""]

    def test_cancel_when_no_job_pending_is_noop_and_second_cancel_is_safe(self) -> None:
        cancelled: list[str] = []

        cancel_pending_show(None, cancelled.append)
        cancel_pending_show(None, cancelled.append)

        assert cancelled == []

    def test_swallows_after_cancel_errors(self) -> None:
        """Destroyed widgets raise TclError; hover-leave must not crash."""
        cancelled: list[str] = []

        def boom(handle: str) -> None:
            cancelled.append(handle)
            raise RuntimeError("invalid command")

        cancel_pending_show("after-gone", boom)

        assert cancelled == ["after-gone"]


class TestComputeTooltipPosition:
    """Pure placement helper — no Tk widgets required."""

    def test_default_below_and_to_the_right(self) -> None:
        x, y = compute_tooltip_position(
            widget_x=100,
            widget_y=50,
            widget_height=20,
            tooltip_width=80,
            tooltip_height=30,
            screen_width=800,
            screen_height=600,
        )
        assert (x, y) == (110, 75)

    def test_flips_left_when_overflowing_right_edge(self) -> None:
        x, y = compute_tooltip_position(
            widget_x=750,
            widget_y=50,
            widget_height=20,
            tooltip_width=200,
            tooltip_height=30,
            screen_width=800,
            screen_height=600,
        )
        assert x == 800 - 200 - 20
        assert y == 75

    def test_flips_above_when_overflowing_bottom_edge(self) -> None:
        x, y = compute_tooltip_position(
            widget_x=100,
            widget_y=560,
            widget_height=30,
            tooltip_width=80,
            tooltip_height=40,
            screen_width=800,
            screen_height=600,
        )
        assert x == 110
        assert y == 560 - 40 - 5

    def test_clamps_to_minimum_origin(self) -> None:
        x, y = compute_tooltip_position(
            widget_x=0,
            widget_y=0,
            widget_height=10,
            tooltip_width=500,
            tooltip_height=400,
            screen_width=200,
            screen_height=100,
        )
        assert x == 10
        assert y == 10

    def test_clamps_left_and_top_when_position_would_be_negative(self) -> None:
        x, y = compute_tooltip_position(
            widget_x=-30,
            widget_y=-50,
            widget_height=20,
            tooltip_width=80,
            tooltip_height=30,
            screen_width=800,
            screen_height=600,
        )
        assert x == 10
        assert y == 10

    def test_clamps_when_overflowing_right_and_bottom_of_screen_rect(self) -> None:
        x, y = compute_tooltip_position(
            widget_x=5,
            widget_y=5,
            widget_height=10,
            tooltip_width=195,
            tooltip_height=75,
            screen_width=200,
            screen_height=80,
        )
        assert x == 200 - 195
        assert y == 80 - 75
        assert x + 195 <= 200
        assert y + 75 <= 80
