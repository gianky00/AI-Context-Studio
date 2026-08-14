# -*- coding: utf-8 -*-
"""Tests for CustomPromptsManager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_context_studio import custom_prompts as custom_prompts_mod
from ai_context_studio.custom_prompts import (
    CustomPromptsManager,
    get_custom_prompts_manager,
    reset_custom_prompts_manager,
)
from ai_context_studio.models import GenerationType
from ai_context_studio.prompt_engine import PromptEngine


class TestCustomPromptsManager:
    """Tests for custom prompt overrides."""

    def test_default_system_prompt(self, mock_config_dir: Path) -> None:
        manager = CustomPromptsManager()
        assert manager.get_system_prompt() == PromptEngine.BASE_SYSTEM_PROMPT
        assert manager.is_system_prompt_customized() is False

    def test_custom_system_prompt_persists(self, mock_config_dir: Path) -> None:
        manager = CustomPromptsManager()
        manager.set_system_prompt("Custom system")
        assert manager.get_system_prompt() == "Custom system"
        assert (mock_config_dir / "custom_prompts.json").exists()

        reset_custom_prompts_manager()
        reloaded = CustomPromptsManager()
        assert reloaded.get_system_prompt() == "Custom system"
        assert reloaded.is_system_prompt_customized() is True

    def test_empty_system_prompt_resets(self, mock_config_dir: Path) -> None:
        manager = CustomPromptsManager()
        manager.set_system_prompt("Custom")
        manager.set_system_prompt("   ")
        assert manager.get_system_prompt() == PromptEngine.BASE_SYSTEM_PROMPT

    def test_custom_doc_prompt(self, mock_config_dir: Path) -> None:
        manager = CustomPromptsManager()
        manager.set_prompt(GenerationType.RULES, "Scrivi regole minime")
        assert manager.get_prompt(GenerationType.RULES) == "Scrivi regole minime"
        assert manager.is_prompt_customized(GenerationType.RULES) is True
        assert manager.is_prompt_customized(GenerationType.ARCHITECTURE) is False

    def test_reset_prompt(self, mock_config_dir: Path) -> None:
        manager = CustomPromptsManager()
        manager.set_prompt(GenerationType.TESTING, "Custom testing")
        manager.reset_prompt(GenerationType.TESTING)
        assert manager.is_prompt_customized(GenerationType.TESTING) is False
        default = manager.get_default_prompt(GenerationType.TESTING)
        assert manager.get_prompt(GenerationType.TESTING) == default
        assert len(default) > 0

    def test_reset_all(self, mock_config_dir: Path) -> None:
        manager = CustomPromptsManager()
        manager.set_system_prompt("Sys")
        manager.set_prompt(GenerationType.CONTEXT, "Ctx")
        manager.reset_all()
        assert manager.is_system_prompt_customized() is False
        assert manager.is_prompt_customized(GenerationType.CONTEXT) is False

    def test_global_manager_singleton(self, mock_config_dir: Path) -> None:
        reset_custom_prompts_manager()
        first = get_custom_prompts_manager()
        second = get_custom_prompts_manager()
        assert first is second

    def test_empty_prompt_clears_customization(self, mock_config_dir: Path) -> None:
        manager = CustomPromptsManager()
        manager.set_prompt(GenerationType.RULES, "Custom rules")
        manager.set_prompt(GenerationType.RULES, "   ")
        assert manager.is_prompt_customized(GenerationType.RULES) is False
        assert manager.get_prompt(GenerationType.RULES) == manager.get_default_prompt(
            GenerationType.RULES
        )

        payload = json.loads(
            (mock_config_dir / "custom_prompts.json").read_text(encoding="utf-8")
        )
        assert "RULES" not in payload["prompts"]

    def test_duplicate_type_overwrites_previous_prompt(self, mock_config_dir: Path) -> None:
        manager = CustomPromptsManager()
        manager.set_prompt(GenerationType.RULES, "First")
        manager.set_prompt(GenerationType.RULES, "Second")
        assert manager.get_prompt(GenerationType.RULES) == "Second"

        payload = json.loads(
            (mock_config_dir / "custom_prompts.json").read_text(encoding="utf-8")
        )
        assert payload["prompts"] == {"RULES": "Second"}

        reset_custom_prompts_manager()
        reloaded = CustomPromptsManager()
        assert reloaded.get_prompt(GenerationType.RULES) == "Second"

    def test_reset_isolates_singleton_to_mock_config_dir(
        self, mock_config_dir: Path
    ) -> None:
        stale = get_custom_prompts_manager()
        stale.set_prompt(GenerationType.CONTEXT, "Stale in-memory")
        stale.set_system_prompt("Stale system")

        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps({"prompts": {}, "system_prompt": None}),
            encoding="utf-8",
        )

        assert get_custom_prompts_manager() is stale
        assert stale.get_system_prompt() == "Stale system"

        reset_custom_prompts_manager()
        fresh = get_custom_prompts_manager()
        assert fresh is not stale
        assert fresh.is_system_prompt_customized() is False
        assert fresh.is_prompt_customized(GenerationType.CONTEXT) is False
        assert (mock_config_dir / "custom_prompts.json").exists()

    def test_corrupt_json_falls_back_to_defaults(self, mock_config_dir: Path) -> None:
        (mock_config_dir / "custom_prompts.json").write_text("{not json", encoding="utf-8")
        manager = CustomPromptsManager()
        assert manager.get_system_prompt() == PromptEngine.BASE_SYSTEM_PROMPT
        assert manager.get_prompt(GenerationType.RULES) == manager.get_default_prompt(
            GenerationType.RULES
        )
        assert manager.is_system_prompt_customized() is False

    def test_non_object_json_falls_back_to_defaults(self, mock_config_dir: Path) -> None:
        (mock_config_dir / "custom_prompts.json").write_text("[]", encoding="utf-8")
        manager = CustomPromptsManager()
        assert manager.get_system_prompt() == PromptEngine.BASE_SYSTEM_PROMPT
        assert manager.is_prompt_customized(GenerationType.TESTING) is False

    def test_prompts_list_falls_back_then_save_writes_dict(
        self, mock_config_dir: Path
    ) -> None:
        prompts_file = mock_config_dir / "custom_prompts.json"
        prompts_file.write_text(
            json.dumps({"prompts": [], "system_prompt": None}),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        assert manager.get_system_prompt() == PromptEngine.BASE_SYSTEM_PROMPT
        assert manager.is_prompt_customized(GenerationType.RULES) is False
        assert manager.is_system_prompt_customized() is False

        manager.set_prompt(GenerationType.RULES, "Recovered rules")
        payload = json.loads(prompts_file.read_text(encoding="utf-8"))
        assert payload["prompts"] == {"RULES": "Recovered rules"}
        assert isinstance(payload["prompts"], dict)

    def test_prompts_string_falls_back_keeps_system_prompt(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps({"prompts": "not-a-dict", "system_prompt": "Custom"}),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        assert manager.is_prompt_customized(GenerationType.RULES) is False
        assert manager.get_prompt(GenerationType.RULES) == manager.get_default_prompt(
            GenerationType.RULES
        )
        assert manager.get_system_prompt() == "Custom"
        assert manager.is_system_prompt_customized() is True

        manager.set_prompt(GenerationType.TESTING, "Recovered testing")
        payload = json.loads(
            (mock_config_dir / "custom_prompts.json").read_text(encoding="utf-8")
        )
        assert payload["prompts"] == {"TESTING": "Recovered testing"}
        assert payload["system_prompt"] == "Custom"

    def test_non_str_system_prompt_treated_as_none(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps({"prompts": {}, "system_prompt": 123}),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        assert manager.is_system_prompt_customized() is False
        assert manager.get_system_prompt() == PromptEngine.BASE_SYSTEM_PROMPT

    def test_whitespace_system_prompt_on_disk_treated_as_default(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps({"prompts": {}, "system_prompt": "   "}),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        assert manager.is_system_prompt_customized() is False
        assert manager.get_system_prompt() == PromptEngine.BASE_SYSTEM_PROMPT

    def test_real_custom_system_prompt_on_disk_still_customized(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps({"prompts": {}, "system_prompt": "Real custom"}),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        assert manager.is_system_prompt_customized() is True
        assert manager.get_system_prompt() == "Real custom"

    def test_c0_only_system_prompt_set_treated_as_default(
        self, mock_config_dir: Path
    ) -> None:
        manager = CustomPromptsManager()
        manager.set_system_prompt("\x00")
        assert manager.is_system_prompt_customized() is False
        assert manager.get_system_prompt() == PromptEngine.BASE_SYSTEM_PROMPT

        payload = json.loads(
            (mock_config_dir / "custom_prompts.json").read_text(encoding="utf-8")
        )
        assert payload["system_prompt"] is None

    def test_system_prompt_with_embedded_c0_stores_printable_text(
        self, mock_config_dir: Path
    ) -> None:
        manager = CustomPromptsManager()
        manager.set_system_prompt("hello\x00")
        assert manager.is_system_prompt_customized() is True
        assert manager.get_system_prompt() == "hello"

        payload = json.loads(
            (mock_config_dir / "custom_prompts.json").read_text(encoding="utf-8")
        )
        assert payload["system_prompt"] == "hello"
        assert "\x00" not in payload["system_prompt"]

    def test_c0_only_system_prompt_on_disk_treated_as_default(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps({"prompts": {}, "system_prompt": "\x00"}),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        assert manager.is_system_prompt_customized() is False
        assert manager.get_system_prompt() == PromptEngine.BASE_SYSTEM_PROMPT

    def test_c0_only_set_prompt_falls_back_to_default(
        self, mock_config_dir: Path
    ) -> None:
        manager = CustomPromptsManager()
        manager.set_prompt(GenerationType.RULES, "Custom rules")
        manager.set_prompt(GenerationType.RULES, "\x00")
        assert manager.is_prompt_customized(GenerationType.RULES) is False
        assert manager.get_prompt(GenerationType.RULES) == manager.get_default_prompt(
            GenerationType.RULES
        )

        payload = json.loads(
            (mock_config_dir / "custom_prompts.json").read_text(encoding="utf-8")
        )
        assert "RULES" not in payload["prompts"]

    def test_prompt_with_embedded_c0_stores_printable_text(
        self, mock_config_dir: Path
    ) -> None:
        manager = CustomPromptsManager()
        manager.set_prompt(GenerationType.RULES, "hello\x00")
        assert manager.is_prompt_customized(GenerationType.RULES) is True
        assert manager.get_prompt(GenerationType.RULES) == "hello"

        payload = json.loads(
            (mock_config_dir / "custom_prompts.json").read_text(encoding="utf-8")
        )
        assert payload["prompts"]["RULES"] == "hello"
        assert "\x00" not in payload["prompts"]["RULES"]

    def test_c0_only_prompt_on_disk_treated_as_missing(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps(
                {"prompts": {"RULES": "\x00"}, "system_prompt": None}
            ),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        assert manager.is_prompt_customized(GenerationType.RULES) is False
        assert manager.get_prompt(GenerationType.RULES) == manager.get_default_prompt(
            GenerationType.RULES
        )

    def test_non_str_prompt_values_ignored_keeps_valid_strings(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps(
                {"prompts": {"RULES": 123, "TESTING": "ok"}, "system_prompt": None}
            ),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        default_rules = manager.get_default_prompt(GenerationType.RULES)
        assert manager.is_prompt_customized(GenerationType.RULES) is False
        assert manager.get_prompt(GenerationType.RULES) == default_rules
        assert manager.get_prompt(GenerationType.RULES) != 123
        assert manager.is_prompt_customized(GenerationType.TESTING) is True
        assert manager.get_prompt(GenerationType.TESTING) == "ok"

    def test_nested_dict_and_list_prompt_values_ignored(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps(
                {
                    "prompts": {
                        "RULES": {"nested": "dict"},
                        "TESTING": ["list"],
                        "ARCHITECTURE": "ok",
                    },
                    "system_prompt": None,
                }
            ),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        assert manager.is_prompt_customized(GenerationType.RULES) is False
        assert manager.get_prompt(GenerationType.RULES) == manager.get_default_prompt(
            GenerationType.RULES
        )
        assert manager.is_prompt_customized(GenerationType.TESTING) is False
        assert manager.get_prompt(GenerationType.TESTING) == manager.get_default_prompt(
            GenerationType.TESTING
        )
        assert manager.is_prompt_customized(GenerationType.ARCHITECTURE) is True
        assert manager.get_prompt(GenerationType.ARCHITECTURE) == "ok"

    def test_empty_string_prompt_value_treated_as_missing(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps(
                {"prompts": {"RULES": "", "TESTING": "   "}, "system_prompt": None}
            ),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        assert manager.is_prompt_customized(GenerationType.RULES) is False
        assert manager.get_prompt(GenerationType.RULES) == manager.get_default_prompt(
            GenerationType.RULES
        )
        assert manager.is_prompt_customized(GenerationType.TESTING) is False
        assert manager.get_prompt(GenerationType.TESTING) == manager.get_default_prompt(
            GenerationType.TESTING
        )

    def test_get_prompt_falls_back_if_in_memory_value_is_not_str(
        self, mock_config_dir: Path
    ) -> None:
        manager = CustomPromptsManager()
        manager._custom_prompts["RULES"] = 123  # type: ignore[assignment]
        default_rules = manager.get_default_prompt(GenerationType.RULES)
        result = manager.get_prompt(GenerationType.RULES)
        assert isinstance(result, str)
        assert result == default_rules
        assert result != 123

    def test_get_prompt_uses_default_for_missing_type(
        self, mock_config_dir: Path
    ) -> None:
        manager = CustomPromptsManager()
        default = manager.get_default_prompt(GenerationType.ARCHITECTURE)
        assert len(default) > 0
        assert manager.get_prompt(GenerationType.ARCHITECTURE) == default
        assert manager.is_prompt_customized(GenerationType.ARCHITECTURE) is False

    def test_unknown_json_key_does_not_override_known_type(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps(
                {
                    "prompts": {"NOT_A_TYPE": "ignored", "RULES": "Custom rules"},
                    "system_prompt": None,
                }
            ),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        assert manager.get_prompt(GenerationType.RULES) == "Custom rules"
        assert manager.get_prompt(GenerationType.ARCHITECTURE) == (
            manager.get_default_prompt(GenerationType.ARCHITECTURE)
        )

    def test_c0_in_prompt_key_is_skipped_not_cleaned(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps(
                {
                    "prompts": {
                        "ARCHITECTURE\x00": "Hijack arch",
                        "RULES": "Custom rules",
                    },
                    "system_prompt": None,
                }
            ),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        default_arch = manager.get_default_prompt(GenerationType.ARCHITECTURE)
        assert manager.get_prompt(GenerationType.ARCHITECTURE) == default_arch
        assert manager.get_prompt(GenerationType.ARCHITECTURE) != "Hijack arch"
        assert manager.get_prompt(GenerationType.RULES) == "Custom rules"
        assert "ARCHITECTURE\x00" not in manager._custom_prompts
        assert manager.is_prompt_customized(GenerationType.ARCHITECTURE) is False

    def test_del_in_prompt_key_is_skipped_clean_key_still_loads(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "custom_prompts.json").write_text(
            json.dumps(
                {
                    "prompts": {
                        "RULES\x7f": "Hijack rules",
                        "TESTING": "Custom testing",
                    },
                    "system_prompt": None,
                }
            ),
            encoding="utf-8",
        )
        manager = CustomPromptsManager()
        assert manager.get_prompt(GenerationType.RULES) == manager.get_default_prompt(
            GenerationType.RULES
        )
        assert "RULES\x7f" not in manager._custom_prompts
        assert manager.get_prompt(GenerationType.TESTING) == "Custom testing"

    def test_get_prompt_missing_from_engine_returns_empty(
        self, mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            PromptEngine,
            "GENERATION_PROMPTS",
            {GenerationType.RULES: "only rules"},
        )
        manager = CustomPromptsManager()
        assert manager.get_prompt(GenerationType.ARCHITECTURE) == ""
        assert manager.get_default_prompt(GenerationType.ARCHITECTURE) == ""
        assert manager.get_prompt(GenerationType.RULES) == "only rules"

    def test_save_roundtrip_persists_prompt_and_system(
        self, mock_config_dir: Path
    ) -> None:
        manager = CustomPromptsManager()
        manager.set_prompt(GenerationType.TESTING, "Test prompt")
        manager.set_system_prompt("Sys prompt")

        prompts_file = mock_config_dir / "custom_prompts.json"
        payload = json.loads(prompts_file.read_text(encoding="utf-8"))
        assert payload["prompts"]["TESTING"] == "Test prompt"
        assert payload["system_prompt"] == "Sys prompt"

        reset_custom_prompts_manager()
        reloaded = CustomPromptsManager()
        assert reloaded.get_prompt(GenerationType.TESTING) == "Test prompt"
        assert reloaded.get_system_prompt() == "Sys prompt"
        assert reloaded.get_default_system_prompt() == PromptEngine.BASE_SYSTEM_PROMPT
        assert reloaded.is_prompt_customized(GenerationType.TESTING) is True

    def test_reset_system_prompt(self, mock_config_dir: Path) -> None:
        manager = CustomPromptsManager()
        manager.set_system_prompt("Custom")
        manager.reset_system_prompt()
        assert manager.is_system_prompt_customized() is False
        assert manager.get_system_prompt() == PromptEngine.BASE_SYSTEM_PROMPT

        reset_custom_prompts_manager()
        reloaded = CustomPromptsManager()
        assert reloaded.is_system_prompt_customized() is False

    def test_get_prompt_covers_all_generation_types(
        self, mock_config_dir: Path
    ) -> None:
        manager = CustomPromptsManager()
        types = list(GenerationType)
        assert len(types) > 1
        for gen_type in types:
            default = manager.get_default_prompt(gen_type)
            assert len(default) > 0
            assert manager.get_prompt(gen_type) == default
            assert manager.is_prompt_customized(gen_type) is False

        manager.set_prompt(types[0], "Custom all-types")
        assert manager.is_prompt_customized(types[0]) is True
        assert manager.get_prompt(types[0]) == "Custom all-types"
        for gen_type in types[1:]:
            assert manager.is_prompt_customized(gen_type) is False
            assert manager.get_prompt(gen_type) == manager.get_default_prompt(gen_type)

    def test_save_restricts_custom_prompts_file(
        self, mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded: list[Path] = []

        def record_restrict(path: Path) -> None:
            recorded.append(Path(path))

        monkeypatch.setattr(custom_prompts_mod, "restrict_file_permissions", record_restrict)

        manager = CustomPromptsManager()
        manager.set_prompt(GenerationType.RULES, "Custom")

        expected = mock_config_dir / "custom_prompts.json"
        assert recorded == [expected]
        assert expected.exists()

    def test_save_oserror_does_not_restrict(
        self, mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded: list[Path] = []

        def record_restrict(path: Path) -> None:
            recorded.append(Path(path))

        monkeypatch.setattr(custom_prompts_mod, "restrict_file_permissions", record_restrict)

        original_write = Path.write_text

        def fail_write(self: Path, *args: object, **kwargs: object) -> int:
            if self == custom_prompts_mod.CUSTOM_PROMPTS_FILE:
                raise OSError("disk full")
            return original_write(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_write)

        manager = CustomPromptsManager()
        manager.set_prompt(GenerationType.RULES, "Custom")

        assert recorded == []
