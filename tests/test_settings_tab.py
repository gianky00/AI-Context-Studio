# -*- coding: utf-8 -*-
"""
Tests for SettingsTab prompt-manager helpers that do not require a Tk window.
"""

from __future__ import annotations

from pathlib import Path

from ai_context_studio.custom_prompts import CustomPromptsManager
from ai_context_studio.models import GenerationType
from ai_context_studio.ui.settings_tab import (
    CUSTOMIZED_BADGE_LABEL,
    CUSTOMIZED_INDICATOR,
    EMPTY_PROMPT_STATUS,
    IDLE_EDITOR_TITLE,
    RESET_ALL_STATUS,
    SETTINGS_DOC_TYPES,
    SYSTEM_PROMPT_TITLE,
    UNCHANGED_PROMPT_STATUS,
    SettingsTab,
    char_count_label,
    customized_badge_text,
    customized_indicator_text,
    default_preview_title,
    doc_type_list_label,
    editor_title_text,
    is_editor_dirty,
    prompt_save_error,
    reset_status_message,
    save_status_message,
    should_show_customized_badge,
)


class TestSettingsDocTypes:
    """Tests for the prompt-manager GenerationType mapping."""

    def test_covers_every_generation_type(self) -> None:
        """The sidebar list should include every GenerationType member once."""
        assert SETTINGS_DOC_TYPES == tuple(GenerationType)
        assert len(SETTINGS_DOC_TYPES) == len(GenerationType)
        assert len(set(SETTINGS_DOC_TYPES)) == len(SETTINGS_DOC_TYPES)

    def test_sidebar_order_matches_class_attribute(self) -> None:
        """SettingsTab.DOC_TYPES should stay in sync with the module mapping."""
        assert SettingsTab.DOC_TYPES is SETTINGS_DOC_TYPES
        assert SETTINGS_DOC_TYPES[0] is GenerationType.ARCHITECTURE
        assert SETTINGS_DOC_TYPES[-1] is GenerationType.PERFORMANCE

    def test_labels_are_unique_and_non_empty(self) -> None:
        """doc_type_list_label must be unique and non-empty for every GenerationType."""
        labels = [doc_type_list_label(doc_type) for doc_type in GenerationType]
        assert len(labels) == len(GenerationType)
        assert all(isinstance(label, str) and label.strip() for label in labels)
        assert len(labels) == len(set(labels))

    def test_list_label_matches_generation_type(self) -> None:
        """Sidebar buttons should show the GenerationType label, not the filename."""
        assert doc_type_list_label(GenerationType.ARCHITECTURE) == "Architettura"
        assert doc_type_list_label(GenerationType.TESTING) == "Guida Testing"
        assert doc_type_list_label(GenerationType.ARCHITECTURE) != (
            GenerationType.ARCHITECTURE.filename
        )


class TestCustomizedMarkers:
    """Tests for sidebar indicator and PERSONALIZZATO badge text."""

    def test_customized_prompt_shows_star_and_badge(self) -> None:
        """A customized prompt should show '*' and the PERSONALIZZATO badge."""
        assert customized_indicator_text(True) == CUSTOMIZED_INDICATOR
        assert customized_badge_text(True) == CUSTOMIZED_BADGE_LABEL
        assert should_show_customized_badge(True) is True

    def test_stock_prompt_hides_markers(self) -> None:
        """A default prompt should show no indicator and no badge."""
        assert customized_indicator_text(False) == ""
        assert customized_badge_text(False) == ""
        assert should_show_customized_badge(False) is False

    def test_badge_text_empty_vs_customized(
        self, mock_config_dir: Path
    ) -> None:
        """Badge text is empty for stock prompts and PERSONALIZZATO when customized."""
        manager = CustomPromptsManager()
        assert customized_badge_text(
            manager.is_prompt_customized(GenerationType.RULES)
        ) == ""

        manager.set_prompt(GenerationType.RULES, "Regole custom")
        assert customized_badge_text(
            manager.is_prompt_customized(GenerationType.RULES)
        ) == CUSTOMIZED_BADGE_LABEL
        assert customized_badge_text(
            manager.is_prompt_customized(GenerationType.ARCHITECTURE)
        ) == ""

        manager.reset_prompt(GenerationType.RULES)
        assert customized_badge_text(
            manager.is_prompt_customized(GenerationType.RULES)
        ) == ""

    def test_markers_follow_custom_prompts_manager(
        self, mock_config_dir: Path
    ) -> None:
        """Badge and indicator should track CustomPromptsManager customization."""
        manager = CustomPromptsManager()
        assert customized_indicator_text(
            manager.is_prompt_customized(GenerationType.RULES)
        ) == ""
        assert should_show_customized_badge(
            manager.is_system_prompt_customized()
        ) is False

        manager.set_prompt(GenerationType.RULES, "Regole custom")
        manager.set_system_prompt("Sistema custom")

        assert customized_indicator_text(
            manager.is_prompt_customized(GenerationType.RULES)
        ) == CUSTOMIZED_INDICATOR
        assert customized_badge_text(
            manager.is_prompt_customized(GenerationType.ARCHITECTURE)
        ) == ""
        assert should_show_customized_badge(
            manager.is_system_prompt_customized()
        ) is True

        manager.reset_prompt(GenerationType.RULES)
        manager.reset_system_prompt()
        assert customized_indicator_text(
            manager.is_prompt_customized(GenerationType.RULES)
        ) == ""
        assert should_show_customized_badge(
            manager.is_system_prompt_customized()
        ) is False


