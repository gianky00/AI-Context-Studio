# -*- coding: utf-8 -*-
"""
Tests for the file scanner module.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_context_studio.scanner import FastFileScanner


class TestFastFileScanner:
    """Tests for FastFileScanner class."""

    def test_create_scanner(self) -> None:
        """Should create scanner instance."""
        scanner = FastFileScanner()
        assert scanner is not None

    def test_scan_empty_directory(self, temp_dir: Path) -> None:
        """Should handle empty directory."""
        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)

        assert result.root_path == temp_dir
        assert result.files == []
        assert result.total_size == 0

    def test_scan_sample_project(self, sample_project: Path) -> None:
        """Should find files in sample project."""
        scanner = FastFileScanner()
        result = scanner.scan(sample_project)

        assert result.root_path == sample_project
        assert len(result.files) > 0

        # Should find Python files
        py_files = [f for f in result.files if f.extension == '.py']
        assert len(py_files) >= 2  # main.py and utils.py

    def test_scan_ignores_pycache(self, sample_project: Path) -> None:
        """Should ignore __pycache__ directory."""
        scanner = FastFileScanner()
        result = scanner.scan(sample_project)

        for file_info in result.files:
            assert "__pycache__" not in file_info.relative_path

    def test_scan_ignores_git(self, sample_project: Path) -> None:
        """Should ignore .git directory."""
        scanner = FastFileScanner()
        result = scanner.scan(sample_project)

        for file_info in result.files:
            assert ".git" not in file_info.relative_path

    def test_files_have_correct_attributes(self, sample_project: Path) -> None:
        """Scanned files should have all required attributes."""
        scanner = FastFileScanner()
        result = scanner.scan(sample_project)

        for file_info in result.files:
            assert file_info.path.exists()
            assert file_info.relative_path
            assert file_info.size >= 0
            assert file_info.extension.startswith('.')
            assert file_info.included is True

    def test_read_files(self, sample_project: Path) -> None:
        """Should read file contents."""
        scanner = FastFileScanner()
        result = scanner.scan(sample_project)
        scanner.read_files(result)

        assert len(result.content_map) > 0

        # Check main.py content
        main_content = None
        for path, content in result.content_map.items():
            if path.endswith("main.py"):
                main_content = content
                break

        assert main_content is not None
        assert "def main" in main_content

    def test_scan_with_progress_callback(self, sample_project: Path) -> None:
        """Should call progress callback during scan."""
        scanner = FastFileScanner()
        progress_calls: list[tuple[str, int]] = []

        def callback(msg: str, pct: int) -> None:
            progress_calls.append((msg, pct))

        scanner.set_progress_callback(callback)
        result = scanner.scan(sample_project)

        assert len(progress_calls) > 0
        # Last call should be completion
        assert progress_calls[-1][1] == 100

    def test_cancel_scan(self, sample_project: Path) -> None:
        """Should be able to cancel scan."""
        scanner = FastFileScanner()

        # Cancel before starting
        scanner.cancel()
        result = scanner.scan(sample_project)

        # Scan should complete but result may vary
        assert result.root_path == sample_project

    def test_nonexistent_directory(self, temp_dir: Path) -> None:
        """Should handle nonexistent directory gracefully."""
        scanner = FastFileScanner()
        nonexistent = temp_dir / "does_not_exist"

        # This should not raise an exception
        result = scanner.scan(nonexistent)
        assert result.files == []


class TestFileFiltering:
    """Tests for file filtering during scan."""

    def test_only_supported_extensions(self, temp_dir: Path) -> None:
        """Should only include supported file extensions."""
        # Create various files
        (temp_dir / "script.py").write_text("# Python")
        (temp_dir / "image.png").write_bytes(b'\x89PNG')
        (temp_dir / "binary.exe").write_bytes(b'\x00\x00')
        (temp_dir / "document.pdf").write_bytes(b'%PDF')
        (temp_dir / "data.json").write_text('{}')

        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)

        extensions = {f.extension for f in result.files}

        assert '.py' in extensions
        assert '.json' in extensions
        assert '.png' not in extensions
        assert '.exe' not in extensions
        assert '.pdf' not in extensions

    def test_hidden_files_ignored(self, temp_dir: Path) -> None:
        """Should ignore hidden files (starting with dot)."""
        (temp_dir / ".hidden.py").write_text("# Hidden")
        (temp_dir / "visible.py").write_text("# Visible")

        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)

        paths = [f.relative_path for f in result.files]
        assert "visible.py" in paths
        assert ".hidden.py" not in paths
