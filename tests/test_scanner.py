# -*- coding: utf-8 -*-
"""
Tests for the file scanner module.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest

from ai_context_studio.constants import MAX_FILE_SIZE, MAX_SCAN_DEPTH, SUPPORTED_EXTENSIONS
from ai_context_studio.models import FileInfo, ScanResult
from ai_context_studio.scanner import FastFileScanner

# Content long enough to pass the short-doc outdated heuristic (>= 200 chars)
# without matching placeholder tokens such as "wip" or "tbd".
_SUBSTANTIAL_DOC = (
    "This is a complete project documentation file covering architecture, "
    "setup, and usage for contributors and operators of the sample project. "
    "It includes enough detail to be treated as finished documentation.\n"
)


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
        scanner.scan(sample_project)

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

    def test_scan_file_path_does_not_crash(self, temp_dir: Path) -> None:
        """Scanning a file path (not a directory) should not raise."""
        target = temp_dir / "single.py"
        target.write_text("print('ok')\n", encoding="utf-8")

        scanner = FastFileScanner()
        result = scanner.scan(target)

        assert result.root_path == target
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


class TestDetectExistingDocs:
    """Tests for FastFileScanner.detect_existing_docs."""

    def test_detects_readme_md(self, temp_dir: Path) -> None:
        """Should detect README.md in the project root."""
        (temp_dir / "README.md").write_text(_SUBSTANTIAL_DOC, encoding="utf-8")
        (temp_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")

        scanner = FastFileScanner()
        result = ScanResult(root_path=temp_dir)
        scanner.detect_existing_docs(result)

        assert "README.md" in result.existing_docs
        doc = result.existing_docs["README.md"]
        assert doc.filename == "README.md"
        assert doc.relative_path == "README.md"
        assert doc.path == temp_dir / "README.md"
        assert _SUBSTANTIAL_DOC in doc.content

    def test_detects_ai_architecture_md(self, temp_dir: Path) -> None:
        """Should detect GenerationType filenames such as AI_ARCHITECTURE.md."""
        (temp_dir / "AI_ARCHITECTURE.md").write_text(
            _SUBSTANTIAL_DOC, encoding="utf-8"
        )

        scanner = FastFileScanner()
        result = ScanResult(root_path=temp_dir)
        scanner.detect_existing_docs(result)

        assert "AI_ARCHITECTURE.md" in result.existing_docs
        doc = result.existing_docs["AI_ARCHITECTURE.md"]
        assert doc.filename == "AI_ARCHITECTURE.md"
        assert doc.relative_path == "AI_ARCHITECTURE.md"

    def test_detects_docs_folder_markdown(self, temp_dir: Path) -> None:
        """Should include markdown files inside a docs/ folder."""
        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()
        (docs_dir / "guide.md").write_text(_SUBSTANTIAL_DOC, encoding="utf-8")
        (docs_dir / "notes.md").write_text(_SUBSTANTIAL_DOC, encoding="utf-8")
        (temp_dir / "unrelated.md").write_text(
            _SUBSTANTIAL_DOC, encoding="utf-8"
        )

        scanner = FastFileScanner()
        result = ScanResult(root_path=temp_dir)
        scanner.detect_existing_docs(result)

        assert "guide.md" in result.existing_docs
        assert "notes.md" in result.existing_docs
        assert result.existing_docs["guide.md"].relative_path == str(
            Path("docs") / "guide.md"
        )
        # Unknown markdown in the project root is not treated as a doc.
        assert "unrelated.md" not in result.existing_docs

    def test_outdated_short_content(self, temp_dir: Path) -> None:
        """Docs shorter than 200 characters should be marked outdated."""
        short = "# Sample Project\n\nThis is a test project.\n"
        assert len(short) < 200
        (temp_dir / "README.md").write_text(short, encoding="utf-8")

        scanner = FastFileScanner()
        result = ScanResult(root_path=temp_dir)
        scanner.detect_existing_docs(result)

        assert result.existing_docs["README.md"].is_outdated is True

    def test_outdated_empty_content(self, temp_dir: Path) -> None:
        """Empty documentation files should be marked outdated."""
        (temp_dir / "README.md").write_text("", encoding="utf-8")

        scanner = FastFileScanner()
        result = ScanResult(root_path=temp_dir)
        scanner.detect_existing_docs(result)

        assert result.existing_docs["README.md"].is_outdated is True

    def test_outdated_todo_placeholder(self, temp_dir: Path) -> None:
        """Docs containing TODO: placeholders should be marked outdated."""
        content = _SUBSTANTIAL_DOC + "\nTODO: fill in remaining sections.\n"
        assert len(content) >= 200
        (temp_dir / "README.md").write_text(content, encoding="utf-8")

        scanner = FastFileScanner()
        result = ScanResult(root_path=temp_dir)
        scanner.detect_existing_docs(result)

        assert result.existing_docs["README.md"].is_outdated is True

    def test_outdated_fixme_placeholder(self, temp_dir: Path) -> None:
        """Docs containing FIXME: placeholders should be marked outdated."""
        content = _SUBSTANTIAL_DOC + "\nFIXME: this section is incomplete.\n"
        assert len(content) >= 200
        (temp_dir / "AI_ARCHITECTURE.md").write_text(content, encoding="utf-8")

        scanner = FastFileScanner()
        result = ScanResult(root_path=temp_dir)
        scanner.detect_existing_docs(result)

        assert result.existing_docs["AI_ARCHITECTURE.md"].is_outdated is True

    def test_substantial_content_not_outdated(self, temp_dir: Path) -> None:
        """Long docs without placeholders should not be marked outdated."""
        assert len(_SUBSTANTIAL_DOC) >= 200
        (temp_dir / "README.md").write_text(_SUBSTANTIAL_DOC, encoding="utf-8")

        scanner = FastFileScanner()
        result = ScanResult(root_path=temp_dir)
        scanner.detect_existing_docs(result)

        assert result.existing_docs["README.md"].is_outdated is False

    def test_path_outside_root_does_not_crash_detect_existing_docs(
        self, temp_dir: Path
    ) -> None:
        """A DirEntry whose path is not under root must be omitted, not crash."""
        project = temp_dir / "project"
        project.mkdir()
        (project / "README.md").write_text(_SUBSTANTIAL_DOC, encoding="utf-8")

        outside = temp_dir / "outside_root"
        outside.mkdir()
        outsider = outside / "CHANGELOG.md"
        outsider.write_text(_SUBSTANTIAL_DOC, encoding="utf-8")

        class _OutsideRootDocEntry:
            name = "CHANGELOG.md"
            path = str(outsider)

            def is_file(self, follow_symlinks: bool = True) -> bool:
                return True

        real_scandir = os.scandir
        project_resolved = project.resolve()

        def scandir_with_outsider(path: object) -> object:
            with real_scandir(path) as it:
                entries = list(it)
            if Path(str(path)).resolve() == project_resolved:
                return iter([_OutsideRootDocEntry(), *entries])
            return iter(entries)

        scanner = FastFileScanner()
        result = ScanResult(root_path=project)
        with patch(
            "ai_context_studio.scanner.os.scandir", scandir_with_outsider
        ):
            scanner.detect_existing_docs(result)

        assert "README.md" in result.existing_docs
        assert "CHANGELOG.md" not in result.existing_docs
        for doc in result.existing_docs.values():
            assert outsider not in (doc.path, Path(doc.relative_path))


class TestDocScanSymlinkSkip:
    """Doc detection must not follow symlinks to files or trees outside the project."""

    def test_scan_for_docs_rejects_symlink_direntry(self, temp_dir: Path) -> None:
        """DirEntry.is_file() follows; docs scan must pass follow_symlinks=False."""
        project = temp_dir / "project"
        project.mkdir()
        secret = (
            "MOCKED_SYMLINK_SECRET_MUST_NOT_ENTER_EXISTING_DOCS_"
            + ("z" * 160)
        )
        target = project / "README.md"
        target.write_text(secret, encoding="utf-8")

        class _SymlinkDocEntry:
            name = "README.md"
            path = str(target)

            def is_file(self, follow_symlinks: bool = True) -> bool:
                return follow_symlinks

        scanner = FastFileScanner()
        result = ScanResult(root_path=project)
        with patch("ai_context_studio.scanner.os.scandir", return_value=iter([_SymlinkDocEntry()])):
            scanner.detect_existing_docs(result)

        assert "README.md" not in result.existing_docs
        for doc in result.existing_docs.values():
            assert secret not in doc.content

    def test_skips_symlinked_docs_folder_via_is_symlink(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A docs/ path that reports as a symlink must not be walked for .md files."""
        project = temp_dir / "project"
        project.mkdir()
        docs = project / "docs"
        docs.mkdir()
        secret = (
            "SYMLINKED_DOCS_FOLDER_SECRET_MUST_NOT_APPEAR_"
            + ("w" * 160)
        )
        (docs / "evil.md").write_text(secret, encoding="utf-8")

        docs_resolved = docs.resolve()
        original_is_symlink = Path.is_symlink

        def is_symlink_guard(self: Path) -> bool:
            try:
                if self.resolve() == docs_resolved:
                    return True
            except OSError:
                pass
            return original_is_symlink(self)

        monkeypatch.setattr(Path, "is_symlink", is_symlink_guard)

        scanner = FastFileScanner()
        result = ScanResult(root_path=project)
        scanner.detect_existing_docs(result)

        assert "evil.md" not in result.existing_docs
        for doc in result.existing_docs.values():
            assert secret not in doc.content

    def test_skips_file_symlink_named_like_known_doc(self, temp_dir: Path) -> None:
        """A README.md symlink pointing outside the project must not leak content."""
        outside = temp_dir / "outside_root"
        outside.mkdir()
        secret = (
            "OUTSIDE_SECRET_DOC_CONTENT_MUST_NOT_LEAK_INTO_EXISTING_DOCS_"
            + ("x" * 160)
        )
        evil = outside / "leaked.md"
        evil.write_text(secret, encoding="utf-8")

        project = temp_dir / "project"
        project.mkdir()
        link = project / "README.md"
        try:
            link.symlink_to(evil)
        except OSError:
            pytest.skip("symlink creation is not permitted on this Windows account")

        scanner = FastFileScanner()
        result = ScanResult(root_path=project)
        scanner.detect_existing_docs(result)

        assert "README.md" not in result.existing_docs
        for doc in result.existing_docs.values():
            assert secret not in doc.content

    def test_skips_docs_folder_symlink_to_outside_tree(self, temp_dir: Path) -> None:
        """A docs/ directory symlink to an outside tree must not list those files."""
        outside = temp_dir / "outside_docs"
        outside.mkdir()
        secret = (
            "OUTSIDE_DOCS_TREE_SECRET_MUST_NOT_APPEAR_IN_EXISTING_DOCS_"
            + ("y" * 160)
        )
        (outside / "evil.md").write_text(secret, encoding="utf-8")

        project = temp_dir / "project"
        project.mkdir()
        docs = project / "docs"
        try:
            docs.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip("symlink creation is not permitted on this Windows account")

        scanner = FastFileScanner()
        result = ScanResult(root_path=project)
        scanner.detect_existing_docs(result)

        assert "evil.md" not in result.existing_docs
        for doc in result.existing_docs.values():
            assert secret not in doc.content