class TestEditorDirtyState:
    """Tests for unsaved-change detection in the prompt editor."""

    def test_identical_text_is_not_dirty(self) -> None:
        """Matching editor and saved text should not be dirty."""
        prompt = "Genera la guida testing."
        assert is_editor_dirty(prompt, prompt) is False

    def test_edited_text_is_dirty(self) -> None:
        """Any difference from the saved prompt should mark the editor dirty."""
        assert is_editor_dirty("nuovo", "vecchio") is True

    def test_whitespace_difference_counts_as_dirty(self) -> None:
        """Trailing whitespace should count as an unsaved change."""
        assert is_editor_dirty("prompt\n", "prompt") is True
        assert is_editor_dirty("prompt ", "prompt") is True

    def test_dirty_against_manager_saved_prompt(
        self, mock_config_dir: Path
    ) -> None:
        """Dirty state should compare the editor buffer to the manager value."""
        manager = CustomPromptsManager()
        manager.set_prompt(GenerationType.CONTEXT, "Contesto salvato")
        saved = manager.get_prompt(GenerationType.CONTEXT)
        assert is_editor_dirty(saved, saved) is False
        assert is_editor_dirty("Contesto modificato", saved) is True


class TestEditorTitles:
    """Tests for editor header and default-preview dialog titles."""

    def test_idle_title_when_nothing_selected(self) -> None:
        """With no selection the editor should ask the user to pick a prompt."""
        assert editor_title_text() == IDLE_EDITOR_TITLE
        assert editor_title_text(None, editing_system=False) == IDLE_EDITOR_TITLE
        assert default_preview_title() is None

    def test_system_prompt_titles(self) -> None:
        """System-prompt editing should use the dedicated titles."""
        assert editor_title_text(editing_system=True) == SYSTEM_PROMPT_TITLE
        assert default_preview_title(editing_system=True) == (
            f"Default: {SYSTEM_PROMPT_TITLE}"
        )

    def test_document_prompt_titles_use_label(self) -> None:
        """Document editing should include the GenerationType label."""
        assert editor_title_text(GenerationType.TESTING) == "Prompt: Guida Testing"
        assert default_preview_title(GenerationType.TESTING) == (
            "Default: Guida Testing"
        )

    def test_system_flag_wins_over_doc_type(self) -> None:
        """editing_system should take precedence if both are set."""
        assert editor_title_text(
            GenerationType.API_DOCS, editing_system=True
        ) == SYSTEM_PROMPT_TITLE

    def test_generation_type_title_editing_system_true_vs_false(self) -> None:
        """Same GenerationType: document title when False, system title when True."""
        doc_type = GenerationType.DATABASE
        assert editor_title_text(doc_type, editing_system=False) == (
            f"Prompt: {doc_type.label}"
        )
        assert editor_title_text(doc_type, editing_system=True) == SYSTEM_PROMPT_TITLE


