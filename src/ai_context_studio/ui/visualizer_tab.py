# -*- coding: utf-8 -*-
"""
Mermaid Visualizer Tab for AI Context Studio.

Professional diagram visualization with zoom, pan, and export capabilities.
"""

from __future__ import annotations

import base64
import logging
import re
import tempfile
import threading
import webbrowser
from pathlib import Path
from typing import Any, Callable, Optional

import customtkinter as ctk

from ..constants import COLORS, FONTS

logger = logging.getLogger(__name__)

# Type aliases
StatusCallback = Callable[[str, str], None]

# Try to import tkinterweb for embedded browser
try:
    from tkinterweb import HtmlFrame
    TKINTERWEB_AVAILABLE = True
except ImportError:
    TKINTERWEB_AVAILABLE = False
    logger.warning("tkinterweb not available, using fallback renderer")

# Try to import webview for advanced features
try:
    import webview
    WEBVIEW_AVAILABLE = True
except ImportError:
    WEBVIEW_AVAILABLE = False
    logger.warning("pywebview not available, export features limited")


class MermaidSanitizer:
    """
    Robust sanitizer for AI-generated Mermaid code.

    Fixes common syntax issues:
    - Unquoted special characters in node labels
    - Subgraph naming problems
    - Edge label formatting
    - Style/linkStyle directive removal (causes parsing errors)
    - Sequence diagram message formatting
    - Various Mermaid syntax edge cases
    """

    # Characters that require quoting in node labels
    SPECIAL_CHARS = r'[;:?!@#$%^&*()+=<>|\\\'\"`,/~]'

    # Problematic style patterns to remove
    STYLE_PATTERNS = [
        r'^\s*style\s+\w+\s+.*$',      # style A fill:#fff...
        r'^\s*linkStyle\s+.*$',         # linkStyle 0 stroke:...
        r'^\s*classDef\s+.*$',          # classDef className...
        r'^\s*class\s+\w+\s+\w+\s*$',   # class A className
    ]

    @classmethod
    def sanitize(cls, code: str) -> str:
        """
        Sanitize Mermaid code to fix common AI-generated issues.

        Args:
            code: Raw Mermaid code from AI generation

        Returns:
            Sanitized Mermaid code that should render correctly
        """
        if not code or not code.strip():
            return code

        # Detect diagram type
        first_line = code.strip().split('\n')[0].lower()
        is_sequence = 'sequencediagram' in first_line.replace(' ', '')
        is_flowchart = any(x in first_line for x in ['graph', 'flowchart'])

        lines = code.split('\n')
        sanitized_lines = []
        in_subgraph = False

        for line in lines:
            # Skip style directives entirely (they cause parsing issues)
            if cls._is_style_line(line):
                continue

            if is_sequence:
                sanitized_line = cls._sanitize_sequence_line(line)
            else:
                sanitized_line = cls._sanitize_line(line, in_subgraph)
            sanitized_lines.append(sanitized_line)

            # Track subgraph state
            stripped = line.strip().lower()
            if stripped.startswith('subgraph'):
                in_subgraph = True
            elif stripped == 'end':
                in_subgraph = False

        return '\n'.join(sanitized_lines)

    @classmethod
    def _is_style_line(cls, line: str) -> bool:
        """Check if line is a style directive that should be removed."""
        stripped = line.strip()
        for pattern in cls.STYLE_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                return True
        return False

    @classmethod
    def _sanitize_sequence_line(cls, line: str) -> str:
        """
        Sanitize sequence diagram lines.

        Fixes issues like:
        - C-->>A: GenerationResult ("success=True")
        - Parentheses in message text
        """
        stripped = line.strip()
        if not stripped or stripped.startswith('%%'):
            return line

        # Fix sequence messages with problematic characters
        # Pattern: A->>B: Message with (parentheses)
        message_pattern = r'([\w]+)([-]+>>?|-->>?)([\w]+):\s*(.+)$'
        match = re.match(message_pattern, stripped)
        if match:
            sender = match.group(1)
            arrow = match.group(2)
            receiver = match.group(3)
            message = match.group(4)

            # Clean up message - remove or escape problematic chars
            message = message.replace('("', ' - ')
            message = message.replace('")', '')
            message = message.replace('(', '[')
            message = message.replace(')', ']')
            message = re.sub(r'["\']', '', message)

            indent = len(line) - len(line.lstrip())
            return ' ' * indent + f'{sender}{arrow}{receiver}: {message}'

        return line

    @classmethod
    def _sanitize_line(cls, line: str, in_subgraph: bool) -> str:
        """Sanitize a single line of flowchart/graph code."""
        stripped = line.strip()
        if not stripped or stripped.startswith('%%'):
            return line

        # Handle subgraph declarations
        if stripped.lower().startswith('subgraph'):
            return cls._sanitize_subgraph(line)

        # Uniformize node brackets - convert () to [] for consistency
        result = cls._uniformize_node_brackets(line)

        # Handle node definitions with labels
        if re.search(r'\[.*\]|\{.*\}|\(\(.*\)\)|\[\[.*\]\]', result):
            result = cls._sanitize_node_labels(result)

        # Handle edge labels
        if re.search(r'--.*--|-..-|==.*==|-->', result):
            result = cls._sanitize_edge_labels(result)

        return result

    @classmethod
    def _uniformize_node_brackets(cls, line: str) -> str:
        """
        Uniformize node brackets to use [] for standard nodes.

        Converts: A("Text with spaces") --> B
        To:       A["Text with spaces"] --> B

        Keeps {} for decision nodes and (()) for circles.
        """
        # Pattern to match single-paren nodes that should be []
        # But NOT decision nodes {} or special shapes (()) [[]]
        def replace_paren_node(match):
            before = match.group(1)
            content = match.group(2)
            after = match.group(3)

            # If content has special meaning (decision, etc), keep as is
            # Otherwise convert to square brackets
            return f'{before}["{content}"]{after}'

        # Match A("content") or A(content) but not A((content)) or A{content}
        result = re.sub(
            r'(\w+)\(([^()]+)\)(?!\))',
            replace_paren_node,
            line
        )

        return result

    @classmethod
    def _sanitize_subgraph(cls, line: str) -> str:
        """
        Sanitize subgraph declarations.

        Converts: subgraph Livello 1: Foundation
        To:       subgraph sg1["Livello 1: Foundation"]
        """
        match = re.match(r'^(\s*)subgraph\s+(.+)$', line, re.IGNORECASE)
        if not match:
            return line

        indent = match.group(1)
        name = match.group(2).strip()

        # If already in bracket format, sanitize the content
        bracket_match = re.match(r'(\w+)\s*\[(.+)\]$', name)
        if bracket_match:
            sub_id = bracket_match.group(1)
            sub_name = bracket_match.group(2).strip('"')
            return f'{indent}subgraph {sub_id}["{sub_name}"]'

        # Check if name has problematic characters or spaces
        if re.search(cls.SPECIAL_CHARS, name) or ' ' in name:
            # Generate a safe ID from the name
            safe_id = 'sg' + re.sub(r'[^a-zA-Z0-9]', '', name)[:8]
            if not safe_id or safe_id == 'sg':
                safe_id = 'subg'
            return f'{indent}subgraph {safe_id}["{name}"]'

        return line

    @classmethod
    def _sanitize_node_labels(cls, line: str) -> str:
        """
        Sanitize node labels with special characters.

        Converts: A[Inizializzazione?] --> B{Configurazione: API Key?};
        To:       A["Inizializzazione?"] --> B{"Configurazione: API Key?"}
        """
        result = line

        # Pattern for different bracket types
        bracket_patterns = [
            (r'\[([^\[\]"]+)\]', '[', ']'),       # Square brackets
            (r'\{([^\{\}"]+)\}', '{', '}'),       # Curly brackets (decisions)
            (r'\[\[([^\[\]"]+)\]\]', '[[', ']]'), # Double square
            (r'\(\(([^\(\)"]+)\)\)', '((', '))'), # Double parens (circles)
        ]

        for pattern, open_br, close_br in bracket_patterns:
            def replace_label(match, ob=open_br, cb=close_br):
                content = match.group(1)
                # Always quote if contains special chars or spaces
                if re.search(cls.SPECIAL_CHARS, content) or ' ' in content:
                    # Escape existing quotes
                    content = content.replace('"', "'")
                    return f'{ob}"{content}"{cb}'
                return match.group(0)

            result = re.sub(pattern, replace_label, result)

        # Remove trailing semicolons (common AI mistake)
        result = re.sub(r';\s*$', '', result)

        return result

    @classmethod
    def _sanitize_edge_labels(cls, line: str) -> str:
        """
        Sanitize edge labels.

        Converts: A -- Testo: con speciali --> B
        To:       A -->|"Testo: con speciali"| B
        """
        result = line

        # Handle |label| format - quote if needed
        def quote_pipe_label(match):
            label = match.group(1)
            if re.search(cls.SPECIAL_CHARS, label) and not label.startswith('"'):
                label = label.replace('"', "'")
                return f'|"{label}"|'
            return match.group(0)

        result = re.sub(r'\|([^|]+)\|', quote_pipe_label, result)

        # Handle -- label --> format (convert to pipe format)
        def convert_inline_label(match):
            prefix = match.group(1)
            label = match.group(2).strip()
            suffix = match.group(3)

            if label and not label.startswith('|'):
                label = label.replace('"', "'")
                return f'-->|"{label}"|'
            return match.group(0)

        result = re.sub(r'(--)\s*([^->|"\s][^->]+?)\s*(-->)', convert_inline_label, result)

        return result

    @classmethod
    def validate(cls, code: str) -> tuple[bool, str]:
        """
        Basic validation of Mermaid code structure.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not code or not code.strip():
            return False, "Codice vuoto"

        lines = [l.strip() for l in code.split('\n') if l.strip() and not l.strip().startswith('%%')]

        if not lines:
            return False, "Nessuna istruzione valida"

        # Check for valid diagram type
        first_line = lines[0].lower()
        valid_types = ['graph', 'flowchart', 'sequencediagram', 'classdiagram',
                       'statediagram', 'erdiagram', 'journey', 'gantt', 'pie',
                       'gitgraph', 'mindmap', 'timeline', 'quadrantchart', 'sankey']

        if not any(vt in first_line for vt in valid_types):
            return False, f"Tipo diagramma non riconosciuto: {first_line[:50]}"

        # Check bracket balance
        open_count = sum(code.count(c) for c in '[{(')
        close_count = sum(code.count(c) for c in ']})')
        if open_count != close_count:
            return False, f"Parentesi non bilanciate: {open_count} aperte, {close_count} chiuse"

        # Check subgraph/end balance
        subgraph_count = len(re.findall(r'\bsubgraph\b', code, re.IGNORECASE))
        end_count = len(re.findall(r'\bend\b', code, re.IGNORECASE))
        if subgraph_count != end_count:
            return False, f"Subgraph/end non bilanciati: {subgraph_count} subgraph, {end_count} end"

        return True, ""


class MermaidDiagram:
    """Represents a single Mermaid diagram."""

    def __init__(self, code: str, source_file: str, index: int):
        self.raw_code = code.strip()
        self.code = MermaidSanitizer.sanitize(self.raw_code)
        self.source_file = source_file
        self.index = index
        self.diagram_type = self._detect_type()
        self.is_valid, self.validation_error = MermaidSanitizer.validate(self.code)

    def _detect_type(self) -> str:
        """Detect the diagram type from code."""
        first_line = self.code.split('\n')[0].strip().lower()
        type_map = {
            'graph': 'Flowchart',
            'flowchart': 'Flowchart',
            'sequencediagram': 'Sequence',
            'classdiagram': 'Class',
            'statediagram': 'State',
            'erdiagram': 'ER',
            'journey': 'Journey',
            'gantt': 'Gantt',
            'pie': 'Pie Chart',
            'gitgraph': 'Git Graph',
            'mindmap': 'Mind Map',
            'timeline': 'Timeline',
            'quadrantchart': 'Quadrant',
            'sankey': 'Sankey',
        }
        for key, value in type_map.items():
            if key in first_line:
                return value
        return 'Diagram'


class VisualizerTab(ctk.CTkFrame):
    """
    Professional Mermaid diagram visualizer tab.

    Features:
    - Embedded HTML rendering with Mermaid.js
    - Zoom and pan controls
    - Export to PNG/SVG
    - Light/Dark theme support
    - Diagram list with quick navigation
    """

    def __init__(
        self,
        master: Any,
        on_status_update: StatusCallback,
        **kwargs: Any
    ) -> None:
        """Initialize the visualizer tab."""
        super().__init__(master, **kwargs)

        self._on_status_update = on_status_update
        self._diagrams: list[MermaidDiagram] = []
        self._current_diagram: Optional[MermaidDiagram] = None
        self._zoom_level: float = 1.0
        self._theme: str = "default"  # default, dark, forest, neutral
        self._temp_html_path: Optional[Path] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the tab UI."""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left sidebar - diagram list
        self._create_sidebar()

        # Main content - viewer
        self._create_viewer()

    def _create_sidebar(self) -> None:
        """Create the diagram list sidebar."""
        sidebar = ctk.CTkFrame(self, width=280, fg_color="#f8fafc")
        sidebar.grid(row=0, column=0, sticky="nsw", padx=(15, 0), pady=15)
        sidebar.grid_propagate(False)

        # Header
        header = ctk.CTkFrame(sidebar, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text="Diagrammi",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#1e293b"
        ).pack(side="left")

        self.diagram_count = ctk.CTkLabel(
            header,
            text="0",
            font=ctk.CTkFont(size=12),
            text_color=COLORS['text_muted'],
            fg_color=COLORS['primary'],
            corner_radius=10,
            width=30,
            height=24
        )
        self.diagram_count.pack(side="right")

        # Refresh button
        ctk.CTkButton(
            sidebar,
            text="Aggiorna da Documenti",
            font=ctk.CTkFont(size=11),
            fg_color=COLORS['primary'],
            hover_color=COLORS['primary_hover'],
            height=32,
            command=self._refresh_from_preview
        ).pack(fill="x", padx=15, pady=(0, 10))

        # Theme selector
        theme_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        theme_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(
            theme_frame,
            text="Tema:",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_muted']
        ).pack(side="left")

        self.theme_combo = ctk.CTkComboBox(
            theme_frame,
            values=["Default", "Dark", "Forest", "Neutral"],
            width=120,
            height=28,
            font=ctk.CTkFont(size=11),
            command=self._on_theme_change
        )
        self.theme_combo.pack(side="right")
        self.theme_combo.set("Default")

        # Diagram list
        ctk.CTkLabel(
            sidebar,
            text="Diagrammi Trovati:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#1e293b"
        ).pack(anchor="w", padx=15, pady=(10, 5))

        self.diagram_list = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent"
        )
        self.diagram_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Placeholder message
        self.no_diagrams_label = ctk.CTkLabel(
            self.diagram_list,
            text="Nessun diagramma.\n\nGenera documenti nella\ntab 'Generatore' poi\nclicca 'Aggiorna'.",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_muted'],
            justify="center"
        )
        self.no_diagrams_label.pack(pady=30)

    def _create_viewer(self) -> None:
        """Create the main diagram viewer."""
        viewer = ctk.CTkFrame(self, fg_color="white")
        viewer.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        viewer.grid_columnconfigure(0, weight=1)
        viewer.grid_rowconfigure(1, weight=1)

        # Toolbar
        self._create_toolbar(viewer)

        # Viewer area
        self._create_viewer_area(viewer)

        # Bottom info bar
        self._create_info_bar(viewer)

    def _create_toolbar(self, parent: ctk.CTkFrame) -> None:
        """Create the toolbar with controls."""
        toolbar = ctk.CTkFrame(parent, fg_color="#f1f5f9", height=50)
        toolbar.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        toolbar.grid_propagate(False)

        # Left side - zoom controls
        zoom_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        zoom_frame.pack(side="left", padx=15, pady=8)

        ctk.CTkButton(
            zoom_frame,
            text="-",
            width=32,
            height=32,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORS['slate'],
            command=self._zoom_out
        ).pack(side="left", padx=2)

        self.zoom_label = ctk.CTkLabel(
            zoom_frame,
            text="100%",
            font=ctk.CTkFont(size=12),
            width=50
        )
        self.zoom_label.pack(side="left", padx=5)

        ctk.CTkButton(
            zoom_frame,
            text="+",
            width=32,
            height=32,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORS['slate'],
            command=self._zoom_in
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            zoom_frame,
            text="Reset",
            width=50,
            height=32,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color=COLORS['primary'],
            hover_color="#e2e8f0",
            command=self._zoom_reset
        ).pack(side="left", padx=5)

        # Right side - action buttons
        actions_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions_frame.pack(side="right", padx=15, pady=8)

        ctk.CTkButton(
            actions_frame,
            text="Copia Codice",
            width=100,
            height=32,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS['slate'],
            command=self._copy_code
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            actions_frame,
            text="Esporta PNG",
            width=100,
            height=32,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS['indigo'],
            hover_color=COLORS['indigo_hover'],
            command=self._export_png
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            actions_frame,
            text="Esporta SVG",
            width=100,
            height=32,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS['teal'],
            hover_color=COLORS['teal_hover'],
            command=self._export_svg
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            actions_frame,
            text="Apri Browser",
            width=100,
            height=32,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS['purple'],
            hover_color=COLORS['purple_hover'],
            command=self._open_in_browser
        ).pack(side="left", padx=3)

    def _create_viewer_area(self, parent: ctk.CTkFrame) -> None:
        """Create the main viewer area."""
        viewer_container = ctk.CTkFrame(parent, fg_color="#f8fafc")
        viewer_container.grid(row=1, column=0, sticky="nsew", padx=1, pady=1)
        viewer_container.grid_columnconfigure(0, weight=1)
        viewer_container.grid_rowconfigure(0, weight=1)

        if TKINTERWEB_AVAILABLE:
            # Use embedded browser
            self.html_frame = HtmlFrame(viewer_container, messages_enabled=False)
            self.html_frame.grid(row=0, column=0, sticky="nsew")
            self._show_welcome_page()
        else:
            # Fallback to simple text display
            self.html_frame = None
            self.fallback_text = ctk.CTkTextbox(
                viewer_container,
                font=ctk.CTkFont(family="Consolas", size=12),
                wrap="word"
            )
            self.fallback_text.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            self.fallback_text.insert("1.0", "tkinterweb non disponibile.\n\nUsa 'Apri Browser' per visualizzare i diagrammi.")
            self.fallback_text.configure(state="disabled")

    def _create_info_bar(self, parent: ctk.CTkFrame) -> None:
        """Create the bottom info bar."""
        info_bar = ctk.CTkFrame(parent, fg_color="#f1f5f9", height=36)
        info_bar.grid(row=2, column=0, sticky="ew", padx=1, pady=1)
        info_bar.grid_propagate(False)

        self.info_label = ctk.CTkLabel(
            info_bar,
            text="Seleziona un diagramma dalla lista",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_muted']
        )
        self.info_label.pack(side="left", padx=15, pady=8)

        self.code_size_label = ctk.CTkLabel(
            info_bar,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_muted']
        )
        self.code_size_label.pack(side="right", padx=15, pady=8)

    def _show_welcome_page(self) -> None:
        """Show welcome page in the viewer."""
        if not TKINTERWEB_AVAILABLE or not self.html_frame:
            return

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
                }
                .container {
                    text-align: center;
                    padding: 40px;
                }
                h1 { color: #1e293b; font-size: 24px; margin-bottom: 10px; }
                p { color: #64748b; font-size: 14px; line-height: 1.6; }
                .icon { font-size: 64px; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">📊</div>
                <h1>Mermaid Visualizer</h1>
                <p>Seleziona un diagramma dalla lista a sinistra<br>
                oppure clicca "Aggiorna da Documenti" per<br>
                caricare i diagrammi dai documenti generati.</p>
            </div>
        </body>
        </html>
        """
        self.html_frame.load_html(html)

    def _generate_mermaid_html(self, diagram: MermaidDiagram) -> str:
        """Generate HTML page for a Mermaid diagram with error handling."""
        theme_map = {
            "Default": "default",
            "Dark": "dark",
            "Forest": "forest",
            "Neutral": "neutral"
        }
        theme = theme_map.get(self.theme_combo.get(), "default")
        is_dark = theme == "dark"

        # Escape the code for JavaScript embedding
        js_escaped_code = (diagram.code
            .replace('\\', '\\\\')
            .replace('`', '\\`')
            .replace('$', '\\$')
            .replace('</', '<\\/')
        )

        # HTML escaped for display in error fallback
        html_escaped_code = (diagram.code
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
        )

        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{
            width: 100%;
            height: 100%;
            overflow: auto;
            background: {"#1e293b" if is_dark else "#ffffff"};
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        #container {{
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100%;
            padding: 20px;
            transform-origin: center center;
            transform: scale({self._zoom_level});
        }}
        .mermaid {{
            background: transparent;
        }}
        .mermaid svg {{
            max-width: none !important;
        }}
        #error-container {{
            display: none;
            padding: 30px;
            max-width: 800px;
            margin: 20px auto;
        }}
        .error-box {{
            background: {"#2d1b1b" if is_dark else "#fef2f2"};
            border: 2px solid {"#7f1d1d" if is_dark else "#fecaca"};
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .error-title {{
            color: {"#fca5a5" if is_dark else "#dc2626"};
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .error-message {{
            color: {"#fca5a5" if is_dark else "#b91c1c"};
            font-size: 14px;
            margin-bottom: 15px;
        }}
        .code-fallback {{
            background: {"#0f172a" if is_dark else "#1e293b"};
            color: #e2e8f0;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 12px;
            white-space: pre-wrap;
            word-break: break-word;
        }}
        .help-text {{
            color: {"#94a3b8" if is_dark else "#64748b"};
            font-size: 13px;
            margin-top: 15px;
        }}
        .help-text a {{
            color: #3b82f6;
        }}
    </style>
</head>
<body>
    <div id="container">
        <pre class="mermaid" id="mermaid-diagram">
{diagram.code}
        </pre>
    </div>

    <div id="error-container">
        <div class="error-box">
            <div class="error-title">Errore nel rendering del diagramma</div>
            <div class="error-message" id="error-message"></div>
            <p class="help-text">
                Il diagramma contiene sintassi non valida per Mermaid.
                <a href="https://mermaid.js.org/syntax/flowchart.html" target="_blank">
                    Consulta la documentazione Mermaid
                </a>
            </p>
        </div>
        <h4 style="color: {"#e2e8f0" if is_dark else "#1e293b"}; margin-bottom: 10px;">
            Codice sorgente:
        </h4>
        <pre class="code-fallback">{html_escaped_code}</pre>
    </div>

    <script>
        mermaid.initialize({{
            startOnLoad: false,
            theme: '{theme}',
            securityLevel: 'loose',
            flowchart: {{
                useMaxWidth: false,
                htmlLabels: true,
                curve: 'basis'
            }},
            sequence: {{
                useMaxWidth: false
            }},
            logLevel: 'error'
        }});

        async function renderDiagram() {{
            const element = document.getElementById('mermaid-diagram');
            const container = document.getElementById('container');
            const errorContainer = document.getElementById('error-container');

            try {{
                const {{ svg }} = await mermaid.render('diagram-svg', element.textContent);
                element.innerHTML = svg;
            }} catch (error) {{
                console.error('Mermaid error:', error);
                container.style.display = 'none';
                errorContainer.style.display = 'block';
                document.getElementById('error-message').textContent =
                    error.message || 'Errore di sintassi nel codice Mermaid';
            }}
        }}

        renderDiagram();
    </script>
</body>
</html>'''

    def _refresh_from_preview(self) -> None:
        """Refresh diagrams from preview tab."""
        # Get preview tab from parent app
        try:
            app = self.winfo_toplevel()
            if hasattr(app, 'preview_tab'):
                results = app.preview_tab._results
                self._extract_diagrams(results)
                self._on_status_update(
                    f"Trovati {len(self._diagrams)} diagrammi",
                    "success" if self._diagrams else "info"
                )
            else:
                self._on_status_update(
                    "Tab Preview non trovata",
                    "warning"
                )
        except Exception as e:
            logger.error("Error refreshing diagrams: %s", e)
            self._on_status_update(f"Errore: {e}", "error")

    def _extract_diagrams(self, results: dict[str, str]) -> None:
        """Extract Mermaid diagrams from document results."""
        self._diagrams.clear()

        # Clear existing diagram buttons
        for widget in self.diagram_list.winfo_children():
            if widget != self.no_diagrams_label:
                widget.destroy()

        pattern = r'```mermaid\s*([\s\S]*?)```'

        for filename, content in results.items():
            matches = re.findall(pattern, content)
            for i, match in enumerate(matches):
                diagram = MermaidDiagram(match, filename, i + 1)
                self._diagrams.append(diagram)

        # Update UI
        self.diagram_count.configure(text=str(len(self._diagrams)))

        if self._diagrams:
            self.no_diagrams_label.pack_forget()
            self._populate_diagram_list()
        else:
            self.no_diagrams_label.pack(pady=30)

    def _populate_diagram_list(self) -> None:
        """Populate the diagram list with buttons and validation status."""
        valid_count = sum(1 for d in self._diagrams if d.is_valid)
        invalid_count = len(self._diagrams) - valid_count

        # Show summary if there are invalid diagrams
        if invalid_count > 0:
            summary = ctk.CTkFrame(self.diagram_list, fg_color="#fef2f2", corner_radius=8)
            summary.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(
                summary,
                text=f"Attenzione: {invalid_count} diagrammi con possibili errori",
                font=ctk.CTkFont(size=10),
                text_color="#dc2626"
            ).pack(pady=8)

        for i, diagram in enumerate(self._diagrams):
            # Color based on validation status
            if diagram.is_valid:
                frame_color = "white"
                status_icon = ""
            else:
                frame_color = "#fefce8"  # Light yellow for warnings
                status_icon = " "

            btn_frame = ctk.CTkFrame(self.diagram_list, fg_color=frame_color, corner_radius=8)
            btn_frame.pack(fill="x", pady=3)

            # Header row with button and status
            header = ctk.CTkFrame(btn_frame, fg_color="transparent")
            header.pack(fill="x", padx=5, pady=2)

            btn = ctk.CTkButton(
                header,
                text=f"{status_icon}{diagram.diagram_type} #{diagram.index}",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="transparent",
                text_color="#1e293b" if diagram.is_valid else "#b45309",
                hover_color="#e2e8f0",
                anchor="w",
                height=32,
                command=lambda d=diagram: self._select_diagram(d)
            )
            btn.pack(side="left", fill="x", expand=True)

            # Source file label
            ctk.CTkLabel(
                btn_frame,
                text=f"Da: {diagram.source_file}",
                font=ctk.CTkFont(size=10),
                text_color=COLORS['text_muted']
            ).pack(anchor="w", padx=10, pady=(0, 3))

            # Show validation error if any
            if not diagram.is_valid:
                ctk.CTkLabel(
                    btn_frame,
                    text=f"Avviso: {diagram.validation_error}",
                    font=ctk.CTkFont(size=9),
                    text_color="#b45309"
                ).pack(anchor="w", padx=10, pady=(0, 5))

    def _select_diagram(self, diagram: MermaidDiagram) -> None:
        """Select and display a diagram."""
        self._current_diagram = diagram
        self._render_diagram()

        # Update info bar with validation status
        if diagram.is_valid:
            info_text = f"{diagram.diagram_type} da {diagram.source_file}"
            info_color = COLORS['text_muted']
        else:
            info_text = f"{diagram.diagram_type} da {diagram.source_file} (Possibile errore di sintassi)"
            info_color = "#b45309"

        self.info_label.configure(text=info_text, text_color=info_color)

        # Show sanitization info if code was modified
        if diagram.raw_code != diagram.code:
            size_text = f"{len(diagram.code)} caratteri (sanitizzato)"
        else:
            size_text = f"{len(diagram.code)} caratteri"

        self.code_size_label.configure(text=size_text)

    def _render_diagram(self) -> None:
        """Render the current diagram."""
        if not self._current_diagram:
            return

        html = self._generate_mermaid_html(self._current_diagram)

        if TKINTERWEB_AVAILABLE and self.html_frame:
            self.html_frame.load_html(html)
        else:
            if hasattr(self, 'fallback_text'):
                self.fallback_text.configure(state="normal")
                self.fallback_text.delete("1.0", "end")
                self.fallback_text.insert("1.0", f"Codice Mermaid:\n\n{self._current_diagram.code}")
                self.fallback_text.configure(state="disabled")

    def _on_theme_change(self, value: str) -> None:
        """Handle theme change."""
        self._render_diagram()

    def _zoom_in(self) -> None:
        """Zoom in."""
        self._zoom_level = min(3.0, self._zoom_level + 0.25)
        self.zoom_label.configure(text=f"{int(self._zoom_level * 100)}%")
        self._render_diagram()

    def _zoom_out(self) -> None:
        """Zoom out."""
        self._zoom_level = max(0.25, self._zoom_level - 0.25)
        self.zoom_label.configure(text=f"{int(self._zoom_level * 100)}%")
        self._render_diagram()

    def _zoom_reset(self) -> None:
        """Reset zoom to 100%."""
        self._zoom_level = 1.0
        self.zoom_label.configure(text="100%")
        self._render_diagram()

    def _copy_code(self) -> None:
        """Copy current diagram code to clipboard."""
        if not self._current_diagram:
            self._on_status_update("Nessun diagramma selezionato", "warning")
            return

        self.clipboard_clear()
        self.clipboard_append(self._current_diagram.code)
        self._on_status_update("Codice copiato negli appunti", "success")

    def _export_png(self) -> None:
        """Export current diagram as PNG."""
        if not self._current_diagram:
            self._on_status_update("Nessun diagramma selezionato", "warning")
            return

        self._open_export_dialog("png")

    def _export_svg(self) -> None:
        """Export current diagram as SVG."""
        if not self._current_diagram:
            self._on_status_update("Nessun diagramma selezionato", "warning")
            return

        self._open_export_dialog("svg")

    def _open_export_dialog(self, format_type: str) -> None:
        """Open browser with export instructions."""
        # For now, open in browser where user can right-click to save
        self._open_in_browser()
        self._on_status_update(
            f"Nel browser: tasto destro sul diagramma > Salva come {format_type.upper()}",
            "info"
        )

    def _open_in_browser(self) -> None:
        """Open current diagram in system browser."""
        if not self._current_diagram:
            self._on_status_update("Nessun diagramma selezionato", "warning")
            return

        html = self._generate_full_browser_html()

        # Save to temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.html',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(html)
            self._temp_html_path = Path(f.name)

        webbrowser.open(f'file://{self._temp_html_path}')
        self._on_status_update("Aperto nel browser", "success")

    def _generate_full_browser_html(self) -> str:
        """Generate full HTML page for browser viewing with all diagrams."""
        theme_map = {
            "Default": "default",
            "Dark": "dark",
            "Forest": "forest",
            "Neutral": "neutral"
        }
        theme = theme_map.get(self.theme_combo.get(), "default")
        is_dark = theme == "dark"

        diagrams_html = ""
        for i, diagram in enumerate(self._diagrams):
            # Escape code for HTML display
            html_escaped_code = (diagram.code
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
            )

            # Status indicator
            status_class = "" if diagram.is_valid else "has-warning"
            status_badge = "" if diagram.is_valid else '<span class="warning-badge">Possibile errore</span>'

            diagrams_html += f'''
            <div class="diagram-card {status_class}" id="diagram-{i}">
                <div class="diagram-header">
                    <h3>{diagram.diagram_type} #{diagram.index} {status_badge}</h3>
                    <span class="source">Da: {diagram.source_file}</span>
                </div>
                <div class="diagram-content" id="content-{i}">
                    <pre class="mermaid" id="mermaid-{i}">
{diagram.code}
                    </pre>
                </div>
                <div class="error-fallback" id="error-{i}" style="display:none;">
                    <div class="error-message">
                        <strong>Errore di rendering:</strong>
                        <span id="error-msg-{i}"></span>
                    </div>
                    <pre class="code-block">{html_escaped_code}</pre>
                </div>
                <div class="diagram-actions">
                    <button onclick="copyCode({i})">Copia Codice</button>
                    <button onclick="downloadSVG({i})">Scarica SVG</button>
                </div>
                <details>
                    <summary>Mostra codice sorgente</summary>
                    <pre class="code-block"><code id="code-{i}">{html_escaped_code}</code></pre>
                </details>
            </div>
            '''

        return f'''<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mermaid Visualizer - AI Context Studio</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: {"#0f172a" if is_dark else "linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)"};
            color: {"#e2e8f0" if is_dark else "#1e293b"};
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .subtitle {{
            color: {"#94a3b8" if is_dark else "#64748b"};
        }}
        .controls {{
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        .controls button {{
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: transform 0.2s;
        }}
        .controls button:hover {{
            transform: translateY(-2px);
        }}
        .btn-primary {{
            background: #3b82f6;
            color: white;
        }}
        .diagram-card {{
            background: {"#1e293b" if is_dark else "white"};
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,{"0.3" if is_dark else "0.1"});
        }}
        .diagram-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid {"#334155" if is_dark else "#e2e8f0"};
        }}
        .diagram-header h3 {{
            font-size: 1.25rem;
        }}
        .source {{
            color: {"#94a3b8" if is_dark else "#64748b"};
            font-size: 0.9rem;
        }}
        .diagram-content {{
            display: flex;
            justify-content: center;
            padding: 30px;
            background: {"#0f172a" if is_dark else "#f8fafc"};
            border-radius: 12px;
            margin-bottom: 20px;
            overflow: auto;
        }}
        .diagram-actions {{
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }}
        .diagram-actions button {{
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            background: {"#334155" if is_dark else "#e2e8f0"};
            color: {"#e2e8f0" if is_dark else "#1e293b"};
        }}
        .diagram-actions button:hover {{
            background: {"#475569" if is_dark else "#cbd5e1"};
        }}
        details {{
            margin-top: 15px;
        }}
        summary {{
            cursor: pointer;
            color: #3b82f6;
            font-weight: 500;
        }}
        .code-block {{
            background: {"#0f172a" if is_dark else "#1e293b"};
            color: #e2e8f0;
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
            overflow-x: auto;
            font-family: 'Consolas', monospace;
            font-size: 13px;
        }}
        .mermaid svg {{
            max-width: none !important;
        }}
        .has-warning {{
            border-left: 4px solid #f59e0b;
        }}
        .warning-badge {{
            background: #fef3c7;
            color: #b45309;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: normal;
            margin-left: 10px;
        }}
        .error-fallback {{
            background: {"#2d1b1b" if is_dark else "#fef2f2"};
            border: 2px solid {"#7f1d1d" if is_dark else "#fecaca"};
            border-radius: 8px;
            padding: 20px;
        }}
        .error-message {{
            color: {"#fca5a5" if is_dark else "#dc2626"};
            margin-bottom: 15px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Mermaid Visualizer</h1>
            <p class="subtitle">AI Context Studio - {len(self._diagrams)} diagrammi</p>
        </header>

        <div class="controls">
            <button class="btn-primary" onclick="window.print()">Stampa / Salva PDF</button>
        </div>

        {diagrams_html}
    </div>

    <script>
        mermaid.initialize({{
            startOnLoad: false,
            theme: '{theme}',
            securityLevel: 'loose',
            flowchart: {{ useMaxWidth: false, htmlLabels: true }},
            sequence: {{ useMaxWidth: false }},
            logLevel: 'error'
        }});

        // Render each diagram individually to handle errors gracefully
        async function renderAllDiagrams() {{
            const diagrams = document.querySelectorAll('.mermaid');

            for (let i = 0; i < diagrams.length; i++) {{
                const element = diagrams[i];
                const index = element.id.replace('mermaid-', '');
                const content = document.getElementById('content-' + index);
                const errorDiv = document.getElementById('error-' + index);
                const errorMsg = document.getElementById('error-msg-' + index);

                try {{
                    const {{ svg }} = await mermaid.render('svg-' + index, element.textContent.trim());
                    element.innerHTML = svg;
                }} catch (error) {{
                    console.error('Mermaid error for diagram ' + index + ':', error);
                    content.style.display = 'none';
                    errorDiv.style.display = 'block';
                    errorMsg.textContent = error.message || 'Errore di sintassi';
                }}
            }}
        }}

        renderAllDiagrams();

        function copyCode(index) {{
            const code = document.getElementById('code-' + index).textContent;
            navigator.clipboard.writeText(code).then(() => {{
                alert('Codice copiato!');
            }});
        }}

        function downloadSVG(index) {{
            const container = document.querySelector('#diagram-' + index + ' .diagram-content');
            const svg = container.querySelector('svg');
            if (svg) {{
                const svgData = new XMLSerializer().serializeToString(svg);
                const blob = new Blob([svgData], {{type: 'image/svg+xml'}});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'diagram-' + index + '.svg';
                a.click();
                URL.revokeObjectURL(url);
            }} else {{
                alert('Impossibile scaricare: il diagramma non è stato renderizzato correttamente');
            }}
        }}
    </script>
</body>
</html>'''

    def load_diagrams(self, diagrams_data: list[tuple[str, str]]) -> None:
        """
        Load diagrams from external source.

        Args:
            diagrams_data: List of (source_file, mermaid_code) tuples.
        """
        self._diagrams.clear()

        for widget in self.diagram_list.winfo_children():
            if widget != self.no_diagrams_label:
                widget.destroy()

        for i, (source, code) in enumerate(diagrams_data):
            diagram = MermaidDiagram(code, source, i + 1)
            self._diagrams.append(diagram)

        self.diagram_count.configure(text=str(len(self._diagrams)))

        if self._diagrams:
            self.no_diagrams_label.pack_forget()
            self._populate_diagram_list()
            self._select_diagram(self._diagrams[0])
        else:
            self.no_diagrams_label.pack(pady=30)
