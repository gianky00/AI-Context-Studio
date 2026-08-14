# -*- coding: utf-8 -*-
"""
Tests for SmartPresetPanel / GuidePanel helpers that do not require a Tk window.
"""

from __future__ import annotations

from ai_context_studio.constants import COLORS
from ai_context_studio.models import FocusArea, ProjectType, SmartPreset
from ai_context_studio.ui.panels import (
    GUIDE_STEPS,
    GUIDE_TIPS,
    NOTES_PLACEHOLDER,
    PREVIEW_NOTES_MAX_LENGTH,
    build_smart_preset,
    focus_areas_from_labels,
    format_preset_preview,
    is_notes_placeholder,
    project_type_from_name,
    sanitize_additional_notes,
    selected_focus_areas,
)


class FakeBooleanVar:
    """Minimal stand-in for tk.BooleanVar used by focus-area checkboxes."""

    def __init__(self, value: bool) -> None:
        self._value = value

    def get(self) -> bool:
        return self._value


class TestProjectTypeFromName:
    """Tests for resolving ProjectType from a radio-button name string."""

    def test_known_name_returns_matching_member(self) -> None:
        """A valid enum name should resolve to that ProjectType."""
        assert project_type_from_name("WEB_FRONTEND") is ProjectType.WEB_FRONTEND
        assert project_type_from_name("DEVOPS") is ProjectType.DEVOPS
        assert project_type_from_name("GENERIC") is ProjectType.GENERIC

    def test_unknown_name_falls_back_to_generic(self) -> None:
        """An unknown or empty name should fall back to GENERIC."""
        assert project_type_from_name("NOT_A_TYPE") is ProjectType.GENERIC
        assert project_type_from_name("") is ProjectType.GENERIC
        assert project_type_from_name("web_frontend") is ProjectType.GENERIC


class TestFocusAreasFromLabels:
    """Tests for mapping checkbox display labels to FocusArea members."""

    def test_known_labels_preserve_order(self) -> None:
        """Known labels should map to FocusArea members in input order."""
        areas = focus_areas_from_labels(["Sicurezza", "Performance"])
        assert areas == [FocusArea.SECURITY, FocusArea.PERFORMANCE]

    def test_unknown_labels_are_skipped(self) -> None:
        """Labels that are not FocusArea display names should be ignored."""
        areas = focus_areas_from_labels(["Sicurezza", "Unknown", "Testing"])
        assert areas == [FocusArea.SECURITY, FocusArea.TESTING]

    def test_empty_labels_returns_empty_list(self) -> None:
        """No labels should produce an empty focus list."""
        assert focus_areas_from_labels([]) == []


class TestSelectedFocusAreas:
    """Tests for collecting selected focus areas from Fake checkbox vars."""

    def test_collects_only_selected_fake_vars(self) -> None:
        """Only areas whose FakeBooleanVar.get() is True should be returned."""
        selections = {
            FocusArea.SECURITY: FakeBooleanVar(True),
            FocusArea.PERFORMANCE: FakeBooleanVar(False),
            FocusArea.TESTING: FakeBooleanVar(True),
        }
        assert selected_focus_areas(selections) == [
            FocusArea.SECURITY,
            FocusArea.TESTING,
        ]

    def test_plain_bools_are_accepted(self) -> None:
        """A mapping of plain bools should work without Tk vars."""
        selections = {
            FocusArea.MAINTAINABILITY: True,
            FocusArea.DOCUMENTATION: False,
            FocusArea.ACCESSIBILITY: True,
        }
        assert selected_focus_areas(selections) == [
            FocusArea.MAINTAINABILITY,
            FocusArea.ACCESSIBILITY,
        ]

    def test_none_selected_returns_empty(self) -> None:
        """All-false selections should yield no focus areas."""
        selections = {
            FocusArea.SECURITY: FakeBooleanVar(False),
            FocusArea.PERFORMANCE: False,
        }
        assert selected_focus_areas(selections) == []


class TestNotesPlaceholder:
    """Tests for placeholder detection and sanitization of additional notes."""

    def test_placeholder_constant_is_detected(self) -> None:
        """The panel placeholder string should be treated as empty notes."""
        assert is_notes_placeholder(NOTES_PLACEHOLDER)
        assert sanitize_additional_notes(NOTES_PLACEHOLDER) == ""

    def test_es_prefix_is_treated_as_placeholder(self) -> None:
        """Text starting with 'Es:' should be dropped, matching panel behavior."""
        assert is_notes_placeholder("Es: esempio")
        assert sanitize_additional_notes("Es: esempio") == ""

    def test_real_notes_are_stripped_but_kept(self) -> None:
        """User notes should be returned stripped, not discarded."""
        assert not is_notes_placeholder("Documenta le API REST")
        assert sanitize_additional_notes("  Documenta le API REST  ") == (
            "Documenta le API REST"
        )

    def test_whitespace_only_becomes_empty(self) -> None:
        """Whitespace-only notes should sanitize to an empty string."""
        assert sanitize_additional_notes("   \n  ") == ""

    def test_control_chars_stripped_placeholder_cannot_inject(self) -> None:
        """C0 controls are removed; they must not hide a placeholder prefix."""
        assert sanitize_additional_notes("Documenta\x00 le API\x07") == (
            "Documenta le API"
        )
        assert sanitize_additional_notes("\x00Es: esempio") == ""
        assert sanitize_additional_notes("\x1b" + NOTES_PLACEHOLDER) == ""


