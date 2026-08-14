# -*- coding: utf-8 -*-
"""Tests for CostHistoryWindow helpers that do not require a Tk window."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ai_context_studio.token_estimator import CostHistoryEntry, Currency
from ai_context_studio.ui.cost_history_window import (
    EMPTY_HISTORY_LABEL,
    empty_history_label,
    filter_entries_by_currency,
    filter_entries_by_date_range,
    format_history_row,
    select_table_entries,
)


def _entry(
    *,
    timestamp: str = "2026-08-13T12:30:00",
    model_id: str = "gemini-2.5-flash",
    estimated_tokens: int = 1500,
    actual_tokens: Optional[int] = 1400,
    estimated_cost: float = 0.0123,
    actual_cost: Optional[float] = 0.0111,
    currency: str = "EUR",
    content_type: str = "code",
) -> CostHistoryEntry:
    return CostHistoryEntry(
        timestamp=timestamp,
        model_id=model_id,
        estimated_tokens=estimated_tokens,
        actual_tokens=actual_tokens,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        currency=currency,
        content_type=content_type,
    )


class TestFormatHistoryRow:
    """Row text extracted from the cost-history table."""

    def test_formats_recorded_actuals(self) -> None:
        date_str, model, estimated, actual, cost = format_history_row(
            _entry(),
            Currency.EUR,
        )
        assert date_str == "13/08/2026 12:30"
        assert model == "2.5-flash"
        assert estimated == "1,500"
        assert actual == "1,400"
        assert cost == "€0.0111"

    def test_estimated_cost_uses_tilde_when_actual_missing(self) -> None:
        _date, _model, _estimated, actual, cost = format_history_row(
            _entry(actual_tokens=None, actual_cost=None),
            Currency.USD,
        )
        assert actual == "-"
        assert cost == "~$0.0123"

    def test_actual_cost_none_uses_estimated_even_with_tokens(self) -> None:
        _date, _model, _estimated, actual, cost = format_history_row(
            _entry(actual_tokens=1400, actual_cost=None),
            Currency.EUR,
        )
        assert actual == "1,400"
        assert cost == "~€0.0123"

    def test_zero_actuals_are_shown(self) -> None:
        _date, _model, _estimated, actual, cost = format_history_row(
            _entry(actual_tokens=0, actual_cost=0.0),
            Currency.EUR,
        )
        assert actual == "0"
        assert cost == "€0.0000"

    def test_invalid_timestamp_falls_back_to_prefix(self) -> None:
        date_str, *_rest = format_history_row(
            _entry(timestamp="not-a-date"),
            Currency.EUR,
        )
        assert date_str == "not-a-date"

    def test_invalid_timestamp_newline_is_single_line(self) -> None:
        date_str, *_rest = format_history_row(
            _entry(timestamp="foo\nbar-extra"),
            Currency.EUR,
        )
        assert "\n" not in date_str
        assert date_str.count("\n") == 0
        assert "foo" in date_str

    def test_invalid_timestamp_nul_is_stripped(self) -> None:
        date_str, *_rest = format_history_row(
            _entry(timestamp="\x00not-a-date"),
            Currency.EUR,
        )
        assert "\x00" not in date_str
        assert "\0" not in date_str
        assert "not-a-date" in date_str

    def test_invalid_timestamp_del_is_stripped(self) -> None:
        date_str, *_rest = format_history_row(
            _entry(timestamp="bad\x7fstamp"),
            Currency.EUR,
        )
        assert "\x7f" not in date_str

    def test_valid_iso_timestamp_uses_strftime(self) -> None:
        date_str, *_rest = format_history_row(
            _entry(timestamp="2026-08-13T12:30:00"),
            Currency.EUR,
        )
        assert date_str == datetime.fromisoformat("2026-08-13T12:30:00").strftime(
            "%d/%m/%Y %H:%M"
        )
        assert date_str == "13/08/2026 12:30"

    def test_usd_symbol_for_usd_display_currency(self) -> None:
        *_rest, cost = format_history_row(_entry(currency="USD"), Currency.USD)
        assert cost.startswith("$")

    def test_nan_actual_cost_shows_dash(self) -> None:
        *_rest, cost = format_history_row(
            _entry(actual_cost=float("nan")),
            Currency.EUR,
        )
        assert cost == "-"
        assert "nan" not in cost.lower()

    def test_inf_actual_cost_shows_dash(self) -> None:
        *_rest, cost = format_history_row(
            _entry(actual_cost=float("inf")),
            Currency.EUR,
        )
        assert cost == "-"

    def test_negative_inf_actual_cost_shows_dash(self) -> None:
        *_rest, cost = format_history_row(
            _entry(actual_cost=float("-inf")),
            Currency.EUR,
        )
        assert cost == "-"

    def test_finite_actual_cost_still_formatted(self) -> None:
        *_rest, cost = format_history_row(
            _entry(actual_cost=0.4),
            Currency.EUR,
        )
        assert cost == "€0.4000"

    def test_nan_estimated_cost_shows_dash_when_actual_missing(self) -> None:
        *_rest, cost = format_history_row(
            _entry(actual_cost=None, estimated_cost=float("nan")),
            Currency.EUR,
        )
        assert cost == "-"
        assert "nan" not in cost.lower()

    def test_finite_estimated_cost_uses_tilde_when_actual_missing(self) -> None:
        *_rest, cost = format_history_row(
            _entry(actual_tokens=None, actual_cost=None, estimated_cost=0.0123),
            Currency.EUR,
        )
        assert cost == "~€0.0123"

    def test_nan_estimated_tokens_shows_dash(self) -> None:
        _date, _model, estimated, _actual, _cost = format_history_row(
            _entry(estimated_tokens=float("nan")),  # type: ignore[arg-type]
            Currency.EUR,
        )
        assert estimated == "-"
        assert "nan" not in estimated.lower()

    def test_inf_estimated_tokens_shows_dash(self) -> None:
        _date, _model, estimated, _actual, _cost = format_history_row(
            _entry(estimated_tokens=float("inf")),  # type: ignore[arg-type]
            Currency.EUR,
        )
        assert estimated == "-"

    def test_nan_actual_tokens_shows_dash(self) -> None:
        _date, _model, _estimated, actual, _cost = format_history_row(
            _entry(actual_tokens=float("nan")),  # type: ignore[arg-type]
            Currency.EUR,
        )
        assert actual == "-"
        assert "nan" not in actual.lower()

    def test_inf_actual_tokens_shows_dash(self) -> None:
        _date, _model, _estimated, actual, _cost = format_history_row(
            _entry(actual_tokens=float("inf")),  # type: ignore[arg-type]
            Currency.EUR,
        )
        assert actual == "-"

    def test_finite_estimated_tokens_uses_thousands_separator(self) -> None:
        _date, _model, estimated, _actual, _cost = format_history_row(
            _entry(estimated_tokens=1500),
            Currency.EUR,
        )
        assert estimated == "1,500"

    def test_none_actual_tokens_shows_dash(self) -> None:
        _date, _model, _estimated, actual, _cost = format_history_row(
            _entry(actual_tokens=None, actual_cost=None),
            Currency.EUR,
        )
        assert actual == "-"

    def test_row_text_includes_model_id(self) -> None:
        entry = _entry(model_id="gemini-2.5-pro")
        _date, model, *_rest = format_history_row(entry, Currency.EUR)
        assert "2.5-pro" in model
        assert model in entry.model_id

    def test_normal_gemini_model_id_strips_prefix(self) -> None:
        _date, model, *_rest = format_history_row(
            _entry(model_id="gemini-2.5-flash"),
            Currency.EUR,
        )
        assert model == "2.5-flash"
        assert "\n" not in model

    def test_model_id_newline_is_single_line(self) -> None:
        _date, model, *_rest = format_history_row(
            _entry(model_id="gemini-2.5-flash\nextra"),
            Currency.EUR,
        )
        assert "\n" not in model
        assert model.count("\n") == 0
        assert "2.5-flash" in model
        assert not model.startswith("gemini-")

    def test_model_id_nul_is_stripped(self) -> None:
        _date, model, *_rest = format_history_row(
            _entry(model_id="gemini-2.5-\x00flash"),
            Currency.EUR,
        )
        assert "\x00" not in model
        assert "\0" not in model

    def test_model_id_del_is_stripped(self) -> None:
        _date, model, *_rest = format_history_row(
            _entry(model_id="gemini-2.5-flash\x7f"),
            Currency.EUR,
        )
        assert "\x7f" not in model


class TestEmptyHistoryLabel:
    """Empty-state copy when the table has nothing to show."""

    def test_empty_list_returns_placeholder(self) -> None:
        assert empty_history_label([]) == EMPTY_HISTORY_LABEL
        assert "Nessuna generazione registrata" in EMPTY_HISTORY_LABEL

    def test_non_empty_list_has_no_placeholder(self) -> None:
        assert empty_history_label([_entry()]) == ""


class TestFilterEntriesByCurrency:
    def test_keeps_matching_currency_only(self) -> None:
        eur = _entry(currency="EUR", estimated_tokens=1)
        usd = _entry(currency="USD", estimated_tokens=2)
        gbp = _entry(currency="GBP", estimated_tokens=3)

        filtered = filter_entries_by_currency([eur, usd, gbp], Currency.EUR)

        assert filtered == [eur]

    def test_empty_list_stays_empty(self) -> None:
        assert filter_entries_by_currency([], Currency.EUR) == []

    def test_no_match_returns_empty(self) -> None:
        assert filter_entries_by_currency([_entry(currency="USD")], Currency.EUR) == []


class TestFilterEntriesByDateRange:
    def test_keeps_entries_within_days(self) -> None:
        now = datetime(2026, 8, 13, 12, 0, 0)
        old = _entry(timestamp="2026-07-01T00:00:00", estimated_tokens=1)
        recent = _entry(timestamp="2026-08-10T00:00:00", estimated_tokens=2)

        filtered = filter_entries_by_date_range(
            [old, recent],
            days=7,
            now=now,
        )

        assert filtered == [recent]

    def test_none_days_returns_all(self) -> None:
        entries = [_entry(timestamp="2000-01-01T00:00:00")]
        assert filter_entries_by_date_range(entries, days=None) == entries

    def test_invalid_timestamp_excluded_when_days_window_active(self) -> None:
        now = datetime(2026, 8, 13, 12, 0, 0)
        invalid = _entry(timestamp="not-a-date", estimated_tokens=1)
        inside = _entry(timestamp="2026-08-01T00:00:00", estimated_tokens=2)

        filtered = filter_entries_by_date_range(
            [invalid, inside],
            days=30,
            now=now,
        )

        assert filtered == [inside]
        assert invalid not in filtered

    def test_none_days_keeps_invalid_timestamps(self) -> None:
        invalid = _entry(timestamp="not-a-date", estimated_tokens=1)
        valid = _entry(timestamp="2026-08-01T00:00:00", estimated_tokens=2)

        assert filter_entries_by_date_range(
            [invalid, valid],
            days=None,
        ) == [invalid, valid]

    def test_aware_stamp_vs_naive_now_does_not_raise(self) -> None:
        now = datetime(2026, 8, 13, 18, 0, 0)
        aware = _entry(timestamp="2026-08-13T12:00:00+00:00", estimated_tokens=1)
        old = _entry(timestamp="2026-07-01T00:00:00", estimated_tokens=2)

        filtered = filter_entries_by_date_range(
            [aware, old],
            days=7,
            now=now,
        )

        assert filtered == [aware]

    def test_naive_stamp_vs_aware_now_does_not_raise(self) -> None:
        now = datetime(2026, 8, 13, 18, 0, 0, tzinfo=timezone.utc)
        naive = _entry(timestamp="2026-08-13T12:00:00", estimated_tokens=1)
        old = _entry(timestamp="2026-07-01T00:00:00", estimated_tokens=2)

        filtered = filter_entries_by_date_range(
            [naive, old],
            days=7,
            now=now,
        )

        assert filtered == [naive]

    def test_aware_stamp_outside_window_is_excluded(self) -> None:
        now = datetime(2026, 8, 13, 12, 0, 0)
        outside = _entry(timestamp="2026-08-01T00:00:00+00:00", estimated_tokens=1)

        filtered = filter_entries_by_date_range(
            [outside],
            days=7,
            now=now,
        )

        assert filtered == []

    def test_invalid_stamp_dropped_among_mixed_tz_when_days_set(self) -> None:
        now = datetime(2026, 8, 13, 12, 0, 0)
        invalid = _entry(timestamp="not-a-date", estimated_tokens=1)
        aware = _entry(timestamp="2026-08-13T12:00:00+00:00", estimated_tokens=2)

        filtered = filter_entries_by_date_range(
            [invalid, aware],
            days=30,
            now=now,
        )

        assert filtered == [aware]
        assert invalid not in filtered

    def test_none_days_keeps_aware_and_invalid(self) -> None:
        invalid = _entry(timestamp="not-a-date", estimated_tokens=1)
        aware = _entry(timestamp="2026-08-13T12:00:00+00:00", estimated_tokens=2)

        assert filter_entries_by_date_range(
            [invalid, aware],
            days=None,
        ) == [invalid, aware]


class TestSelectTableEntries:
    """Currency + date-range + recency order used by the window table."""

    def test_filters_currency_and_reverses_recent_first(self) -> None:
        older = _entry(timestamp="2026-08-01T00:00:00", estimated_tokens=1)
        newer = _entry(timestamp="2026-08-13T00:00:00", estimated_tokens=2)
        usd = _entry(timestamp="2026-08-14T00:00:00", currency="USD", estimated_tokens=3)

        rows = select_table_entries([older, newer, usd], Currency.EUR)

        assert rows == [newer, older]
        assert empty_history_label(rows) == ""

    def test_empty_after_filter_uses_empty_label(self) -> None:
        rows = select_table_entries([_entry(currency="USD")], Currency.EUR)
        assert rows == []
        assert empty_history_label(rows) == EMPTY_HISTORY_LABEL

    def test_unknown_currency_filter_empty_shows_placeholder_text(self) -> None:
        unknown = _entry(currency="CHF")
        blank = _entry(currency="")
        filtered = filter_entries_by_currency([unknown, blank], Currency.EUR)
        rows = select_table_entries([unknown, blank], Currency.EUR)

        assert filtered == []
        assert rows == []
        label = empty_history_label(rows)
        assert label == EMPTY_HISTORY_LABEL
        assert label == (
            "Nessuna generazione registrata.\n"
            "I costi verranno tracciati automaticamente."
        )

    def test_date_filter_keeps_recent_entries(self) -> None:
        now = datetime(2026, 8, 13, 12, 0, 0)
        old = _entry(timestamp="2026-07-01T00:00:00", estimated_tokens=1)
        recent = _entry(timestamp="2026-08-12T00:00:00", estimated_tokens=2)

        rows = select_table_entries(
            [old, recent],
            Currency.EUR,
            days=7,
            now=now,
        )

        assert rows == [recent]

    def test_date_window_drops_unparseable_stamps(self) -> None:
        now = datetime(2026, 8, 13, 12, 0, 0)
        invalid = _entry(timestamp="not-a-date", estimated_tokens=1)
        inside = _entry(timestamp="2026-08-01T00:00:00", estimated_tokens=2)

        rows = select_table_entries(
            [invalid, inside],
            Currency.EUR,
            days=30,
            now=now,
        )

        assert rows == [inside]
