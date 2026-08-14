# -*- coding: utf-8 -*-
"""Tests for PreviewTab helpers (no Tk window)."""

from __future__ import annotations

from pathlib import Path

from ai_context_studio.ui.preview_tab import (
    build_mermaid_preview_html,
    ensure_docs_directory,
    extract_mermaid_blocks,
)
from ai_context_studio.ui.visualizer_tab import MERMAID_CDN_URL


class TestExtractMermaidBlocks:
    def test_empty_documents_returns_empty_list(self) -> None:
        assert extract_mermaid_blocks({}) == []

    def test_no_mermaid_blocks_returns_empty_list(self) -> None:
        documents = {
            "README.md": "# Hello\n\n```python\nprint(1)\n```\n",
            "NOTES.md": "plain text, no fences",
        }
        assert extract_mermaid_blocks(documents) == []

    def test_one_block_returns_filename_and_body(self) -> None:
        documents = {
            "AI_ARCHITECTURE.md": (
                "intro\n```mermaid\ngraph TD\n    A --> B\n```\noutro"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("AI_ARCHITECTURE.md", "graph TD\n    A --> B")
        ]

    def test_multiple_files_preserve_order_and_skip_empty(self) -> None:
        documents = {
            "a.md": "```mermaid\ngraph TD\n    A --> B\n```",
            "b.md": "no diagrams here",
            "c.md": (
                "```mermaid\nsequenceDiagram\n    A->>B: hi\n```\n"
                "```mermaid\nclassDiagram\n    A -- B\n```"
            ),
        }
        assert extract_mermaid_blocks(documents) == [
            ("a.md", "graph TD\n    A --> B"),
            ("c.md", "sequenceDiagram\n    A->>B: hi"),
            ("c.md", "classDiagram\n    A -- B"),
        ]

    def test_strips_whitespace_from_diagram_body(self) -> None:
        documents = {
            "doc.md": "```mermaid\n\n  graph TD\n    A --> B\n\n```"
        }
        assert extract_mermaid_blocks(documents) == [
            ("doc.md", "graph TD\n    A --> B")
        ]

    def test_two_blocks_in_one_file_unclosed_fence_ignored(self) -> None:
        documents = {
            "doc.md": (
                "```mermaid\ngraph TD\n    A --> B\n```\n"
                "```mermaid\nsequenceDiagram\n    A->>B: hi\n```\n"
                "```mermaid\nclassDiagram\n    A -- B\n"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("doc.md", "graph TD\n    A --> B"),
            ("doc.md", "sequenceDiagram\n    A->>B: hi"),
        ]

    def test_title_case_mermaid_fence_extracted(self) -> None:
        documents = {
            "AI_ARCHITECTURE.md": (
                "intro\n```Mermaid\ngraph TD\n    A --> B\n```\noutro"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("AI_ARCHITECTURE.md", "graph TD\n    A --> B")
        ]

    def test_uppercase_mermaid_fence_extracted(self) -> None:
        documents = {
            "AI_ARCHITECTURE.md": (
                "intro\n```MERMAID\ngraph TD\n    A --> B\n```\noutro"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("AI_ARCHITECTURE.md", "graph TD\n    A --> B")
        ]

    def test_mixed_case_unclosed_ignored_python_still_ignored(self) -> None:
        documents = {
            "doc.md": (
                "```python\nprint(1)\n```\n"
                "```Mermaid\ngraph TD\n    A --> B\n```\n"
                "```MERMAID\nclassDiagram\n    A -- B\n"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("doc.md", "graph TD\n    A --> B"),
        ]

    def test_space_between_backticks_and_mermaid_extracted(self) -> None:
        documents = {
            "AI_ARCHITECTURE.md": (
                "intro\n``` mermaid\ngraph TD\n    A --> B\n```\noutro"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("AI_ARCHITECTURE.md", "graph TD\n    A --> B")
        ]

    def test_multiple_spaces_between_backticks_and_mermaid_extracted(self) -> None:
        documents = {
            "AI_ARCHITECTURE.md": (
                "intro\n```  mermaid\ngraph TD\n    A --> B\n```\noutro"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("AI_ARCHITECTURE.md", "graph TD\n    A --> B")
        ]

    def test_notmermaid_info_string_not_extracted(self) -> None:
        documents = {
            "doc.md": "```notmermaid\ngraph TD\n    A --> B\n```\n"
        }
        assert extract_mermaid_blocks(documents) == []

    def test_tilde_mermaid_fence_extracted(self) -> None:
        documents = {
            "AI_ARCHITECTURE.md": (
                "intro\n~~~mermaid\ngraph TD\n    A --> B\n~~~\noutro"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("AI_ARCHITECTURE.md", "graph TD\n    A --> B")
        ]

    def test_space_between_tildes_and_mermaid_extracted(self) -> None:
        documents = {
            "AI_ARCHITECTURE.md": (
                "intro\n~~~ mermaid\ngraph TD\n    A --> B\n~~~\noutro"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("AI_ARCHITECTURE.md", "graph TD\n    A --> B")
        ]

    def test_tilde_python_fence_ignored(self) -> None:
        documents = {
            "doc.md": "~~~python\nprint(1)\n~~~\n"
        }
        assert extract_mermaid_blocks(documents) == []

    def test_unclosed_tilde_mermaid_ignored(self) -> None:
        documents = {
            "doc.md": (
                "~~~mermaid\ngraph TD\n    A --> B\n~~~\n"
                "~~~mermaid\nclassDiagram\n    A -- B\n"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("doc.md", "graph TD\n    A --> B"),
        ]

    def test_mixed_backtick_and_tilde_mermaid_in_order(self) -> None:
        documents = {
            "doc.md": (
                "```mermaid\ngraph TD\n    A --> B\n```\n"
                "~~~mermaid\nsequenceDiagram\n    A->>B: hi\n~~~\n"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("doc.md", "graph TD\n    A --> B"),
            ("doc.md", "sequenceDiagram\n    A->>B: hi"),
        ]

    def test_empty_backtick_mermaid_fence_skipped(self) -> None:
        documents = {"doc.md": "```mermaid\n\n```"}
        assert extract_mermaid_blocks(documents) == []

    def test_empty_tilde_mermaid_fence_skipped(self) -> None:
        documents = {"doc.md": "~~~mermaid\n  \n~~~"}
        assert extract_mermaid_blocks(documents) == []

    def test_empty_fence_skipped_real_diagram_kept(self) -> None:
        documents = {
            "doc.md": (
                "```mermaid\n\n```\n"
                "```mermaid\ngraph TD\n    A --> B\n```"
            )
        }
        assert extract_mermaid_blocks(documents) == [
            ("doc.md", "graph TD\n    A --> B"),
        ]


class TestBuildMermaidPreviewHtml:
    def test_escapes_filename_and_script_payload(self) -> None:
        html = build_mermaid_preview_html(
            [
                (
                    '<script>alert(1)</script>.md',
                    'graph TD\n    A["</pre><script>alert(1)</script>"]',
                )
            ]
        )
        assert "<script>alert(1)</script>.md" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;.md" in html
        assert "</pre><script>alert(1)</script>" not in html

    def test_pins_mermaid_cdn_and_strict_security(self) -> None:
        html = build_mermaid_preview_html([("AI_ARCHITECTURE.md", "graph TD\n    A --> B")])
        assert MERMAID_CDN_URL in html
        assert "cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js" not in html
        assert "securityLevel: 'strict'" in html
        assert "securityLevel: 'loose'" not in html
        assert "htmlLabels: false" in html
        assert "integrity=" in html

    def test_html_includes_mermaid_initialize(self) -> None:
        html = build_mermaid_preview_html([("AI_ARCHITECTURE.md", "graph TD\n    A --> B")])
        assert "mermaid.initialize" in html

    def test_html_includes_pinned_mermaid_cdn_version(self) -> None:
        html = build_mermaid_preview_html([("AI_ARCHITECTURE.md", "graph TD\n    A --> B")])
        assert "mermaid@10.9.3" in html

    def test_strips_style_and_classdef_directives(self) -> None:
        html = build_mermaid_preview_html(
            [
                (
                    "AI_ARCHITECTURE.md",
                    (
                        "graph TD\n"
                        "    A --> B\n"
                        "    style A fill:#fff\n"
                        "    classDef foo fill:#f9f\n"
                    ),
                )
            ]
        )
        assert "style A fill:#fff" not in html
        assert "classDef foo fill:#f9f" not in html
        assert "graph TD" in html

    def test_sanitizes_before_escaping_script_breakout(self) -> None:
        html = build_mermaid_preview_html(
            [
                (
                    "doc.md",
                    'graph TD\n    A["</pre><script>alert(1)</script>"]',
                )
            ]
        )
        assert "</pre><script>alert(1)</script>" not in html
        assert "&lt;/pre&gt;" in html
        assert "&lt;script&gt;" in html

    def test_filename_newline_flattened_and_script_escaped(self) -> None:
        html = build_mermaid_preview_html(
            [
                (
                    "AI_ARCHITECTURE.md\n<script>alert(1)</script>",
                    "graph TD\n    A --> B",
                )
            ]
        )
        start = html.index("<h3>") + len("<h3>")
        end = html.index("</h3>", start)
        heading = html[start:end]
        assert "\n" not in heading
        assert "<script>" not in heading
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in heading
        assert "AI_ARCHITECTURE.md" in heading

    def test_filename_nul_stripped_from_html(self) -> None:
        html = build_mermaid_preview_html(
            [("AI_ARCH\x00.md", "graph TD\n    A --> B")]
        )
        assert "\x00" not in html
        assert "AI_ARCH.md" in html

    def test_filename_del_stripped_from_html(self) -> None:
        html = build_mermaid_preview_html(
            [("AI_ARCHITECTURE.md\x7f", "graph TD\n    A --> B")]
        )
        assert "\x7f" not in html
        assert "AI_ARCHITECTURE.md" in html



class TestEnsureDocsDirectory:
    def test_creates_directory_and_returns_none(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        assert ensure_docs_directory(docs_dir) is None
        assert docs_dir.is_dir()

    def test_existing_directory_returns_none(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        assert ensure_docs_directory(docs_dir) is None
        assert docs_dir.is_dir()

    def test_path_is_file_returns_error_without_raising(
        self, tmp_path: Path
    ) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.write_text("not a directory", encoding="utf-8")
        result = ensure_docs_directory(docs_dir)
        assert isinstance(result, str)
        assert "docs" in result
        assert "cartella" in result.lower()
        assert docs_dir.is_file()

    def test_missing_parent_still_creates(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "nested" / "project" / "docs"
        assert ensure_docs_directory(docs_dir) is None
        assert docs_dir.is_dir()