class TestMaxFileSizeSkip:
    """Tests for skipping files larger than MAX_FILE_SIZE during scan."""

    def test_skips_file_over_max_size(self, temp_dir: Path) -> None:
        """Files larger than MAX_FILE_SIZE should not appear in scan results."""
        (temp_dir / "small.py").write_text("print('ok')\n", encoding="utf-8")
        oversized = temp_dir / "huge.py"
        oversized.write_bytes(b"x" * (MAX_FILE_SIZE + 1))

        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)

        paths = [f.relative_path for f in result.files]
        assert "small.py" in paths
        assert "huge.py" not in paths

    def test_includes_file_at_max_size(self, temp_dir: Path) -> None:
        """Files exactly at MAX_FILE_SIZE should still be included."""
        at_limit = temp_dir / "limit.py"
        at_limit.write_bytes(b"x" * MAX_FILE_SIZE)

        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)

        paths = [f.relative_path for f in result.files]
        assert "limit.py" in paths
        matching = [f for f in result.files if f.relative_path == "limit.py"]
        assert matching[0].size == MAX_FILE_SIZE


class TestMaxScanDepth:
    """A tree deeper than MAX_SCAN_DEPTH must not crash the scan."""

    def test_scan_does_not_crash_beyond_max_depth(self, temp_dir: Path) -> None:
        """Files past MAX_SCAN_DEPTH are skipped; shallower files are kept."""
        (temp_dir / "shallow.py").write_text("shallow = True\n", encoding="utf-8")

        current = temp_dir
        for i in range(MAX_SCAN_DEPTH):
            current = current / f"d{i}"
            current.mkdir()
        (current / "at_limit.py").write_text("at_limit = True\n", encoding="utf-8")

        beyond = current / "too_deep"
        beyond.mkdir()
        (beyond / "too_deep.py").write_text("too_deep = True\n", encoding="utf-8")

        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)

        paths = [f.relative_path.replace("\\", "/") for f in result.files]
        assert "shallow.py" in paths
        assert any(path.endswith("at_limit.py") for path in paths)
        assert not any(path.endswith("too_deep.py") for path in paths)


