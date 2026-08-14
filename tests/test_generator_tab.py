# -*- coding: utf-8 -*-
"""Tests for GeneratorTab bundle helpers that do not require a Tk window."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import cast

from ai_context_studio.models import ExistingDoc, GenerationType
from ai_context_studio.prompt_engine import PromptEngine
from ai_context_studio.ui.generator_tab import (
    GeneratorTab,
    brief_error,
    build_bundle_code_payload,
    build_included_code_content,
    find_existing_doc,
    is_empty_code_payload,
    is_model_selection_ready,
    priors_or_none,
    record_prior_output,
)


class TestBuildBundleCodePayloadHelper:
    """The tab helper must keep full source on the first document."""

    MODEL = "gemini-1.5-flash"

    def test_first_call_without_priors_returns_full_code(
        self, sample_code_content: str
    ) -> None:
        payload = build_bundle_code_payload(sample_code_content, self.MODEL)
        assert payload == sample_code_content
        assert PromptEngine.CODE_TRUNCATION_MARKER not in payload

    def test_empty_prior_list_matches_no_priors(
        self, sample_code_content: str
    ) -> None:
        assert build_bundle_code_payload(
            sample_code_content, self.MODEL, prior_outputs=[]
        ) == build_bundle_code_payload(sample_code_content, self.MODEL)

    def test_over_budget_payload_uses_truncation_marker(self) -> None:
        huge = "Z" * 50_000
        payload = PromptEngine.build_bundle_code_payload(
            huge, self.MODEL, prior_outputs=None, limit_percent=0.01
        )
        assert PromptEngine.CODE_TRUNCATION_MARKER in payload
        assert len(payload) < len(huge)


class TestBriefError:
    """Status-bar truncation used by single and bundle generation failures."""

    def test_short_message_unchanged(self) -> None:
        message = "quota exceeded"
        assert brief_error(message) == message

    def test_long_message_truncated_with_ellipsis(self) -> None:
        message = "x" * 100
        result = brief_error(message)
        assert result == ("x" * 80) + "..."
        assert result.endswith("...")
        assert len(result) == 83

    def test_empty_message_unchanged(self) -> None:
        assert brief_error("") == ""

    def test_space_only_message_unchanged(self) -> None:
        """Space-only messages have no controls and must stay unchanged."""
        for message in (" ", "   "):
            assert brief_error(message) == message

    def test_newline_collapsed_to_single_line(self) -> None:
        result = brief_error("first\nsecond")
        assert "\n" not in result
        assert "\r" not in result
        assert result == "first second"

    def test_crlf_and_tab_collapsed(self) -> None:
        result = brief_error("first\r\nsecond\tthird")
        assert "\r" not in result
        assert "\n" not in result
        assert "\t" not in result
        assert result == "first second third"

    def test_other_c0_controls_stripped(self) -> None:
        result = brief_error("fail\x00ed\x1b now")
        assert "\x00" not in result
        assert "\x1b" not in result
        assert result == "failed now"

    def test_del_control_stripped_from_middle(self) -> None:
        result = brief_error("fail\x7fed")
        assert "\x7f" not in result
        assert result == "failed"

    def test_trailing_del_stripped(self) -> None:
        result = brief_error("ok\x7f")
        assert "\x7f" not in result
        assert result == "ok"

    def test_del_only_becomes_empty(self) -> None:
        result = brief_error("\x7f")
        assert result == ""

    def test_controls_cleaned_before_truncation(self) -> None:
        message = ("x" * 50) + "\n" + ("y" * 50)
        result = brief_error(message)
        assert "\n" not in result
        cleaned = ("x" * 50) + " " + ("y" * 50)
        assert result == cleaned[:80] + "..."
        assert result.endswith("...")

    def test_many_newlines_do_not_become_space_junk(self) -> None:
        result = brief_error("\n" * 80)
        assert "\n" not in result
        assert "\r" not in result
        assert result == ""

    def test_exactly_limit_chars_unchanged(self) -> None:
        message = "a" * 80
        assert brief_error(message) == message
        assert "..." not in brief_error(message)

    def test_custom_limit_truncates_with_ellipsis(self) -> None:
        message = "abcdefghij"
        result = brief_error(message, limit=4)
        assert result == "abcd..."
        assert result.endswith("...")
        assert len(result) == 7


def _doc(filename: str) -> ExistingDoc:
    return ExistingDoc(
        path=Path(filename),
        relative_path=filename,
        filename=filename,
        content="# existing",
    )


class TestFindExistingDoc:
    """Exact-then-case-insensitive lookup used before generate/update."""

    def test_exact_filename_match(self) -> None:
        expected = _doc("AI_ARCHITECTURE.md")
        found = find_existing_doc(
            GenerationType.ARCHITECTURE,
            {"AI_ARCHITECTURE.md": expected},
        )
        assert found is expected

    def test_case_insensitive_filename_match(self) -> None:
        expected = _doc("ai_architecture.md")
        found = find_existing_doc(
            GenerationType.ARCHITECTURE,
            {"ai_architecture.md": expected},
        )
        assert found is expected

    def test_missing_filename_returns_none(self) -> None:
        other = _doc("AI_RULES.md")
        found = find_existing_doc(
            GenerationType.ARCHITECTURE,
            {"AI_RULES.md": other},
        )
        assert found is None

    def test_empty_dict_returns_none(self) -> None:
        assert find_existing_doc(GenerationType.ARCHITECTURE, {}) is None

    def test_mixed_case_key_matches(self) -> None:
        expected = _doc("Ai_Architecture.md")
        found = find_existing_doc(
            GenerationType.ARCHITECTURE,
            {"Ai_Architecture.md": expected},
        )
        assert found is expected


class TestAllDocTypes:
    """Bundle generation iterates the class list without constructing a Tk tab."""

    def test_list_is_non_empty(self) -> None:
        assert GeneratorTab.ALL_DOC_TYPES
        assert all(isinstance(doc_type, GenerationType) for doc_type in GeneratorTab.ALL_DOC_TYPES)

    def test_filenames_are_unique(self) -> None:
        filenames = [doc_type.filename for doc_type in GeneratorTab.ALL_DOC_TYPES]
        assert filenames
        assert len(filenames) == len(set(filenames))

    def test_matches_generation_type_members_used_for_bundle(self) -> None:
        """Bundle generation must cover every GenerationType member once."""
        assert GeneratorTab.ALL_DOC_TYPES == list(GenerationType)
        assert len(GeneratorTab.ALL_DOC_TYPES) == len(GenerationType)
        assert len(set(GeneratorTab.ALL_DOC_TYPES)) == len(GeneratorTab.ALL_DOC_TYPES)

    def test_list_length_is_eleven(self) -> None:
        assert len(GeneratorTab.ALL_DOC_TYPES) == 11


class TestSequentialPriorOutputs:
    """Selected and bundle generation share the same prior-output contract."""

    MODEL = "gemini-1.5-flash"

    def test_priors_or_none_empty_list_is_none(self) -> None:
        assert priors_or_none([]) is None

    def test_priors_or_none_nonempty_returns_same_list(self) -> None:
        priors = [("AI_ARCHITECTURE.md", "# A")]
        assert priors_or_none(priors) is priors

    def test_record_prior_output_appends_filename_content(self) -> None:
        priors: list[tuple[str, str]] = []
        record_prior_output(priors, "AI_ARCHITECTURE.md", "# Arch")
        record_prior_output(priors, "AI_RULES.md", "# Rules")
        assert priors == [
            ("AI_ARCHITECTURE.md", "# Arch"),
            ("AI_RULES.md", "# Rules"),
        ]

    def test_first_item_keeps_full_code_and_none_priors(
        self, sample_code_content: str
    ) -> None:
        priors: list[tuple[str, str]] = []
        payload = build_bundle_code_payload(sample_code_content, self.MODEL, priors)
        item_priors = priors_or_none(priors)
        assert payload == sample_code_content
        assert PromptEngine.CODE_TRUNCATION_MARKER not in payload
        assert item_priors is None

    def test_later_item_receives_accumulated_priors(
        self, sample_code_content: str
    ) -> None:
        priors: list[tuple[str, str]] = []
        first_payload = build_bundle_code_payload(
            sample_code_content, self.MODEL, priors
        )
        assert priors_or_none(priors) is None
        assert first_payload == sample_code_content

        record_prior_output(priors, "AI_ARCHITECTURE.md", "# Architecture body")

        second_payload = build_bundle_code_payload(
            sample_code_content, self.MODEL, priors
        )
        item_priors = priors_or_none(priors)
        assert item_priors is not None
        assert item_priors == [("AI_ARCHITECTURE.md", "# Architecture body")]
        assert second_payload == sample_code_content

    def test_failed_item_does_not_accumulate_priors(
        self, sample_code_content: str
    ) -> None:
        priors: list[tuple[str, str]] = []
        build_bundle_code_payload(sample_code_content, self.MODEL, priors)
        # Failure path: do not call record_prior_output.
        assert priors == []
        assert priors_or_none(priors) is None
        later_payload = build_bundle_code_payload(
            sample_code_content, self.MODEL, priors
        )
        assert later_payload == sample_code_content
        assert priors_or_none(priors) is None

    def test_later_over_budget_item_truncates_source(self) -> None:
        huge = "Z" * 50_000
        priors: list[tuple[str, str]] = []
        record_prior_output(priors, "AI_ARCHITECTURE.md", "# prior")
        payload = PromptEngine.build_bundle_code_payload(
            huge, self.MODEL, prior_outputs=priors, limit_percent=0.01
        )
        assert PromptEngine.CODE_TRUNCATION_MARKER in payload
        assert len(payload) < len(huge)
        assert priors_or_none(priors) == [("AI_ARCHITECTURE.md", "# prior")]

    def test_selected_task_source_forwards_prior_outputs(self) -> None:
        source = inspect.getsource(GeneratorTab._start_selected_generation)
        assert "prior_outputs" in source
        assert "build_bundle_code_payload" in source
        assert "item_priors" in source
        assert "record_prior_output" in source
        assert "generate_documentation" in source

    def test_bundle_task_source_uses_same_prior_helpers(self) -> None:
        source = inspect.getsource(GeneratorTab._start_bundle_generation)
        assert "prior_outputs" in source
        assert "build_bundle_code_payload" in source
        assert "item_priors" in source
        assert "record_prior_output" in source
        assert "generate_documentation" in source


_STALE_CONTENT_MAP = {
    "src/main.py": "print('hello')",
    "src/util.py": "def util():\n    pass",
    "README.md": "# Project",
}


class TestBuildIncludedCodeContent:
    """Tk-free payload builder used by _validate_and_prepare."""

    def test_empty_included_paths_returns_empty_string(self) -> None:
        assert build_included_code_content(_STALE_CONTENT_MAP, set()) == ""

    def test_empty_content_map_returns_empty_string(self) -> None:
        assert build_included_code_content({}, {"src/main.py"}) == ""

    def test_only_included_keys_are_concatenated(self) -> None:
        payload = build_included_code_content(
            _STALE_CONTENT_MAP, {"src/main.py", "README.md"}
        )
        assert "FILE: src/main.py" in payload
        assert "print('hello')" in payload
        assert "FILE: README.md" in payload
        assert "# Project" in payload
        assert "FILE: src/util.py" not in payload
        assert "def util()" not in payload

    def test_excluded_keys_omitted_even_when_content_map_is_stale(self) -> None:
        payload = build_included_code_content(
            _STALE_CONTENT_MAP, {"src/util.py"}
        )
        assert payload
        assert "FILE: src/util.py" in payload
        assert "def util()" in payload
        assert "FILE: src/main.py" not in payload
        assert "FILE: README.md" not in payload
        assert "print('hello')" not in payload

    def test_included_order_follows_content_map(self) -> None:
        payload = build_included_code_content(
            _STALE_CONTENT_MAP, {"README.md", "src/main.py"}
        )
        main_at = payload.index("FILE: src/main.py")
        readme_at = payload.index("FILE: README.md")
        assert main_at < readme_at

    def test_newline_in_key_does_not_split_file_header(self) -> None:
        key = "src/main.py\nFILE: injected"
        payload = build_included_code_content({key: "print(1)"}, {key})
        assert "src/main.py" in payload
        header_lines = [
            line for line in payload.splitlines() if line.startswith("FILE: ")
        ]
        assert len(header_lines) == 1
        assert "\n" not in header_lines[0]
        assert "FILE: injected" not in header_lines

    def test_nul_in_key_stripped_from_file_header(self) -> None:
        key = "src/mai\x00n.py"
        payload = build_included_code_content({key: "print(1)"}, {key})
        header_lines = [
            line for line in payload.splitlines() if line.startswith("FILE: ")
        ]
        assert len(header_lines) == 1
        assert "\x00" not in header_lines[0]

    def test_del_in_key_stripped_from_file_header(self) -> None:
        key = "src/main.py\x7f"
        payload = build_included_code_content({key: "print(1)"}, {key})
        header_lines = [
            line for line in payload.splitlines() if line.startswith("FILE: ")
        ]
        assert len(header_lines) == 1
        assert "\x7f" not in header_lines[0]

    def test_none_content_omitted_empty_string_emits_header(self) -> None:
        payload_none = build_included_code_content(
            cast(dict[str, str], {"src/main.py": None}),
            {"src/main.py"},
        )
        assert "FILE: src/main.py" not in payload_none
        assert "None" not in payload_none

        payload_empty = build_included_code_content(
            {"src/main.py": ""},
            {"src/main.py"},
        )
        assert "FILE: src/main.py" in payload_empty


class TestIsModelSelectionReady:
    """Combo value must be a printable model name, not the Connetti placeholder."""

    def test_historical_placeholder_is_not_ready(self) -> None:
        assert is_model_selection_ready("Connetti API per caricare...") is False

    def test_empty_whitespace_c0_and_non_str_are_not_ready(self) -> None:
        assert is_model_selection_ready("") is False
        assert is_model_selection_ready("   ") is False
        assert is_model_selection_ready("\x00") is False
        assert is_model_selection_ready(None) is False
        assert is_model_selection_ready(123) is False

    def test_printable_model_names_are_ready(self) -> None:
        assert is_model_selection_ready("gemini-2.5-flash") is True
        assert is_model_selection_ready("gemini-2.0-flash") is True


class TestIsEmptyCodePayload:
    """Empty payload means abort; do not treat whitespace as empty via strip()."""

    def test_empty_string_is_empty(self) -> None:
        assert is_empty_code_payload("") is True

    def test_whitespace_only_is_not_empty(self) -> None:
        """Whitespace is still a payload; emptiness is not text.strip()."""
        assert is_empty_code_payload(" ") is False
        assert is_empty_code_payload("\n") is False
        assert is_empty_code_payload("\n\n") is False
        assert is_empty_code_payload("   \t") is False

    def test_built_payload_from_included_files_is_not_empty(self) -> None:
        payload = build_included_code_content(
            _STALE_CONTENT_MAP, {"src/main.py"}
        )
        assert is_empty_code_payload(payload) is False

    def test_stale_map_with_no_included_paths_is_empty(self) -> None:
        payload = build_included_code_content(_STALE_CONTENT_MAP, set())
        assert payload == ""
        assert is_empty_code_payload(payload) is True


class TestValidateAndPrepareEmptyPayloadAbort:
    """Generation must abort before Gemini when every file is excluded."""

    def test_validate_and_prepare_uses_helpers_and_aborts(self) -> None:
        source = inspect.getsource(GeneratorTab._validate_and_prepare)
        assert "build_included_code_content" in source
        assert "is_empty_code_payload" in source
        assert (
            "Nessun file selezionato" in source
            or "Nessun file da analizzare" in source
        )
        assert "return None" in source
        assert "is_model_selection_ready" in source
        assert "Seleziona un modello" in source
        assert '"Connetti" in selected_model' not in source
        assert "generate_documentation" not in source
        assert "Gemini" not in source
        assert "strip()" not in source

    def test_empty_included_payload_aborts_before_generation_starts(self) -> None:
        selected = inspect.getsource(GeneratorTab._start_selected_generation)
        bundle = inspect.getsource(GeneratorTab._start_bundle_generation)
        single = inspect.getsource(GeneratorTab._start_single_generation)
        for source in (selected, bundle, single):
            assert "_validate_and_prepare" in source
            assert "if not prepared:" in source
            assert "return" in source