class TestBuildSmartPreset:
    """Tests for assembling SmartPreset from widget-collected strings."""

    def test_builds_preset_from_name_and_labels(self) -> None:
        """Project type name and focus labels should populate the preset."""
        preset = build_smart_preset(
            "WEB_BACKEND",
            ["Sicurezza", "Performance"],
            "Sviluppatori Senior / Architect",
            "Documenta le query SQLAlchemy",
        )
        assert isinstance(preset, SmartPreset)
        assert preset.project_type is ProjectType.WEB_BACKEND
        assert preset.focus_areas == [FocusArea.SECURITY, FocusArea.PERFORMANCE]
        assert preset.target_audience == "Sviluppatori Senior / Architect"
        assert preset.additional_notes == "Documenta le query SQLAlchemy"

    def test_invalid_type_and_placeholder_notes_use_defaults(self) -> None:
        """Unknown type and placeholder notes should not leak into the preset."""
        preset = build_smart_preset(
            "INVALID",
            [],
            "AI Agents (Claude, Copilot, Cursor, Jules)",
            NOTES_PLACEHOLDER,
        )
        assert preset.project_type is ProjectType.GENERIC
        assert preset.focus_areas == []
        assert preset.additional_notes == ""

    def test_focus_labels_from_fake_widget_collection(self) -> None:
        """Fake checkbox collection should feed labels into build_smart_preset."""
        selections = {
            FocusArea.TESTING: FakeBooleanVar(True),
            FocusArea.SECURITY: FakeBooleanVar(False),
        }
        labels = [area.value[1] for area in selected_focus_areas(selections)]
        preset = build_smart_preset(
            "LIBRARY",
            labels,
            "Team DevOps / SRE",
            "",
        )
        assert preset.project_type is ProjectType.LIBRARY
        assert preset.focus_areas == [FocusArea.TESTING]
        assert preset.additional_notes == ""

    def test_audience_nul_and_esc_are_stripped(self) -> None:
        """C0 / ESC in target_audience must not leak into the preset."""
        preset = build_smart_preset(
            "GENERIC",
            [],
            "Devs\x00\x1bteam",
            "Documenta le API",
        )
        assert "\x00" not in preset.target_audience
        assert "\x1b" not in preset.target_audience
        assert "Devs" in preset.target_audience
        assert "team" in preset.target_audience
        assert all(ord(ch) >= 32 and ord(ch) != 127 for ch in preset.target_audience)

    def test_audience_newlines_stay_a_single_field(self) -> None:
        """Newlines in audience are collapsed or stripped so it stays one field."""
        preset = build_smart_preset(
            "GENERIC",
            [],
            "Devs\nteam\r\nops",
            "Keep these notes",
        )
        assert "\n" not in preset.target_audience
        assert "\r" not in preset.target_audience
        assert "Devs" in preset.target_audience
        assert "team" in preset.target_audience
        assert "ops" in preset.target_audience

    def test_notes_c0_and_placeholder_unchanged_with_dirty_audience(self) -> None:
        """additional_notes C0 strip and placeholder drop stay as before."""
        with_controls = build_smart_preset(
            "GENERIC",
            [],
            "Sviluppatori Senior / Architect",
            "Documenta\x00 le API\x07",
        )
        assert with_controls.additional_notes == "Documenta le API"

        placeholder = build_smart_preset(
            "GENERIC",
            [],
            "Devs\x00\x1bteam",
            NOTES_PLACEHOLDER,
        )
        assert placeholder.additional_notes == ""
        assert "\x00" not in placeholder.target_audience
        assert "\x1b" not in placeholder.target_audience