class TestSymlinkSkip:
    """Symlinks must not pull files from outside the scanned tree."""

    def test_skips_file_symlink(self, temp_dir: Path) -> None:
        real = temp_dir / "real.py"
        real.write_text("value = 1\n", encoding="utf-8")
        link = temp_dir / "alias.py"
        try:
            link.symlink_to(real)
        except OSError:
            pytest.skip("symlink creation is not permitted on this Windows account")

        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)
        paths = [f.relative_path for f in result.files]
        assert "real.py" in paths
        assert "alias.py" not in paths

    def test_skips_directory_symlink_outside_tree(self, temp_dir: Path) -> None:
        outside = temp_dir / "outside_root"
        outside.mkdir()
        (outside / "secret.py").write_text("secret = True\n", encoding="utf-8")

        project = temp_dir / "project"
        project.mkdir()
        (project / "app.py").write_text("app = True\n", encoding="utf-8")
        vendor = project / "vendor"
        try:
            vendor.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip("symlink creation is not permitted on this Windows account")

        scanner = FastFileScanner()
        result = scanner.scan(project)
        paths = [f.relative_path.replace("\\", "/") for f in result.files]
        assert "app.py" in paths
        assert not any(path.endswith("secret.py") for path in paths)


class TestReadFilesPathGuard:
    def test_read_files_skips_path_outside_root(self, temp_dir: Path) -> None:
        project = temp_dir / "project"
        project.mkdir()
        insider = project / "ok.py"
        insider.write_text("ok = True\n", encoding="utf-8")
        outsider = temp_dir / "secret.py"
        outsider.write_text("secret = True\n", encoding="utf-8")

        result = ScanResult(root_path=project)
        result.files = [
            FileInfo(path=insider, relative_path="ok.py", size=10, extension=".py"),
            FileInfo(
                path=outsider,
                relative_path="secret.py",
                size=14,
                extension=".py",
            ),
        ]
        scanner = FastFileScanner()
        scanner.read_files(result)

        assert "ok.py" in result.content_map
        assert "ok = True" in result.content_map["ok.py"]
        assert "secret.py" not in result.content_map


