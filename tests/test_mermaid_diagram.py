# -*- coding: utf-8 -*-
"""Tests for MermaidDiagram type detection (no Tk / tkinterweb widgets)."""

from __future__ import annotations

import tkinter as tk

from ai_context_studio.ui.visualizer_tab import (
    MermaidDiagram,
    iter_mermaid_fence_bodies,
)


class TestMermaidDiagramTypeDetection:
    """First-line diagram type labels from MermaidDiagram (no GUI)."""

    def test_flowchart_first_line(self) -> None:
        diagram = MermaidDiagram(
            "flowchart TD\n    A --> B\n",
            "doc.md",
            1,
        )
        assert diagram.diagram_type == "Flowchart"

    def test_sequence_diagram_first_line(self) -> None:
        diagram = MermaidDiagram(
            "sequenceDiagram\n    A->>B: hello\n",
            "doc.md",
            1,
        )
        assert diagram.diagram_type == "Sequence"

    def test_unknown_first_line(self) -> None:
        diagram = MermaidDiagram(
            "unknownType\n    A --> B\n",
            "doc.md",
            1,
        )
        assert diagram.diagram_type == "Diagram"

    def test_construction_does_not_create_tk_root(self) -> None:
        before = tk._default_root
        MermaidDiagram("flowchart TD\n    A --> B\n", "doc.md", 1)
        assert tk._default_root is before


class TestIterMermaidFenceBodies:
    """Case-insensitive ```mermaid / ~~~mermaid fence extraction (no Tk)."""

    _BODY = "graph TD\n    A --> B"

    def test_lowercase_mermaid_yields_body(self) -> None:
        bodies = iter_mermaid_fence_bodies(f"```mermaid\n{self._BODY}```")
        assert bodies == [self._BODY]

    def test_spaced_info_string_yields_body(self) -> None:
        """CommonMark allows spaces between backticks and the info string."""
        bodies = iter_mermaid_fence_bodies("``` mermaid\ngraph TD\n    A --> B\n```")
        assert bodies == [self._BODY]

    def test_titlecase_mermaid_yields_body(self) -> None:
        bodies = iter_mermaid_fence_bodies(f"```Mermaid\n{self._BODY}```")
        assert bodies == [self._BODY]

    def test_uppercase_mermaid_yields_body(self) -> None:
        bodies = iter_mermaid_fence_bodies(f"```MERMAID\n{self._BODY}```")
        assert bodies == [self._BODY]

    def test_python_fence_ignored(self) -> None:
        bodies = iter_mermaid_fence_bodies("```python\nprint('hi')\n```")
        assert bodies == []

    def test_unclosed_fence_ignored(self) -> None:
        bodies = iter_mermaid_fence_bodies(f"```mermaid\n{self._BODY}")
        assert bodies == []

    def test_helper_does_not_create_tk_root(self) -> None:
        before = tk._default_root
        iter_mermaid_fence_bodies(f"```mermaid\n{self._BODY}```")
        assert tk._default_root is before

    def test_tilde_mermaid_yields_body(self) -> None:
        bodies = iter_mermaid_fence_bodies(f"~~~mermaid\n{self._BODY}~~~")
        assert bodies == [self._BODY]

    def test_spaced_tilde_info_string_yields_body(self) -> None:
        """CommonMark allows spaces between tildes and the info string."""
        bodies = iter_mermaid_fence_bodies(f"~~~ mermaid\n{self._BODY}~~~")
        assert bodies == [self._BODY]

    def test_tilde_python_fence_ignored(self) -> None:
        bodies = iter_mermaid_fence_bodies("~~~python\nprint('hi')\n~~~")
        assert bodies == []

    def test_unclosed_tilde_mermaid_ignored(self) -> None:
        bodies = iter_mermaid_fence_bodies(f"~~~mermaid\n{self._BODY}")
        assert bodies == []

    def test_backtick_mermaid_still_works(self) -> None:
        bodies = iter_mermaid_fence_bodies(f"```mermaid\n{self._BODY}```")
        assert bodies == [self._BODY]

    def test_mixed_backtick_and_tilde_yields_both_in_order(self) -> None:
        tilde_body = "graph LR\n    C --> D"
        content = (
            f"```mermaid\n{self._BODY}```\n\n"
            f"~~~mermaid\n{tilde_body}~~~"
        )
        bodies = iter_mermaid_fence_bodies(content)
        assert bodies == [self._BODY, tilde_body]

    def test_empty_backtick_fence_skipped(self) -> None:
        bodies = iter_mermaid_fence_bodies("```mermaid\n\n```")
        assert bodies == []

    def test_whitespace_only_tilde_fence_skipped(self) -> None:
        bodies = iter_mermaid_fence_bodies("~~~mermaid\n  \n~~~")
        assert bodies == []

    def test_empty_fence_plus_real_body_yields_only_stripped_real(self) -> None:
        content = "```mermaid\n\n```\n\n```mermaid\n  graph TD\n    A --> B  \n```"
        bodies = iter_mermaid_fence_bodies(content)
        assert bodies == ["graph TD\n    A --> B"]
