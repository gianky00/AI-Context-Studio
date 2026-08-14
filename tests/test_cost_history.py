# -*- coding: utf-8 -*-
"""Tests for CostHistoryManager persistence (offline, no Gemini)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from ai_context_studio import token_estimator as token_estimator_mod
from ai_context_studio.token_estimator import (
    ContentType,
    CostEstimate,
    CostHistoryEntry,
    CostHistoryManager,
    Currency,
)


def _estimate(
    *,
    tokens: int = 100,
    cost: float = 0.01,
    model_id: str = "gemini-2.5-flash",
    currency: Currency = Currency.EUR,
    timestamp: str = "2099-01-01T12:00:00",
) -> CostEstimate:
    return CostEstimate(
        input_tokens=tokens,
        output_tokens=0,
        total_tokens=tokens,
        input_cost=cost,
        output_cost=0.0,
        total_cost=cost,
        currency=currency,
        model_id=model_id,
        model_name=model_id,
        content_type=ContentType.CODE,
        timestamp=timestamp,
    )


def _entry_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "timestamp": "2026-01-01T00:00:00",
        "model_id": "gemini-2.5-flash",
        "estimated_tokens": 10,
        "actual_tokens": None,
        "estimated_cost": 0.1,
        "actual_cost": None,
        "currency": "EUR",
        "content_type": "code",
    }
    payload.update(overrides)
    return payload


class TestCostHistoryEntry:
    def test_from_dict_ignores_unknown_keys(self) -> None:
        entry = CostHistoryEntry.from_dict(
            _entry_payload(future_field="ignore-me")
        )
        assert entry.model_id == "gemini-2.5-flash"
        assert entry.accuracy_ratio is None

    def test_from_dict_coerces_nan_actual_cost_to_none(self) -> None:
        entry = CostHistoryEntry.from_dict(_entry_payload(actual_cost=float("nan")))
        assert entry.actual_cost is None

    def test_from_dict_coerces_inf_actual_cost_to_none(self) -> None:
        pos = CostHistoryEntry.from_dict(_entry_payload(actual_cost=float("inf")))
        assert pos.actual_cost is None

        neg = CostHistoryEntry.from_dict(_entry_payload(actual_cost=float("-inf")))
        assert neg.actual_cost is None

    def test_from_dict_coerces_non_finite_estimated_cost_to_zero(self) -> None:
        nan_entry = CostHistoryEntry.from_dict(
            _entry_payload(estimated_cost=float("nan"))
        )
        assert nan_entry.estimated_cost == 0.0
        assert math.isfinite(nan_entry.estimated_cost)

        inf_entry = CostHistoryEntry.from_dict(
            _entry_payload(estimated_cost=float("inf"))
        )
        assert inf_entry.estimated_cost == 0.0

        neg_inf_entry = CostHistoryEntry.from_dict(
            _entry_payload(estimated_cost=float("-inf"))
        )
        assert neg_inf_entry.estimated_cost == 0.0

    def test_from_dict_keeps_finite_costs(self) -> None:
        entry = CostHistoryEntry.from_dict(
            _entry_payload(estimated_cost=0.25, actual_cost=0.4)
        )
        assert entry.estimated_cost == pytest.approx(0.25)
        assert entry.actual_cost == pytest.approx(0.4)

    def test_from_dict_coerces_non_finite_estimated_tokens_to_zero(self) -> None:
        nan_entry = CostHistoryEntry.from_dict(
            _entry_payload(estimated_tokens=float("nan"))
        )
        assert nan_entry.estimated_tokens == 0
        assert math.isfinite(nan_entry.estimated_tokens)

        inf_entry = CostHistoryEntry.from_dict(
            _entry_payload(estimated_tokens=float("inf"))
        )
        assert inf_entry.estimated_tokens == 0

        neg_inf_entry = CostHistoryEntry.from_dict(
            _entry_payload(estimated_tokens=float("-inf"))
        )
        assert neg_inf_entry.estimated_tokens == 0

    def test_from_dict_coerces_non_finite_actual_tokens_to_none(self) -> None:
        nan_entry = CostHistoryEntry.from_dict(
            _entry_payload(actual_tokens=float("nan"))
        )
        assert nan_entry.actual_tokens is None

        inf_entry = CostHistoryEntry.from_dict(
            _entry_payload(actual_tokens=float("inf"))
        )
        assert inf_entry.actual_tokens is None

        neg_inf_entry = CostHistoryEntry.from_dict(
            _entry_payload(actual_tokens=float("-inf"))
        )
        assert neg_inf_entry.actual_tokens is None

    def test_from_dict_keeps_finite_tokens(self) -> None:
        entry = CostHistoryEntry.from_dict(
            _entry_payload(estimated_tokens=10, actual_tokens=8)
        )
        assert entry.estimated_tokens == 10
        assert entry.actual_tokens == 8

    def test_from_dict_coerces_non_finite_accuracy_ratio_to_none(self) -> None:
        nan_entry = CostHistoryEntry.from_dict(
            _entry_payload(accuracy_ratio=float("nan"))
        )
        assert nan_entry.accuracy_ratio is None

        inf_entry = CostHistoryEntry.from_dict(
            _entry_payload(accuracy_ratio=float("inf"))
        )
        assert inf_entry.accuracy_ratio is None


class TestCostHistoryManager:
    def test_add_entry_persists_and_reloads(self, mock_config_dir: Path) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(tokens=200, cost=0.02), actual_tokens=180)

        history_file = mock_config_dir / "cost_history.json"
        assert history_file.exists()

        reloaded = CostHistoryManager()
        entries = reloaded.get_entries()
        assert len(entries) == 1
        assert entries[0].estimated_tokens == 200
        assert entries[0].actual_tokens == 180
        assert entries[0].accuracy_ratio == 0.9

    def test_actual_tokens_zero_records_accuracy(self, mock_config_dir: Path) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(tokens=50), actual_tokens=0)

        entry = manager.get_entries()[0]
        assert entry.actual_tokens == 0
        assert entry.accuracy_ratio == 0.0

    def test_save_creates_history_file_parent(
        self, mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        nested = mock_config_dir / "nested" / "dir" / "cost_history.json"
        monkeypatch.setattr(CostHistoryManager, "HISTORY_FILE", nested)

        manager = CostHistoryManager()
        manager.add_entry(_estimate())

        assert nested.exists()
        payload = json.loads(nested.read_text(encoding="utf-8"))
        assert len(payload["entries"]) == 1

    def test_max_entries_caps_memory_and_disk(
        self, mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(CostHistoryManager, "MAX_ENTRIES", 3)
        manager = CostHistoryManager()
        for i in range(5):
            manager.add_entry(_estimate(tokens=i + 1, timestamp=f"2099-01-0{i + 1}T00:00:00"))

        assert len(manager.get_entries(limit=100)) == 3
        kept = [e.estimated_tokens for e in manager.get_entries(limit=100)]
        assert kept == [3, 4, 5]

        reloaded = CostHistoryManager()
        assert [e.estimated_tokens for e in reloaded.get_entries(limit=100)] == [3, 4, 5]

    def test_corrupt_json_starts_empty(self, mock_config_dir: Path) -> None:
        history_file = mock_config_dir / "cost_history.json"
        history_file.write_text("{not json", encoding="utf-8")

        manager = CostHistoryManager()
        assert manager.get_entries() == []

    def test_get_total_spend_prefers_actual_cost(self, mock_config_dir: Path) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(cost=1.0), actual_cost=0.4)
        manager.add_entry(_estimate(cost=2.0, currency=Currency.USD))
        manager.add_entry(
            _estimate(cost=9.0, timestamp="2000-01-01T00:00:00"),
            actual_cost=9.0,
        )

        assert manager.get_total_spend(currency="EUR", days=30) == 0.4
        assert manager.get_total_spend(currency="USD", days=30) == 2.0

    def test_get_accuracy_stats_empty_and_filtered(self, mock_config_dir: Path) -> None:
        manager = CostHistoryManager()
        empty = manager.get_accuracy_stats()
        assert empty["count"] == 0
        assert empty["average"] == 1.0

        manager.add_entry(_estimate(tokens=100, model_id="gemini-2.5-flash"), actual_tokens=80)
        manager.add_entry(_estimate(tokens=100, model_id="gemini-2.5-pro"), actual_tokens=120)

        flash = manager.get_accuracy_stats("gemini-2.5-flash")
        assert flash["count"] == 1
        assert flash["average"] == 0.8
        assert flash["min"] == 0.8
        assert flash["max"] == 0.8

        all_stats = manager.get_accuracy_stats()
        assert all_stats["count"] == 2
        assert all_stats["average"] == 1.0

    def test_clear_empties_file(self, mock_config_dir: Path) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate())
        manager.clear()

        assert manager.get_entries() == []
        payload = json.loads(
            (mock_config_dir / "cost_history.json").read_text(encoding="utf-8")
        )
        assert payload["entries"] == []

    def test_save_restricts_history_file(
        self, mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded: list[Path] = []

        def record_restrict(path: Path) -> None:
            recorded.append(Path(path))

        monkeypatch.setattr(
            token_estimator_mod, "restrict_file_permissions", record_restrict
        )

        manager = CostHistoryManager()
        manager.add_entry(_estimate())

        expected = CostHistoryManager.HISTORY_FILE
        assert recorded == [expected]
        assert expected == mock_config_dir / "cost_history.json"
        assert expected.exists()

    def test_save_oserror_does_not_restrict(
        self, mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded: list[Path] = []

        def record_restrict(path: Path) -> None:
            recorded.append(Path(path))

        monkeypatch.setattr(
            token_estimator_mod, "restrict_file_permissions", record_restrict
        )

        def fail_dump(*args: object, **kwargs: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(token_estimator_mod.json, "dump", fail_dump)

        manager = CostHistoryManager()
        manager.add_entry(_estimate())

        assert recorded == []


@pytest.fixture
def isolated_history_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Patch token_estimator CONFIG_DIR and HISTORY_FILE onto a tempfile dir."""
    import ai_context_studio.token_estimator as token_estimator

    config_dir = tmp_path / ".ai_context_studio"
    config_dir.mkdir()
    history_file = config_dir / "cost_history.json"
    monkeypatch.setattr(token_estimator, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(CostHistoryManager, "HISTORY_FILE", history_file)
    return history_file


class TestCostHistoryManagerTempfileIsolation:
    """CostHistoryManager tests that never touch the real home CONFIG_DIR."""

    def test_add_entry_and_get_entries(self, isolated_history_file: Path) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(tokens=250, cost=0.05), actual_tokens=200)

        entries = manager.get_entries()
        assert len(entries) == 1
        assert entries[0].estimated_tokens == 250
        assert entries[0].actual_tokens == 200
        assert entries[0].accuracy_ratio == 0.8
        assert isolated_history_file.exists()
        assert isolated_history_file.parent.name == ".ai_context_studio"

    def test_get_entries_respects_limit(self, isolated_history_file: Path) -> None:
        manager = CostHistoryManager()
        for i in range(5):
            manager.add_entry(_estimate(tokens=i + 1, timestamp=f"2099-02-0{i + 1}T00:00:00"))

        latest = manager.get_entries(limit=2)
        assert [e.estimated_tokens for e in latest] == [4, 5]

    def test_get_total_spend_estimated_and_actual(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(cost=1.5))
        manager.add_entry(_estimate(cost=2.0), actual_cost=0.75)
        manager.add_entry(_estimate(cost=3.0, currency=Currency.USD))

        assert manager.get_total_spend(currency="EUR", days=30) == pytest.approx(2.25)
        assert manager.get_total_spend(currency="USD", days=30) == pytest.approx(3.0)

    def test_get_total_spend_skips_unparseable_timestamps(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(
            _estimate(cost=1.0, timestamp="not-a-date"),
            actual_cost=999.0,
        )
        manager.add_entry(
            _estimate(cost=0.5, timestamp="2099-01-01T12:00:00"),
            actual_cost=0.5,
        )

        assert manager.get_total_spend(currency="EUR", days=30) == pytest.approx(0.5)

    def test_get_total_spend_nan_actual_falls_back_to_estimate(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(
            _estimate(cost=0.3, timestamp="2099-01-01T12:00:00"),
            actual_cost=float("nan"),
        )
        manager.add_entry(
            _estimate(cost=9.0, timestamp="2099-01-01T13:00:00"),
            actual_cost=0.5,
        )
        manager.add_entry(
            _estimate(cost=1.0, timestamp="not-a-date"),
            actual_cost=999.0,
        )

        total = manager.get_total_spend(currency="EUR", days=30)
        assert math.isfinite(total)
        assert total == pytest.approx(0.8)

    def test_get_total_spend_inf_actual_falls_back_to_estimate(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(
            _estimate(cost=0.2, timestamp="2099-01-01T12:00:00"),
            actual_cost=float("inf"),
        )
        manager.add_entry(
            _estimate(cost=0.1, timestamp="2099-01-01T13:00:00"),
            actual_cost=float("-inf"),
        )
        manager.add_entry(
            _estimate(cost=9.0, timestamp="2099-01-01T14:00:00"),
            actual_cost=0.5,
        )
        manager.add_entry(
            _estimate(cost=1.0, timestamp="not-a-date"),
            actual_cost=999.0,
        )

        total = manager.get_total_spend(currency="EUR", days=30)
        assert math.isfinite(total)
        assert total == pytest.approx(0.8)

    def test_get_total_spend_includes_timezone_aware_recent_stamp(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(
            _estimate(cost=1.0, timestamp="2026-08-13T12:00:00+00:00"),
            actual_cost=0.25,
        )
        manager.add_entry(
            _estimate(cost=1.0, timestamp="not-a-date"),
            actual_cost=999.0,
        )

        assert manager.get_total_spend(currency="EUR", days=30) == pytest.approx(0.25)

    def test_get_total_spend_excludes_timezone_aware_old_stamp(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(
            _estimate(cost=9.0, timestamp="2000-01-01T00:00:00+00:00"),
            actual_cost=9.0,
        )
        manager.add_entry(
            _estimate(cost=1.0, timestamp="not-a-date"),
            actual_cost=999.0,
        )

        assert manager.get_total_spend(currency="EUR", days=30) == pytest.approx(0.0)

    def test_get_accuracy_stats_empty(self, isolated_history_file: Path) -> None:
        manager = CostHistoryManager()
        stats = manager.get_accuracy_stats()
        assert stats == {"average": 1.0, "min": 1.0, "max": 1.0, "count": 0}

        manager.add_entry(_estimate(tokens=100))
        still_empty = manager.get_accuracy_stats()
        assert still_empty["count"] == 0
        assert manager.get_entries()[0].accuracy_ratio is None

    def test_get_accuracy_stats_with_actual_tokens(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(tokens=100), actual_tokens=50)
        manager.add_entry(_estimate(tokens=100), actual_tokens=150)
        manager.add_entry(_estimate(tokens=100))

        stats = manager.get_accuracy_stats()
        assert stats["count"] == 2
        assert stats["average"] == pytest.approx(1.0)
        assert stats["min"] == pytest.approx(0.5)
        assert stats["max"] == pytest.approx(1.5)

    def test_clear_writes_empty_history(self, isolated_history_file: Path) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(tokens=10))
        manager.clear()

        assert manager.get_entries() == []
        payload = json.loads(isolated_history_file.read_text(encoding="utf-8"))
        assert payload["entries"] == []

    def test_add_entry_coerces_nan_actual_cost_to_none(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(cost=0.3), actual_cost=float("nan"))

        assert manager.get_entries()[-1].actual_cost is None

    def test_add_entry_coerces_inf_actual_cost_to_none(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(cost=0.3), actual_cost=float("inf"))
        assert manager.get_entries()[-1].actual_cost is None

        manager.add_entry(_estimate(cost=0.4), actual_cost=float("-inf"))
        assert manager.get_entries()[-1].actual_cost is None

    def test_add_entry_stores_finite_actual_cost(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(cost=0.3), actual_cost=0.5)

        assert manager.get_entries()[-1].actual_cost == pytest.approx(0.5)

    def test_add_entry_coerces_non_finite_estimated_cost_to_zero(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(cost=float("nan")))
        assert manager.get_entries()[-1].estimated_cost == 0.0
        assert math.isfinite(manager.get_entries()[-1].estimated_cost)

        manager.add_entry(_estimate(cost=float("inf")))
        assert manager.get_entries()[-1].estimated_cost == 0.0

        manager.add_entry(_estimate(cost=float("-inf")))
        assert manager.get_entries()[-1].estimated_cost == 0.0

    def test_add_entry_non_finite_costs_reload_without_raw_nan(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(
            _estimate(cost=float("nan"), timestamp="2099-01-01T12:00:00"),
            actual_cost=float("nan"),
        )
        manager.add_entry(
            _estimate(cost=float("inf"), timestamp="2099-01-01T13:00:00"),
            actual_cost=float("inf"),
        )

        raw = isolated_history_file.read_text(encoding="utf-8")
        assert "NaN" not in raw
        assert "Infinity" not in raw
        payload = json.loads(raw)
        assert all(entry["actual_cost"] is None for entry in payload["entries"])
        assert all(
            math.isfinite(entry["estimated_cost"]) for entry in payload["entries"]
        )

        reloaded = CostHistoryManager()
        entries = reloaded.get_entries()
        assert len(entries) == 2
        assert all(entry.actual_cost is None for entry in entries)
        assert all(entry.estimated_cost == 0.0 for entry in entries)

    def test_load_coerces_legacy_nan_json(self, isolated_history_file: Path) -> None:
        isolated_history_file.write_text(
            json.dumps(
                {"entries": [_entry_payload(
                    estimated_cost=float("nan"),
                    actual_cost=float("nan"),
                )]},
                allow_nan=True,
            ),
            encoding="utf-8",
        )

        manager = CostHistoryManager()
        entry = manager.get_entries()[0]
        assert entry.actual_cost is None
        assert entry.estimated_cost == 0.0
        assert math.isfinite(entry.estimated_cost)

    def test_add_entry_coerces_nan_actual_tokens_and_skips_accuracy(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(tokens=200), actual_tokens=float("nan"))

        entry = manager.get_entries()[-1]
        assert entry.actual_tokens is None
        assert entry.accuracy_ratio is None

    def test_add_entry_records_finite_accuracy_ratio(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(tokens=200), actual_tokens=180)

        entry = manager.get_entries()[-1]
        assert entry.actual_tokens == 180
        assert entry.accuracy_ratio == pytest.approx(0.9)

    def test_get_accuracy_stats_skips_non_finite_ratios(
        self, isolated_history_file: Path
    ) -> None:
        manager = CostHistoryManager()
        manager.add_entry(_estimate(tokens=100), actual_tokens=80)
        manager._history.append(
            CostHistoryEntry.from_dict(
                _entry_payload(estimated_tokens=10, actual_tokens=8)
            )
        )
        manager._history[-1].accuracy_ratio = float("nan")

        stats = manager.get_accuracy_stats()
        assert math.isfinite(stats["average"])
        assert stats["count"] == 1
        assert stats["average"] == pytest.approx(0.8)
        assert stats["min"] == pytest.approx(0.8)
        assert stats["max"] == pytest.approx(0.8)