class TestReadFilesStaleMap:
    """A later read_files must drop content_map keys for files no longer included."""

    def test_read_files_drops_excluded_keys_keeps_included(
        self, temp_dir: Path
    ) -> None:
        (temp_dir / "keep.py").write_text("keep = 1\n", encoding="utf-8")
        (temp_dir / "drop.py").write_text("drop = 1\n", encoding="utf-8")

        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)
        scanner.read_files(result)

        assert "keep.py" in result.content_map
        assert "drop.py" in result.content_map

        for file_info in result.files:
            if file_info.relative_path == "drop.py":
                file_info.included = False

        (temp_dir / "keep.py").write_text("keep = 2\n", encoding="utf-8")
        scanner.read_files(result)

        assert "drop.py" not in result.content_map
        assert "keep.py" in result.content_map
        assert "keep = 2" in result.content_map["keep.py"]

    def test_read_files_empty_reread_updates_map(self, temp_dir: Path) -> None:
        """An included file truncated to empty must replace the previous body."""
        (temp_dir / "keep.py").write_text("keep = 1\n", encoding="utf-8")
        (temp_dir / "empty_me.py").write_text("old body\n", encoding="utf-8")

        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)
        scanner.read_files(result)

        assert result.content_map["keep.py"] == "keep = 1\n"
        assert result.content_map["empty_me.py"] == "old body\n"

        (temp_dir / "empty_me.py").write_text("", encoding="utf-8")
        scanner.read_files(result)

        assert result.content_map["empty_me.py"] == ""
        assert result.content_map["keep.py"] == "keep = 1\n"

    def test_read_files_none_keeps_previous_content(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A None read (failure / binary skip) must not wipe a still-included key."""
        (temp_dir / "keep.py").write_text("keep = 1\n", encoding="utf-8")
        (temp_dir / "flaky.py").write_text("flaky = 1\n", encoding="utf-8")

        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)
        scanner.read_files(result)

        assert result.content_map["flaky.py"] == "flaky = 1\n"
        assert result.content_map["keep.py"] == "keep = 1\n"

        original = scanner._read_file_safe
        flaky_path = (temp_dir / "flaky.py").resolve()

        def none_for_flaky(path: Path) -> Optional[str]:
            if path.resolve() == flaky_path:
                return None
            return original(path)

        monkeypatch.setattr(scanner, "_read_file_safe", none_for_flaky)
        scanner.read_files(result)

        assert result.content_map["flaky.py"] == "flaky = 1\n"
        assert result.content_map["keep.py"] == "keep = 1\n"


class TestReadFilesBinarySkip:
    """Binary or undecodable files must not enter the context map."""

    def test_skips_binary_undecodable_file(self, temp_dir: Path) -> None:
        """A supported-extension file with NUL bytes should not be read."""
        (temp_dir / "good.py").write_text("value = 1\n", encoding="utf-8")
        (temp_dir / "blob.py").write_bytes(b"\x00\x01\x02\xff\xfe\x00binary")

        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)
        scanner.read_files(result)

        assert "good.py" in result.content_map
        assert "value = 1" in result.content_map["good.py"]
        assert "blob.py" not in result.content_map


class TestReadFilesCancel:
    """Cancellation during read_files must stop filling content_map."""

    def test_cancel_during_read_files_stops_filling_content_map(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (temp_dir / "a.py").write_text("a = 1\n", encoding="utf-8")
        (temp_dir / "b.py").write_text("b = 2\n", encoding="utf-8")
        (temp_dir / "c.py").write_text("c = 3\n", encoding="utf-8")

        scanner = FastFileScanner()
        result = scanner.scan(temp_dir)
        assert len(result.files) == 3

        original = scanner._read_file_safe

        def read_then_cancel(path: Path) -> Optional[str]:
            content = original(path)
            scanner.cancel()
            return content

        monkeypatch.setattr(scanner, "_read_file_safe", read_then_cancel)
        scanner.read_files(result)

        assert len(result.content_map) == 1


class TestPermissionErrorSkip:
    """A permission-denied subdirectory must not crash the scan."""

    def test_permission_error_on_subdirectory_does_not_crash(
        self, temp_dir: Path
    ) -> None:
        (temp_dir / "ok.py").write_text("ok = True\n", encoding="utf-8")
        readable = temp_dir / "src"
        readable.mkdir()
        (readable / "app.py").write_text("app = True\n", encoding="utf-8")
        blocked = temp_dir / "blocked"
        blocked.mkdir()
        (blocked / "secret.py").write_text("secret = True\n", encoding="utf-8")

        real_scandir = os.scandir
        blocked_resolved = blocked.resolve()

        def scandir_maybe_blocked(path: object) -> object:
            if Path(str(path)).resolve() == blocked_resolved:
                raise PermissionError("Access is denied")
            return real_scandir(path)

        scanner = FastFileScanner()
        with patch("ai_context_studio.scanner.os.scandir", scandir_maybe_blocked):
            result = scanner.scan(temp_dir)

        paths = [f.relative_path.replace("\\", "/") for f in result.files]
        assert "ok.py" in paths
        assert "src/app.py" in paths
        assert not any(path.endswith("secret.py") for path in paths)


class TestProcessFileOutsideRoot:
    """A DirEntry whose path is not under the scan root must be skipped."""

    def test_process_file_path_outside_root_does_not_raise(
        self, temp_dir: Path
    ) -> None:
        """ValueError from Path.relative_to must not abort _process_file."""
        assert ".py" in SUPPORTED_EXTENSIONS

        root = temp_dir / "project"
        root.mkdir()
        outside_path = str(temp_dir / "outside_root" / "evil.py")

        class _SmallStat:
            st_size = 64

        class _OutsideRootFileEntry:
            name = "evil.py"
            path = outside_path

            def stat(self, follow_symlinks: bool = True) -> _SmallStat:
                return _SmallStat()

        scanner = FastFileScanner()
        files: list[FileInfo] = []
        scanner._process_file(_OutsideRootFileEntry(), root, files)

        assert files == []