class TestGuideContent:
    """Tests for GuidePanel copy extracted as module constants."""

    def test_guide_has_three_steps(self) -> None:
        """The guide should describe exactly three setup steps."""
        assert len(GUIDE_STEPS) == 3
        titles = [title for _, title, _, _ in GUIDE_STEPS]
        assert titles == [
            "Configura API",
            "Seleziona Progetto",
            "Genera Documentazione",
        ]

    def test_step_descriptions_cover_the_workflow(self) -> None:
        """Each step description should mention the matching tab or action."""
        descriptions = [desc for _, _, desc, _ in GUIDE_STEPS]
        assert "Setup" in descriptions[0]
        assert "Sfoglia" in descriptions[1]
        assert "Generatore" in descriptions[2]

    def test_step_colors_use_theme_constants(self) -> None:
        """Step accent colors should come from the shared COLORS map."""
        colors = [color for _, _, _, color in GUIDE_STEPS]
        assert colors == [COLORS["primary"], COLORS["teal"], COLORS["success"]]

    def test_tips_mention_shortcuts_and_docs_folder(self) -> None:
        """Tips should include keyboard shortcuts and the /docs output path."""
        joined = " ".join(GUIDE_TIPS)
        assert "Ctrl+O" in joined
        assert "Ctrl+G" in joined
        assert "Ctrl+S" in joined
        assert "F1" in joined
        assert "/docs" in joined
        assert len(GUIDE_TIPS) == 5


class TestFormatPresetPreview:
    """Tests for the SmartPreset panel preview summary (no Tk)."""

    def test_preview_includes_project_type_label(self) -> None:
        """Preview should include the ProjectType display label, not the enum name."""
        preset = SmartPreset(project_type=ProjectType.DEVOPS)
        text = format_preset_preview(preset)
        assert f"TIPO PROGETTO: {ProjectType.DEVOPS.label}" in text
        assert "DEVOPS" not in text

    def test_empty_notes_are_omitted_from_preview(self) -> None:
        """Preview should include type and audience but not a notes line."""
        preset = SmartPreset(
            project_type=ProjectType.WEB_BACKEND,
            target_audience="Sviluppatori Senior / Architect",
            additional_notes="",
        )
        text = format_preset_preview(preset)
        assert "Web Backend" in text
        assert "Sviluppatori Senior / Architect" in text
        assert "NOTE SPECIFICHE" not in text

    def test_whitespace_notes_are_treated_as_empty(self) -> None:
        """Whitespace-only notes should not appear in the preview."""
        preset = SmartPreset(additional_notes="   \n  ")
        text = format_preset_preview(preset)
        assert "NOTE SPECIFICHE" not in text

    def test_short_notes_are_shown_in_full(self) -> None:
        """Notes within the max length should appear untruncated."""
        notes = "Documenta le query SQLAlchemy"
        preset = SmartPreset(additional_notes=notes)
        text = format_preset_preview(preset)
        assert f"NOTE SPECIFICHE: {notes}" in text
        notes_part = text.split("NOTE SPECIFICHE:", 1)[1]
        assert "..." not in notes_part

    def test_long_notes_are_truncated_to_max_length(self) -> None:
        """Notes longer than the preview cap should be ellipsized."""
        notes = "A" * (PREVIEW_NOTES_MAX_LENGTH + 50)
        preset = SmartPreset(additional_notes=notes)
        text = format_preset_preview(preset)
        expected = "A" * PREVIEW_NOTES_MAX_LENGTH + "..."
        assert f"NOTE SPECIFICHE: {expected}" in text
        assert "A" * (PREVIEW_NOTES_MAX_LENGTH + 1) not in text

    def test_exact_max_length_notes_are_not_truncated(self) -> None:
        """Notes exactly at the cap should not gain an ellipsis."""
        notes = "B" * PREVIEW_NOTES_MAX_LENGTH
        preset = SmartPreset(additional_notes=notes)
        text = format_preset_preview(preset)
        assert f"NOTE SPECIFICHE: {notes}" in text
        notes_part = text.split("NOTE SPECIFICHE:", 1)[1]
        assert "..." not in notes_part

    def test_boundary_200_kept_201_truncated_none_and_empty_omitted(self) -> None:
        """200 chars stay intact, 201 are truncated, None/empty are omitted."""
        exact = "C" * 200
        over = "C" * 201

        exact_text = format_preset_preview(SmartPreset(additional_notes=exact))
        assert f"NOTE SPECIFICHE: {exact}" in exact_text
        assert "..." not in exact_text.split("NOTE SPECIFICHE:", 1)[1]

        over_text = format_preset_preview(SmartPreset(additional_notes=over))
        assert f"NOTE SPECIFICHE: {exact}..." in over_text
        assert over not in over_text

        none_preset = SmartPreset()
        none_preset.additional_notes = None  # type: ignore[assignment]
        for preset in (none_preset, SmartPreset(additional_notes="")):
            assert "NOTE SPECIFICHE" not in format_preset_preview(preset)

    def test_custom_max_length_is_honored(self) -> None:
        """A caller-supplied cap should truncate notes at that length."""
        preset = SmartPreset(additional_notes="abcdefghijklmnop")
        text = format_preset_preview(preset, notes_max_length=10)
        assert "NOTE SPECIFICHE: abcdefghij..." in text
        assert "abcdefghijk" not in text
