# -*- coding: utf-8 -*-
"""
Tests for file-tree helpers that do not require a Tk window.
"""

from __future__ import annotations

import os
from pathlib import Path

from ai_context_studio.constants import DEFAULT_IGNORED_DIRS, FILE_ICONS
from ai_context_studio.models import FileInfo
from ai_context_studio.ui.file_tree import (
    _DEFAULT_FILE_ICON,
    display_name_from_relative_path,
    file_icon_for_extension,
    find_file_by_relative_path,
    group_files_by_directory,
    included_files,
    relative_path_dir_key,
    set_files_included,
    toggle_files_included,
)


def _file(
    relative_path: str,
    *,
    size: int = 100,
    included: bool = True,
) -> FileInfo:
    """Build a FileInfo for helper tests (no filesystem access)."""
    extension = Path(relative_path).suffix.lower()
    return FileInfo(
        path=Path(relative_path),
        relative_path=relative_path,
        size=size,
        extension=extension,
        included=included,
    )


class TestRelativePathDirKey:
    """Tests for grouping files by top-level directory key."""

    def test_root_file_groups_under_dot(self) -> None:
        """A file with no separator should group under '.'."""
        assert relative_path_dir_key("README.md") == "."

    def test_nested_file_uses_first_segment(self) -> None:
        """A nested path should use the first segment as the directory key."""
        nested = os.path.join("src", "main.py")
        assert relative_path_dir_key(nested) == "src"

    def test_deeper_nesting_still_uses_first_segment(self) -> None:
        """Deeper paths should still key on the first directory only."""
        nested = os.path.join("src", "ui", "file_tree.py")
        assert relative_path_dir_key(nested) == "src"

    def test_empty_string_groups_under_dot(self) -> None:
        """An empty relative path has no separator, so it groups under '.'."""
        assert relative_path_dir_key("") == "."

    def test_forward_slash_path_uses_first_segment(self) -> None:
        """POSIX-style forward-slash paths should still key on the first directory."""
        assert relative_path_dir_key("src/main.py") == "src"

    def test_mixed_separators_use_first_segment(self) -> None:
        """A mixed backslash/forward-slash path should still use the first segment."""
        assert relative_path_dir_key("src\\nested/file.py") == "src"

    def test_leading_slash_uses_first_nonempty_segment(self) -> None:
        """A leading slash must not become an empty directory key."""
        assert relative_path_dir_key("/src/main.py") == "src"

    def test_double_slash_uses_first_nonempty_segment(self) -> None:
        """Empty segments from doubled slashes should be ignored."""
        assert relative_path_dir_key("src//main.py") == "src"

    def test_parent_segment_groups_under_dot(self) -> None:
        """A leading '..' segment should be dropped so the file groups at root."""
        assert relative_path_dir_key("../main.py") == "."

    def test_dot_segment_uses_first_real_directory(self) -> None:
        """A leading '.' segment should be dropped so the next directory is the key."""
        assert relative_path_dir_key("./src/main.py") == "src"

    def test_embedded_dot_segment_uses_first_real_directory(self) -> None:
        """An embedded '.' segment should be ignored when choosing the directory key."""
        assert relative_path_dir_key("src/./main.py") == "src"

    def test_nul_in_directory_segment_is_dropped_from_key(self) -> None:
        """C0 characters in a directory segment must not appear in the grouping key."""
        key = relative_path_dir_key("src\x00/main.py")
        assert key == "src"
        assert "\x00" not in key


class TestFileIconForExtension:
    """Tests for FILE_ICONS lookup used by the tree."""

    def test_known_extension_uses_file_icons(self) -> None:
        """Known extensions should return the mapped FILE_ICONS value."""
        assert file_icon_for_extension(".py") == FILE_ICONS[".py"]
        assert file_icon_for_extension(".md") == FILE_ICONS[".md"]

    def test_unknown_extension_uses_default_icon(self) -> None:
        """Unknown extensions should fall back to the default document icon."""
        assert file_icon_for_extension(".xyz") == _DEFAULT_FILE_ICON
        assert file_icon_for_extension("") == _DEFAULT_FILE_ICON

    def test_lookup_is_case_insensitive(self) -> None:
        """Windows scanner extensions are often mixed-case; lookup must ignore case."""
        assert file_icon_for_extension(".PY") == FILE_ICONS[".py"]
        assert file_icon_for_extension(".Ts") == FILE_ICONS[".ts"]
        assert file_icon_for_extension(".MD") == FILE_ICONS[".md"]
        assert file_icon_for_extension(".UNKNOWN") == _DEFAULT_FILE_ICON
        assert file_icon_for_extension("") == _DEFAULT_FILE_ICON


