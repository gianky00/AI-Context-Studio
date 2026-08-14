# -*- coding: utf-8 -*-
"""Tests for SetupTab helpers that do not require a Tk window."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ai_context_studio.ui.setup_tab import (
    SetupTab,
    api_key_is_usable,
    api_status_is_connected,
    format_bundle_file_section,
    markdown_fence_language,
    project_path_is_usable,
    shutdown_scan_resources,
)


class TestMarkdownFenceLanguage:
    """Extension → markdown fence language used when exporting a context bundle."""

    def test_python_extension(self) -> None:
        assert markdown_fence_language(".py") == "python"

    def test_typescript_extension(self) -> None:
        assert markdown_fence_language(".ts") == "typescript"

    def test_javascript_extension(self) -> None:
        assert markdown_fence_language(".js") == "javascript"

    def test_markdown_extension(self) -> None:
        assert markdown_fence_language(".md") == "markdown"

    def test_yml_maps_to_yaml(self) -> None:
        assert markdown_fence_language(".yml") == "yaml"

    def test_unknown_extension_is_empty(self) -> None:
        assert markdown_fence_language(".unknown") == ""

    def test_empty_extension_is_empty(self) -> None:
        assert markdown_fence_language("") == ""

    def test_suffix_matching_is_case_insensitive(self) -> None:
        assert markdown_fence_language(".PY") == "python"
        assert markdown_fence_language(".Ts") == "typescript"
        assert markdown_fence_language(".YML") == "yaml"

    def test_bare_py_normalizes_to_python(self) -> None:
        assert markdown_fence_language("py") == "python"

    def test_bare_yml_uppercase_maps_to_yaml(self) -> None:
        assert markdown_fence_language("YML") == "yaml"

    def test_bare_unknown_extension_is_empty(self) -> None:
        assert markdown_fence_language("unknown") == ""

    @pytest.mark.parametrize(
        "extension, language",
        [
            (".json", "json"),
            (".cs", "csharp"),
            (".html", "html"),
        ],
    )
    def test_existing_map_entries(self, extension: str, language: str) -> None:
        assert markdown_fence_language(extension) == language


class TestFormatBundleFileSection:
    """Pure helper: one bundle file section without writing to disk."""

    def test_python_file_uses_python_fence(self) -> None:
        section = format_bundle_file_section(
            relative_path="src/main.py",
            path="C:/proj/src/main.py",
            size=42,
            content="print('hi')",
        )
        assert section.startswith("## FILE: src/main.py\n")
        assert "## Path: C:/proj/src/main.py\n" in section
        assert "## Size: 42 bytes\n" in section
        assert "```python\nprint('hi')\n```" in section
        assert "-" * 80 in section

    def test_unknown_extension_uses_untagged_fence(self) -> None:
        section = format_bundle_file_section(
            relative_path="notes.xyz",
            path="/tmp/notes.xyz",
            size=1,
            content="hello",
        )
        assert "## FILE: notes.xyz" in section
        assert "```\nhello\n```" in section
        assert "```xyz" not in section

    def test_size_is_thousands_separated(self) -> None:
        section = format_bundle_file_section(
            relative_path="big.ts",
            path="/tmp/big.ts",
            size=1234567,
            content="export {}",
        )
        assert "## Size: 1,234,567 bytes\n" in section
        assert "```typescript\nexport {}\n```" in section

    def test_nested_triple_backticks_do_not_close_fence_early(self) -> None:
        content = "print('hi')\n```\nprint('bye')"
        section = format_bundle_file_section(
            relative_path="src/main.py",
            path="C:/proj/src/main.py",
            size=20,
            content=content,
        )
        # CommonMark: fence must be longer than any backtick run in content.
        wrapped = "````python\nprint('hi')\n```\nprint('bye')\n````"
        assert wrapped in section
        inner = section.find("\n```\n")
        closing = section.rfind("\n````")
        assert inner != -1
        assert closing > inner
        # Following section header stays after the longer closing fence.
        next_file = format_bundle_file_section(
            relative_path="other.py",
            path="C:/proj/other.py",
            size=1,
            content="x = 1",
        )
        bundle = section + next_file
        assert bundle.find("## FILE: other.py") > closing

    def test_relative_path_newline_does_not_inject_second_file_heading(self) -> None:
        section = format_bundle_file_section(
            relative_path="src/main.py\n## FILE: injected",
            path="C:/proj/src/main.py",
            size=1,
            content="print('hi')",
        )
        file_lines = [
            line for line in section.splitlines() if line.startswith("## FILE:")
        ]
        assert len(file_lines) == 1
        header = file_lines[0]
        assert "\n" not in header
        assert "src/main.py" in header
        assert "## FILE: injected" not in section.splitlines()

    def test_relative_path_nul_is_removed_from_file_header(self) -> None:
        section = format_bundle_file_section(
            relative_path="src/mai\x00n.py",
            path="C:/proj/src/main.py",
            size=1,
            content="x",
        )
        file_lines = [
            line for line in section.splitlines() if line.startswith("## FILE:")
        ]
        assert len(file_lines) == 1
        assert "\x00" not in file_lines[0]

    def test_relative_path_del_is_removed_from_file_header(self) -> None:
        section = format_bundle_file_section(
            relative_path="src/main.py\x7f",
            path="C:/proj/src/main.py",
            size=1,
            content="x",
        )
        file_lines = [
            line for line in section.splitlines() if line.startswith("## FILE:")
        ]
        assert len(file_lines) == 1
        assert "\x7f" not in file_lines[0]

    def test_path_newline_keeps_path_header_on_one_line(self) -> None:
        section = format_bundle_file_section(
            relative_path="foo.py",
            path="C:\\proj\\foo\nbar",
            size=1,
            content="x",
        )
        path_lines = [
            line for line in section.splitlines() if line.startswith("## Path:")
        ]
        assert len(path_lines) == 1
        assert "\n" not in path_lines[0]
        assert "foo" in path_lines[0]
        assert "bar" in path_lines[0]


class TestApiStatusIsConnected:
    """Pure helper: badge text → connected, matching ``is_api_connected``."""

    def test_connesso_is_connected(self) -> None:
        assert api_status_is_connected("Connesso") is True

    def test_non_connesso_is_not_connected(self) -> None:
        assert api_status_is_connected("Non connesso") is False

    def test_empty_is_not_connected(self) -> None:
        assert api_status_is_connected("") is False

    def test_success_badge_substring_is_connected(self) -> None:
        # Live badge: "● Connesso (N modelli)" — "Connesso" is a substring.
        assert api_status_is_connected("\u25CF Connesso (5 modelli)") is True

    def test_idle_badge_substring_is_not_connected(self) -> None:
        # Idle badge: "● Non connesso" — lowercase "connesso" does not match.
        assert api_status_is_connected("\u25CF Non connesso") is False

    def test_error_badge_is_not_connected(self) -> None:
        assert api_status_is_connected("\u25CF Errore") is False

    def test_lowercase_connesso_is_not_connected(self) -> None:
        assert api_status_is_connected("connesso") is False

    def test_connesso_with_extra_whitespace_is_connected(self) -> None:
        assert api_status_is_connected("  Connesso  ") is True


class TestApiKeyIsUsable:
    """Pure helper: reject blank / C0 API keys before configure()."""

    @pytest.mark.parametrize(
        "key",
        [
            "",
            "   ",
            "\x00",
            "\nAIza",
            None,
            123,
            "AIza\tSyDummy",
            "AIza\nSyDummy",
        ],
    )
    def test_blank_c0_and_non_str_are_not_usable(self, key: object) -> None:
        assert api_key_is_usable(key) is False

    def test_printable_key_is_usable(self) -> None:
        assert api_key_is_usable("AIzaSyDummyKeyValue") is True

    def test_del_inside_key_is_not_usable(self) -> None:
        assert api_key_is_usable("AIza\x7fSyDummy") is False


class TestProjectPathIsUsable:
    """Pure helper: reject blank / C0 scan paths before Path.is_dir() / scan."""

    @pytest.mark.parametrize(
        "path",
        [
            "",
            "   ",
            "C:\\proj\\foo\nbar",
            "C:\\proj\x00",
            "C:\\proj\\foo\tbar",
            None,
            123,
        ],
    )
    def test_blank_c0_and_non_str_are_not_usable(self, path: object) -> None:
        assert project_path_is_usable(path) is False

    def test_normal_windows_path_is_usable(self) -> None:
        assert project_path_is_usable("C:\\Users\\gianc\\proj") is True

    def test_del_inside_path_is_not_usable(self) -> None:
        assert project_path_is_usable("C:\\proj\x7ffoo") is False

    def test_start_scan_rejects_unusable_path_before_is_dir(self) -> None:
        source = inspect.getsource(SetupTab._start_scan)
        helper_at = source.find("project_path_is_usable")
        is_dir_at = source.find("Path(path).is_dir()")
        assert helper_at != -1
        assert is_dir_at != -1
        assert helper_at < is_dir_at
        assert "Seleziona una cartella valida" in source

    def test_start_scan_does_not_use_exists_as_directory_gate(self) -> None:
        source = inspect.getsource(SetupTab._start_scan)
        assert "Path(path).is_dir()" in source
        assert "Path(path).exists()" not in source
        assert "Seleziona una cartella valida" in source


class TestShutdownScanResources:
    """Tk-free helper: cancel in-flight scan, then shut the executor."""

    def test_calls_scanner_cancel(self) -> None:
        scanner = MagicMock()
        executor = MagicMock()

        shutdown_scan_resources(scanner, executor)

        scanner.cancel.assert_called_once_with()

    def test_shuts_executor_without_waiting(self) -> None:
        scanner = MagicMock()
        executor = MagicMock()

        shutdown_scan_resources(scanner, executor)

        executor.shutdown.assert_called_once_with(wait=False, cancel_futures=True)

    def test_missing_cancel_still_shuts_executor(self) -> None:
        scanner = SimpleNamespace()
        executor = MagicMock()

        shutdown_scan_resources(scanner, executor)

        executor.shutdown.assert_called_once_with(wait=False, cancel_futures=True)

    def test_cancel_error_still_shuts_executor(self) -> None:
        scanner = MagicMock()
        scanner.cancel.side_effect = RuntimeError("cancel failed")
        executor = MagicMock()

        shutdown_scan_resources(scanner, executor)

        executor.shutdown.assert_called_once_with(wait=False, cancel_futures=True)
