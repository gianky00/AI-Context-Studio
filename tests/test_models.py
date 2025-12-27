# -*- coding: utf-8 -*-
"""
Tests for data models module.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_context_studio.models import (
    FileInfo,
    FocusArea,
    GenerationResult,
    GenerationType,
    ProjectType,
    ScanResult,
    SmartPreset,
)


class TestGenerationType:
    """Tests for GenerationType enum."""

    def test_all_types_have_attributes(self) -> None:
        """All generation types should have required attributes."""
        for gen_type in GenerationType:
            assert hasattr(gen_type, 'filename')
            assert hasattr(gen_type, 'icon')
            assert hasattr(gen_type, 'label')
            assert hasattr(gen_type, 'color')
            assert hasattr(gen_type, 'description')

    def test_filenames_are_markdown(self) -> None:
        """All filenames should end with .md."""
        for gen_type in GenerationType:
            assert gen_type.filename.endswith('.md')

    def test_labels_are_non_empty(self) -> None:
        """All labels should be non-empty strings."""
        for gen_type in GenerationType:
            assert isinstance(gen_type.label, str)
            assert len(gen_type.label) > 0

    def test_architecture_type(self) -> None:
        """Architecture type should have correct filename."""
        assert GenerationType.ARCHITECTURE.filename == "AI_ARCHITECTURE.md"

    def test_rules_type(self) -> None:
        """Rules type should have correct filename."""
        assert GenerationType.RULES.filename == "AI_RULES.md"


class TestProjectType:
    """Tests for ProjectType enum."""

    def test_all_types_have_attributes(self) -> None:
        """All project types should have required attributes."""
        for proj_type in ProjectType:
            assert hasattr(proj_type, 'icon')
            assert hasattr(proj_type, 'label')
            assert hasattr(proj_type, 'description')

    def test_labels_are_unique(self) -> None:
        """All project type labels should be unique."""
        labels = [pt.label for pt in ProjectType]
        assert len(labels) == len(set(labels))

    def test_generic_type_exists(self) -> None:
        """Generic project type should exist."""
        assert ProjectType.GENERIC is not None
        assert ProjectType.GENERIC.label == "Generico"


class TestFocusArea:
    """Tests for FocusArea enum."""

    def test_all_areas_have_attributes(self) -> None:
        """All focus areas should have required attributes."""
        for area in FocusArea:
            assert len(area.value) == 3  # icon, label, description

    def test_security_area_exists(self) -> None:
        """Security focus area should exist."""
        assert FocusArea.SECURITY is not None


class TestFileInfo:
    """Tests for FileInfo dataclass."""

    def test_create_file_info(self) -> None:
        """Should create FileInfo with required fields."""
        file_info = FileInfo(
            path=Path("/test/file.py"),
            relative_path="file.py",
            size=1024,
            extension=".py"
        )
        assert file_info.path == Path("/test/file.py")
        assert file_info.relative_path == "file.py"
        assert file_info.size == 1024
        assert file_info.extension == ".py"
        assert file_info.included is True  # Default

    def test_file_info_default_included(self) -> None:
        """FileInfo should be included by default."""
        file_info = FileInfo(
            path=Path("/test"),
            relative_path="test",
            size=100,
            extension=".py"
        )
        assert file_info.included is True

    def test_file_info_excluded(self) -> None:
        """FileInfo can be marked as excluded."""
        file_info = FileInfo(
            path=Path("/test"),
            relative_path="test",
            size=100,
            extension=".py",
            included=False
        )
        assert file_info.included is False


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_create_scan_result(self) -> None:
        """Should create ScanResult with root path."""
        result = ScanResult(root_path=Path("/project"))
        assert result.root_path == Path("/project")
        assert result.files == []
        assert result.total_size == 0
        assert result.estimated_tokens == 0
        assert result.content_map == {}

    def test_scan_result_with_files(self) -> None:
        """Should store file list."""
        files = [
            FileInfo(
                path=Path("/project/main.py"),
                relative_path="main.py",
                size=500,
                extension=".py"
            )
        ]
        result = ScanResult(root_path=Path("/project"), files=files)
        assert len(result.files) == 1


class TestSmartPreset:
    """Tests for SmartPreset dataclass."""

    def test_create_default_preset(self) -> None:
        """Should create preset with defaults."""
        preset = SmartPreset()
        assert preset.project_type == ProjectType.GENERIC
        assert preset.focus_areas == []
        assert "AI Agents" in preset.target_audience
        assert preset.additional_notes == ""

    def test_preset_to_prompt_context(self) -> None:
        """Should generate prompt context string."""
        preset = SmartPreset(
            project_type=ProjectType.WEB_FRONTEND,
            focus_areas=[FocusArea.SECURITY, FocusArea.PERFORMANCE],
            additional_notes="Custom note"
        )
        context = preset.to_prompt_context()

        assert "Web Frontend" in context
        assert "Sicurezza" in context
        assert "Performance" in context
        assert "Custom note" in context
        assert "ESAUSTIVO" in context

    def test_preset_without_notes(self) -> None:
        """Preset context should work without notes."""
        preset = SmartPreset()
        context = preset.to_prompt_context()
        assert "NOTE SPECIFICHE" not in context


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_create_success_result(self) -> None:
        """Should create successful result."""
        result = GenerationResult(
            success=True,
            doc_type=GenerationType.ARCHITECTURE,
            content="# Architecture\n\nContent here.",
            tokens_used=100,
            generation_time=2.5
        )
        assert result.success is True
        assert result.doc_type == GenerationType.ARCHITECTURE
        assert "Architecture" in result.content
        assert result.tokens_used == 100
        assert result.generation_time == 2.5
        assert result.error_message == ""

    def test_create_failure_result(self) -> None:
        """Should create failed result."""
        result = GenerationResult(
            success=False,
            doc_type=GenerationType.RULES,
            error_message="API Error"
        )
        assert result.success is False
        assert result.error_message == "API Error"
        assert result.content == ""

    def test_result_retries(self) -> None:
        """Should track retry count."""
        result = GenerationResult(
            success=True,
            doc_type=GenerationType.CONTEXT,
            retries=2
        )
        assert result.retries == 2