class TestFindFileByRelativePath:
    """Tests for path-key lookup used by include/exclude toggles."""

    def test_finds_matching_file(self) -> None:
        """Should return the file whose relative_path matches."""
        files = [_file("a.py"), _file(os.path.join("src", "b.py"))]
        found = find_file_by_relative_path(files, os.path.join("src", "b.py"))
        assert found is files[1]

    def test_returns_none_when_missing(self) -> None:
        """Should return None when no file matches the path key."""
        files = [_file("a.py")]
        assert find_file_by_relative_path(files, "missing.py") is None

    def test_returns_first_match(self) -> None:
        """Duplicate relative paths should resolve to the first file."""
        first = _file("dup.py", size=1)
        second = _file("dup.py", size=2)
        found = find_file_by_relative_path([first, second], "dup.py")
        assert found is first


class TestIncludeExcludeToggle:
    """Tests for include/exclude/toggle helpers used by the tree."""

    def test_set_files_included_true(self) -> None:
        """set_files_included(True) should mark every file included."""
        files = [_file("a.py", included=False), _file("b.py", included=False)]
        set_files_included(files, True)
        assert all(f.included for f in files)

    def test_set_files_included_false(self) -> None:
        """set_files_included(False) should mark every file excluded."""
        files = [_file("a.py", included=True), _file("b.py", included=True)]
        set_files_included(files, False)
        assert all(not f.included for f in files)

    def test_toggle_files_included_inverts_each(self) -> None:
        """toggle_files_included should invert each file independently."""
        files = [_file("a.py", included=True), _file("b.py", included=False)]
        toggle_files_included(files)
        assert files[0].included is False
        assert files[1].included is True

    def test_included_files_filters_excluded(self) -> None:
        """included_files should return only files marked included."""
        files = [
            _file("keep.py", included=True),
            _file("skip.py", included=False),
            _file("also.py", included=True),
        ]
        result = included_files(files)
        assert [f.relative_path for f in result] == ["keep.py", "also.py"]

    def test_included_files_returns_new_list_without_mutating_input(self) -> None:
        """Filtering included=False must not alias or shrink the caller's list."""
        keep = _file("keep.py", included=True)
        skip = _file("skip.py", included=False)
        files = [keep, skip]
        result = included_files(files)
        assert result is not files
        assert files == [keep, skip]
        assert result == [keep]
        assert result[0] is keep

    def test_included_files_empty_when_none_selected(self) -> None:
        """included_files should return an empty list when all are excluded."""
        files = [_file("a.py", included=False)]
        assert included_files(files) == []

    def test_helpers_tolerate_empty_list(self) -> None:
        """Include/exclude helpers should be no-ops on an empty list."""
        empty: list[FileInfo] = []
        set_files_included(empty, True)
        toggle_files_included(empty)
        assert included_files(empty) == []
        assert find_file_by_relative_path(empty, "x.py") is None


class TestDisplayNameFromRelativePath:
    """Tests for the basename shown on each tree row."""

    def test_root_file_keeps_filename(self) -> None:
        """A project-root file should display as its own name."""
        assert display_name_from_relative_path("README.md") == "README.md"

    def test_nested_file_uses_basename(self) -> None:
        """A nested path should display only the file name."""
        nested = os.path.join("src", "main.py")
        assert display_name_from_relative_path(nested) == "main.py"

    def test_deeper_nesting_still_uses_basename(self) -> None:
        """Deeper paths should still display only the final segment."""
        nested = os.path.join("src", "ui", "file_tree.py")
        assert display_name_from_relative_path(nested) == "file_tree.py"

    def test_empty_relative_path_is_empty_label(self) -> None:
        """An empty relative path has no basename, so the label is empty."""
        assert display_name_from_relative_path("") == ""

    def test_windows_backslash_path_uses_basename(self) -> None:
        """Windows-style backslash paths should still display only the file name."""
        assert display_name_from_relative_path("src\\main.py") == "main.py"
        assert display_name_from_relative_path("src\\ui\\file_tree.py") == "file_tree.py"

    def test_forward_slash_path_uses_basename(self) -> None:
        """POSIX-style forward-slash paths should still display only the file name."""
        assert display_name_from_relative_path("src/main.py") == "main.py"

    def test_leading_slash_uses_basename(self) -> None:
        """A leading slash should still display only the file name."""
        assert display_name_from_relative_path("/src/main.py") == "main.py"

    def test_double_slash_uses_basename(self) -> None:
        """Empty segments from doubled slashes should not become the label."""
        assert display_name_from_relative_path("src//main.py") == "main.py"

    def test_trailing_slash_uses_last_nonempty_segment(self) -> None:
        """A trailing slash should display the last non-empty segment."""
        assert display_name_from_relative_path("src/main.py/") == "main.py"

    def test_parent_segment_uses_basename(self) -> None:
        """A leading '..' segment should not become the display name."""
        assert display_name_from_relative_path("../main.py") == "main.py"

    def test_dot_segment_uses_basename(self) -> None:
        """A leading '.' segment should not become the display name."""
        assert display_name_from_relative_path("./src/main.py") == "main.py"

    def test_nul_in_filename_is_dropped_from_label(self) -> None:
        """NUL inside a filename segment should be dropped, joining the remaining chars."""
        name = display_name_from_relative_path("src/mai\x00n.py")
        assert name == "main.py"
        assert "\x00" not in name

    def test_newline_in_filename_is_not_in_label(self) -> None:
        """Newlines in a segment must not appear in the tree label."""
        name = display_name_from_relative_path("foo\nbar.py")
        assert "\n" not in name
        assert "\r" not in name
        assert "\x00" not in name
        assert "\x7f" not in name

    def test_del_in_filename_is_dropped_from_label(self) -> None:
        """DEL (0x7F) must not appear in the tree label."""
        name = display_name_from_relative_path("main.py\x7f")
        assert name == "main.py"
        assert "\x7f" not in name


