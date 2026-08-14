# -*- coding: utf-8 -*-
"""Tests for local path containment (no Tk, no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_context_studio.path_safety import is_path_inside, resolve_contained_file


class TestResolveContainedFile:
    def test_plain_markdown_name(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        result = resolve_contained_file(docs, "AI_ARCHITECTURE.md")
        assert result == (docs / "AI_ARCHITECTURE.md").resolve()
        assert result.parent == docs.resolve()

    def test_rejects_parent_directory(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError, match="single path component"):
            resolve_contained_file(docs, "../secret.md")

    def test_rejects_windows_parent(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError, match="single path component"):
            resolve_contained_file(docs, "..\\secret.md")

    def test_rejects_absolute_path(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError, match="absolute"):
            resolve_contained_file(docs, str(temp_dir / "outside.md"))

    def test_rejects_nested_relative(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError, match="single path component"):
            resolve_contained_file(docs, "sub/AI_RULES.md")

    def test_rejects_empty_and_dots(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "")
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "   ")
        with pytest.raises(ValueError):
            resolve_contained_file(docs, ".")
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "..")

    def test_rejects_colon_in_name(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "C:outside.md")

    def test_rejects_nul_in_name(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "file\0.md")
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "\0")

    def test_rejects_embedded_newline_in_name(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "file\n.md")
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "ok\nbad.md")

    def test_rejects_tab_in_filename(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "file\t.md")
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "ok\tbad.md")

    @pytest.mark.parametrize("control", ["\x0b", "\x0c", "\x1b", "\x7f"])
    def test_rejects_remaining_c0_and_del_in_filename(
        self, temp_dir: Path, control: str
    ) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError):
            resolve_contained_file(docs, f"file{control}.md")

    def test_rejects_trailing_slash_names(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "AI_ARCHITECTURE.md/")
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "AI_ARCHITECTURE.md\\")

    def test_rejects_unc_like_name(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError, match="absolute"):
            resolve_contained_file(docs, r"\\server\share\file.md")
        with pytest.raises(ValueError, match="absolute"):
            resolve_contained_file(docs, "//server/share/file.md")

    @pytest.mark.parametrize(
        "reserved",
        [
            "NUL",
            "nul",
            "CON",
            "CON.md",
            "AUX.txt",
            "PRN",
            "COM1",
            "COM9",
            "LPT1",
            "LPT9",
            "CONIN$",
            "CONIN$.md",
            "conout$",
            "CONOUT$.txt",
        ],
    )
    def test_rejects_windows_reserved_device_names(
        self, temp_dir: Path, reserved: str
    ) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError):
            resolve_contained_file(docs, reserved)

    def test_allows_console_md_not_reserved(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        result = resolve_contained_file(docs, "CONSOLE.md")
        assert result == (docs / "CONSOLE.md").resolve()

    def test_rejects_trailing_dot_in_filename(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "AI_ARCHITECTURE.md.")

    def test_rejects_trailing_space_in_filename(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        with pytest.raises(ValueError):
            resolve_contained_file(docs, "AI_ARCHITECTURE.md ")

    def test_allows_internal_dots_in_filename(self, temp_dir: Path) -> None:
        docs = temp_dir / "docs"
        docs.mkdir()
        result = resolve_contained_file(docs, "file.name.md")
        assert result == (docs / "file.name.md").resolve()


class TestIsPathInside:
    def test_file_inside_root(self, temp_dir: Path) -> None:
        child = temp_dir / "src" / "app.py"
        child.parent.mkdir()
        child.write_text("x = 1\n", encoding="utf-8")
        assert is_path_inside(child, temp_dir) is True

    def test_equal_root(self, temp_dir: Path) -> None:
        assert is_path_inside(temp_dir, temp_dir) is True

    def test_file_that_is_the_root_itself(self, temp_dir: Path) -> None:
        file_root = temp_dir / "project.py"
        file_root.write_text("x = 1\n", encoding="utf-8")
        assert is_path_inside(file_root, file_root) is True

    def test_nested_file(self, temp_dir: Path) -> None:
        nested = temp_dir / "src" / "pkg" / "mod.py"
        nested.parent.mkdir(parents=True)
        nested.write_text("x = 1\n", encoding="utf-8")
        assert is_path_inside(nested, temp_dir) is True

    def test_sibling_outside_root(self, temp_dir: Path) -> None:
        root = temp_dir / "project"
        root.mkdir()
        outsider = temp_dir / "secret.py"
        outsider.write_text("secret = 1\n", encoding="utf-8")
        assert is_path_inside(outsider, root) is False

    def test_unc_like_path_not_inside_local_root(self, temp_dir: Path) -> None:
        unc = Path(r"\\?\UNC\server\share\file.md")
        assert is_path_inside(unc, temp_dir) is False
