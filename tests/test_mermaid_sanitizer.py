# -*- coding: utf-8 -*-
"""
Tests for MermaidSanitizer (no GUI required).
"""

from __future__ import annotations

from ai_context_studio.ui.visualizer_tab import MermaidSanitizer


class TestMermaidSanitizerSanitize:
    """Unit tests for MermaidSanitizer.sanitize."""

    def test_empty_input(self) -> None:
        """Empty or whitespace-only input should be returned unchanged."""
        assert MermaidSanitizer.sanitize("") == ""
        assert MermaidSanitizer.sanitize("   ") == "   "
        assert MermaidSanitizer.sanitize("\n") == "\n"

    def test_unquoted_special_chars_in_labels(self) -> None:
        """Unquoted special characters in node labels should be quoted."""
        code = (
            "graph TD\n"
            "    A[Inizializzazione?] --> B{Configurazione: API Key?}\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert 'A["Inizializzazione?"]' in result
        assert 'B{"Configurazione: API Key?"}' in result
        assert "A[Inizializzazione?]" not in result

    def test_style_classdef_linkstyle_stripping(self) -> None:
        """style, classDef, linkStyle, and class directives should be removed."""
        code = (
            "graph TD\n"
            "    A --> B\n"
            "    style A fill:#fff,stroke:#333\n"
            "    classDef foo fill:#f9f,stroke:#333\n"
            "    linkStyle 0 stroke:#ff3,stroke-width:2px\n"
            "    class A foo\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "graph TD" in result
        assert "A --> B" in result
        assert "style A" not in result
        assert "classDef" not in result
        assert "linkStyle" not in result
        assert "class A foo" not in result

    def test_sequence_diagram_messages(self) -> None:
        """Sequence messages should drop quotes and normalize parentheses."""
        code = (
            "sequenceDiagram\n"
            '    C-->>A: GenerationResult ("success=True")\n'
            "    A->>B: Message with (parentheses)\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "sequenceDiagram" in result
        assert "C-->>A: GenerationResult  - success=True" in result
        assert "A->>B: Message with [parentheses]" in result
        assert '("success=True")' not in result
        assert "(parentheses)" not in result

    def test_parenthesized_identifier_does_not_crash(self) -> None:
        code = 'graph TD\n    A["</pre><script>alert(1)</script>"]\n'
        result = MermaidSanitizer.sanitize(code)
        assert "graph TD" in result
        assert "A[" in result

    def test_click_href_url_is_stripped(self) -> None:
        """click Node \"url\" must be dropped; graph nodes remain."""
        code = (
            "graph TD\n"
            "    A[Start] --> B[End]\n"
            '    click A "https://evil.example"\n'
        )
        result = MermaidSanitizer.sanitize(code)

        assert "graph TD" in result
        assert "A[Start]" in result or 'A["Start"]' in result
        assert "B[End]" in result or 'B["End"]' in result
        assert "-->" in result
        assert "click" not in result.lower()
        assert "https://evil.example" not in result

    def test_click_javascript_is_stripped(self) -> None:
        """click Node javascript:... must be dropped."""
        code = (
            "graph TD\n"
            "    A --> B\n"
            "    click A javascript:alert(1)\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "graph TD" in result
        assert "A --> B" in result
        assert "click" not in result.lower()
        assert "javascript:" not in result.lower()
        assert "alert(1)" not in result

    def test_click_call_callback_is_stripped(self) -> None:
        """click Node call fn() must be dropped."""
        code = (
            "graph TD\n"
            "    A --> B\n"
            "    click A call someFn()\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "graph TD" in result
        assert "A --> B" in result
        assert "click" not in result.lower()
        assert "someFn" not in result

    def test_click_is_stripped_case_insensitive(self) -> None:
        """CLICK directives must be stripped regardless of case."""
        code = (
            "graph TD\n"
            "    A --> B\n"
            "    CLICK A href\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "graph TD" in result
        assert "A --> B" in result
        assert "click" not in result.lower()
        assert "CLICK" not in result
        assert "href" not in result.lower()

    def test_sequence_diagram_click_is_stripped(self) -> None:
        """Sequence diagrams must also drop click lines (before sequence branch)."""
        code = (
            "sequenceDiagram\n"
            "    A->>B: hello\n"
            '    click A "https://evil.example"\n'
        )
        result = MermaidSanitizer.sanitize(code)

        assert "sequenceDiagram" in result
        assert "A->>B: hello" in result
        assert "click" not in result.lower()
        assert "https://evil.example" not in result

    def test_call_directive_is_stripped(self) -> None:
        """Standalone mermaid call lines invoke JS and must be dropped."""
        code = (
            "flowchart TD\n"
            "    A[Call store] --> B[End]\n"
            "    call callbackName\n"
            "      call foo\n"
            '    click A "https://evil"\n'
            "    %%{init: {'securityLevel': 'loose'}}%%\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "flowchart TD" in result
        assert "Call store" in result
        assert "A[Call store]" in result or 'A["Call store"]' in result
        assert "callbackName" not in result
        assert "call foo" not in result.lower()
        assert "click" not in result.lower()
        assert "https://evil" not in result
        assert "%%{init:" not in result
        assert "securityLevel" not in result
        assert "loose" not in result

    def test_indented_call_directive_is_stripped(self) -> None:
        """Indented call directives must be dropped; Call in labels must remain."""
        code = (
            "flowchart TD\n"
            "    A[Call store] --> B\n"
            "  call foo\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "flowchart TD" in result
        assert "Call store" in result
        assert "A[Call store]" in result or 'A["Call store"]' in result
        assert "call foo" not in result.lower()
        assert not any(
            line.strip().lower().startswith("call ")
            for line in result.splitlines()
        )

    def test_init_frontmatter_on_first_line_is_stripped(self) -> None:
        """%%{init: ...}%% must not override mermaid.initialize securityLevel."""
        code = (
            "%%{init: {'securityLevel': 'loose'}}%%\n"
            "graph TD\n"
            "    A[Start] --> B[End]\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "%%{init:" not in result
        assert "securityLevel" not in result
        assert "loose" not in result
        assert "graph TD" in result
        assert "A[Start]" in result or 'A["Start"]' in result
        assert "B[End]" in result or 'B["End"]' in result

    def test_config_frontmatter_is_stripped(self) -> None:
        """%%{config: ...}%% directives must be dropped."""
        code = (
            "graph TD\n"
            "    A --> B\n"
            "    %%{config: {'theme': 'dark', 'flowchart': {'htmlLabels': true}}}%%\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "%%{config:" not in result
        assert "htmlLabels" not in result
        assert "graph TD" in result
        assert "A --> B" in result

    def test_init_frontmatter_on_later_line_is_stripped(self) -> None:
        """Init directives are not limited to the first line."""
        code = (
            "graph TD\n"
            "    A --> B\n"
            "    %%{init: {'htmlLabels': true}}%%\n"
            "    B --> C\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "%%{init:" not in result
        assert "htmlLabels" not in result
        assert "graph TD" in result
        assert "A --> B" in result
        assert "B --> C" in result

    def test_harmless_percent_comments_are_kept(self) -> None:
        """Plain %% comments must remain; only init/config frontmatter is stripped."""
        code = (
            "graph TD\n"
            "    %% this is a comment\n"
            "    A --> B\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "%% this is a comment" in result
        assert "graph TD" in result
        assert "A --> B" in result

    def test_multiline_init_directive_is_stripped(self) -> None:
        """Multiline %%{init: ...}%% must not override mermaid.initialize securityLevel."""
        code = (
            "%%{\n"
            "  init: {\n"
            "    'securityLevel': 'loose',\n"
            "    'htmlLabels': true,\n"
            "    'theme': 'dark'\n"
            "  }\n"
            "}%%\n"
            "graph TD\n"
            "    A --> B\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "%%{init" not in result
        assert "securityLevel" not in result
        assert "loose" not in result
        assert "htmlLabels" not in result
        assert "graph TD" in result
        assert "A --> B" in result

    def test_multiline_config_directive_is_stripped(self) -> None:
        """Multiline %%{config: ...}%% directives must be dropped; diagram lines remain."""
        code = (
            "%%{\n"
            "  config: {\n"
            "    'securityLevel': 'loose',\n"
            "    'theme': 'dark'\n"
            "  }\n"
            "}%%\n"
            "graph TD\n"
            "    A --> B\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "%%{config" not in result
        assert "securityLevel" not in result
        assert "loose" not in result
        assert "graph TD" in result
        assert "A --> B" in result

    def test_leading_yaml_frontmatter_is_stripped(self) -> None:
        """Leading YAML frontmatter must not override mermaid.initialize securityLevel."""
        code = (
            "---\n"
            "config:\n"
            "  securityLevel: 'loose'\n"
            "  theme: dark\n"
            "---\n"
            "flowchart TD\n"
            "    A --> B\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "securityLevel" not in result
        assert "loose" not in result
        assert "flowchart TD" in result
        assert "A --> B" in result

    def test_yaml_frontmatter_does_not_strip_edge_dashes(self) -> None:
        """A --- B edges in the diagram body must not be treated as frontmatter."""
        code = (
            "graph TD\n"
            "    A --- B\n"
        )
        result = MermaidSanitizer.sanitize(code)

        assert "graph TD" in result
        assert "A --- B" in result


class TestMermaidSanitizerEscapeForHtml:
    """HTML injection defenses for MermaidSanitizer.escape_for_html."""

    def test_script_breakout_is_html_escaped(self) -> None:
        """Sanitize then escape so a </pre><script> payload cannot break HTML."""
        code = 'graph TD\n    A["</pre><script>alert(1)</script>"]\n'
        result = MermaidSanitizer.escape_for_html(code)

        assert "<script>" not in result
        assert "</pre>" not in result
        assert "&lt;script&gt;" in result
        assert "&lt;/pre&gt;" in result
        assert "graph TD" in result

    def test_quotes_and_ampersands_are_escaped(self) -> None:
        """quote=True must neutralize attribute breakout and ampersands."""
        code = "graph TD\n    A[x & \"y\" 'z']\n"
        result = MermaidSanitizer.escape_for_html(code)

        assert "<" not in result or "&lt;" in result
        assert "&amp;" in result
        assert "&quot;" in result
        assert "&#x27;" in result
        assert '"' not in result
        assert "'" not in result

    def test_empty_input_passthrough(self) -> None:
        assert MermaidSanitizer.escape_for_html("") == ""
        assert MermaidSanitizer.escape_for_html("   ") == "   "

    def test_sanitizes_before_escaping(self) -> None:
        """Style directives are stripped before the remaining code is escaped."""
        code = (
            "graph TD\n"
            "    A --> B\n"
            "    style A fill:#fff,stroke:#333\n"
        )
        result = MermaidSanitizer.escape_for_html(code)

        assert "style A" not in result
        assert "graph TD" in result
        assert "A --&gt; B" in result