class TestGroupFilesByDirectory:
    """Tests for grouping a scan result without re-filtering ignored dirs."""

    def test_empty_scan_returns_empty_mapping(self) -> None:
        """An empty scan should produce no directory groups."""
        assert group_files_by_directory([]) == {}

    def test_groups_root_and_nested_files(self) -> None:
        """Root files group under '.' and nested files under the first segment."""
        root = _file("README.md")
        nested_a = _file(os.path.join("src", "a.py"))
        nested_b = _file(os.path.join("src", "b.py"))
        grouped = group_files_by_directory([root, nested_a, nested_b])
        assert grouped["."] == [root]
        assert grouped["src"] == [nested_a, nested_b]

    def test_does_not_drop_scanner_ignored_dir_names(self) -> None:
        """The tree must not re-filter dirs the scanner already handled."""
        ignored = next(iter(DEFAULT_IGNORED_DIRS))
        leftover = _file(os.path.join(ignored, "leftover.py"))
        grouped = group_files_by_directory([leftover])
        assert ignored in grouped
        assert grouped[ignored] == [leftover]

    def test_empty_relative_path_groups_under_dot(self) -> None:
        """A file with an empty relative path should group under '.'."""
        empty = _file("")
        grouped = group_files_by_directory([empty])
        assert grouped["."] == [empty]

    def test_windows_backslash_path_groups_under_first_segment(self) -> None:
        """Windows-style backslash paths should group under the first directory."""
        nested = _file("src\\main.py")
        grouped = group_files_by_directory([nested])
        assert grouped["src"] == [nested]

    def test_forward_slash_path_groups_under_first_segment(self) -> None:
        """POSIX-style forward-slash paths should group under the first directory, not '.'."""
        nested = _file("src/main.py")
        grouped = group_files_by_directory([nested])
        assert "." not in grouped
        assert grouped["src"] == [nested]

    def test_mixed_separators_group_under_first_segment(self) -> None:
        """A mixed backslash/forward-slash path should group under the first directory."""
        nested = _file("src\\nested/file.py")
        grouped = group_files_by_directory([nested])
        assert grouped["src"] == [nested]

    def test_leading_slash_groups_under_first_nonempty_segment(self) -> None:
        """A leading-slash path should group under src, not an empty key."""
        nested = _file("/src/main.py")
        grouped = group_files_by_directory([nested])
        assert "" not in grouped
        assert grouped["src"] == [nested]

    def test_double_slash_groups_under_first_nonempty_segment(self) -> None:
        """Doubled slashes should still group under the first real directory."""
        nested = _file("src//main.py")
        grouped = group_files_by_directory([nested])
        assert grouped["src"] == [nested]

    def test_groups_multiple_files_in_same_directory(self) -> None:
        """Several files in the same top-level dir should share one group."""
        first = _file(os.path.join("src", "a.py"))
        second = _file(os.path.join("src", "b.py"))
        third = _file(os.path.join("src", "c.py"))
        grouped = group_files_by_directory([first, second, third])
        assert list(grouped) == ["src"]
        assert grouped["src"] == [first, second, third]

    def test_preserves_insertion_order_of_directories(self) -> None:
        """Directory keys should follow first-seen order, not alphabetical sort."""
        pkg = _file(os.path.join("pkg", "a.py"))
        src = _file(os.path.join("src", "b.py"))
        pkg_again = _file(os.path.join("pkg", "c.py"))
        root = _file("README.md")
        grouped = group_files_by_directory([pkg, src, pkg_again, root])
        assert list(grouped) == ["pkg", "src", "."]
        assert grouped["pkg"] == [pkg, pkg_again]
        assert grouped["src"] == [src]
        assert grouped["."] == [root]