class TestCharCountLabel:
    """Tests for the editor character-count footer."""

    def test_empty_content_shows_zero(self) -> None:
        """An empty editor should report zero characters."""
        assert char_count_label("") == "0 caratteri"

    def test_counts_characters_with_thousands_separator(self) -> None:
        """The footer should use thousands separators for larger prompts."""
        assert char_count_label("abc") == "3 caratteri"
        assert char_count_label("x" * 1234) == "1,234 caratteri"


class TestStatusMessages:
    """Tests for save/reset status-bar copy used by the prompt manager."""

    def test_save_messages(self) -> None:
        """Save should name the system prompt or the document label."""
        assert save_status_message(editing_system=True) == (
            "Prompt di sistema salvato"
        )
        assert save_status_message(GenerationType.SECURITY) == (
            "Prompt Audit Sicurezza salvato"
        )
        assert save_status_message() == ""

    def test_reset_messages(self) -> None:
        """Reset should distinguish system, one document, and reset-all."""
        assert reset_status_message(editing_system=True) == (
            "Prompt di sistema ripristinato"
        )
        assert reset_status_message(GenerationType.ONBOARDING) == (
            "Prompt Onboarding Dev ripristinato"
        )
        assert reset_status_message(reset_all=True) == RESET_ALL_STATUS
        assert reset_status_message() == ""


class TestPromptSaveError:
    """Tests for save validation used before writing a customized prompt."""

    def test_empty_prompt_is_rejected(self) -> None:
        """Saving an empty editor should fail with a dedicated status."""
        assert prompt_save_error("") == EMPTY_PROMPT_STATUS
        assert prompt_save_error("   \n\t") == EMPTY_PROMPT_STATUS

    def test_c0_only_prompt_is_rejected(self) -> None:
        """NUL/ESC-only content is not whitespace but must not be saved."""
        assert prompt_save_error("\x00") == EMPTY_PROMPT_STATUS
        assert prompt_save_error("\x1b\x1b") == EMPTY_PROMPT_STATUS

    def test_whitespace_mixed_with_c0_is_empty(self) -> None:
        """Spaces plus C0 controls still have no printable prompt text."""
        assert prompt_save_error(" \x00 \x1b ") == EMPTY_PROMPT_STATUS
        assert prompt_save_error("\t\x00\n") == EMPTY_PROMPT_STATUS

    def test_printable_prompt_with_embedded_nul_is_ok(self) -> None:
        """A real prompt with a later NUL is not empty; C0 is emptiness-only."""
        assert prompt_save_error("hello\x00") is None
        assert prompt_save_error("hello\x00", "vecchio") is None

    def test_del_only_prompt_is_rejected(self) -> None:
        """DEL-only content is not C0 but must not be treated as saveable."""
        assert prompt_save_error("\x7f") == EMPTY_PROMPT_STATUS
        assert prompt_save_error(" \x7f ") == EMPTY_PROMPT_STATUS

    def test_printable_prompt_with_embedded_del_is_ok(self) -> None:
        """A real prompt with a later DEL is not empty; DEL is emptiness-only."""
        assert prompt_save_error("hello\x7f") is None

    def test_unchanged_prompt_is_rejected(self) -> None:
        """Saving without edits should fail so the file is not rewritten."""
        saved = "Genera la guida testing."
        assert prompt_save_error(saved, saved) == UNCHANGED_PROMPT_STATUS
        assert is_editor_dirty(saved, saved) is False

    def test_edited_non_empty_prompt_is_ok(self) -> None:
        """A non-empty dirty buffer should pass validation."""
        assert prompt_save_error("nuovo", "vecchio") is None

    def test_empty_wins_over_dirty_check(self) -> None:
        """Whitespace-only content is empty even when it differs from saved."""
        assert prompt_save_error("  ", "prompt salvato") == EMPTY_PROMPT_STATUS

    def test_dirty_against_manager_saved_prompt(
        self, mock_config_dir: Path
    ) -> None:
        """Validation should compare the editor buffer to the manager value."""
        manager = CustomPromptsManager()
        manager.set_prompt(GenerationType.CONTEXT, "Contesto salvato")
        saved = manager.get_prompt(GenerationType.CONTEXT)
        assert prompt_save_error(saved, saved) == UNCHANGED_PROMPT_STATUS
        assert prompt_save_error("", saved) == EMPTY_PROMPT_STATUS
        assert prompt_save_error("Contesto modificato", saved) is None
