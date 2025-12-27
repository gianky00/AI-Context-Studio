# -*- coding: utf-8 -*-
"""
Data models and enumerations for AI Context Studio.

This module contains all data structures used throughout the application:
- Generation types and document configurations
- Project type classifications
- Focus area definitions
- File and scan result data classes
- Smart preset configurations
- Generation result containers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from .constants import COLORS


class GenerationType(Enum):
    """
    Types of documentation that can be generated.

    Each generation type includes:
    - filename: Output file name
    - icon: Display emoji
    - label: Human-readable label
    - color: UI color code
    - description: Detailed description for tooltips
    """
    ARCHITECTURE = (
        "AI_ARCHITECTURE.md",
        "\U0001F3D7\uFE0F",  # Building construction
        "Architettura",
        COLORS['primary'],
        "Genera documentazione completa dell'architettura: stack tecnologico, "
        "struttura directory, componenti, diagrammi Mermaid, setup sviluppo."
    )
    RULES = (
        "AI_RULES.md",
        "\U0001F4CB",  # Clipboard
        "Regole Coding",
        COLORS['purple'],
        "Genera le regole di coding del progetto: convenzioni naming, pattern "
        "obbligatori, struttura file, DO/DON'T, checklist pre-commit."
    )
    CONTEXT = (
        "PROJECT_CONTEXT.md",
        "\U0001F4D6",  # Open book
        "Contesto Progetto",
        COLORS['teal'],
        "Genera il contesto business: problema risolto, utenti target, "
        "funzionalità, roadmap, glossario, integrazioni."
    )
    API_DOCS = (
        "API_DOCUMENTATION.md",
        "\U0001F50C",  # Electric plug
        "Documentazione API",
        COLORS['orange'],
        "Genera documentazione API completa: endpoints, parametri, "
        "request/response, esempi cURL, modelli dati."
    )
    TESTING = (
        "TESTING_GUIDE.md",
        "\U0001F9EA",  # Test tube
        "Guida Testing",
        COLORS['pink'],
        "Genera guida al testing: strategia test, setup ambiente, convenzioni, "
        "scenari da testare, mocking, CI/CD."
    )
    SECURITY = (
        "SECURITY_AUDIT.md",
        "\U0001F512",  # Lock
        "Audit Sicurezza",
        COLORS['danger'],
        "Genera audit di sicurezza: autenticazione, gestione secrets, "
        "OWASP Top 10, vulnerabilità, raccomandazioni."
    )
    ONBOARDING = (
        "DEVELOPER_ONBOARDING.md",
        "\U0001F680",  # Rocket
        "Onboarding Dev",
        COLORS['success'],
        "Genera guida onboarding per nuovi sviluppatori: setup day-1, "
        "architettura semplificata, workflow, risorse, FAQ."
    )
    DATABASE = (
        "DATABASE_SCHEMA.md",
        "\U0001F5C4\uFE0F",  # File cabinet
        "Schema Database",
        COLORS['indigo'],
        "Genera documentazione database: schema ER, tabelle, relazioni, "
        "indici, stored procedures, migration strategy."
    )
    DEPLOYMENT = (
        "DEPLOYMENT_GUIDE.md",
        "\U0001F4E6",  # Package
        "Guida Deploy",
        COLORS['cyan'],
        "Genera guida deployment: ambienti, configurazioni, CI/CD, "
        "rollback, monitoring, troubleshooting."
    )
    DEPENDENCIES = (
        "DEPENDENCIES_ANALYSIS.md",
        "\U0001F517",  # Link
        "Analisi Dipendenze",
        COLORS['slate'],
        "Analizza dipendenze: librerie usate, versioni, licenze, "
        "vulnerabilità note, alternative suggerite."
    )
    PERFORMANCE = (
        "PERFORMANCE_GUIDE.md",
        "\u26A1",  # Lightning
        "Guida Performance",
        COLORS['warning'],
        "Genera guida performance: bottleneck identificati, ottimizzazioni, "
        "caching strategies, profiling, best practices."
    )

    def __init__(
        self,
        filename: str,
        icon: str,
        label: str,
        color: str,
        description: str
    ) -> None:
        self.filename = filename
        self.icon = icon
        self.label = label
        self.color = color
        self.description = description


class ProjectType(Enum):
    """
    Project type classifications for smart preset selection.

    Each project type includes:
    - icon: Display emoji
    - label: Human-readable label
    - description: Example technologies
    """
    WEB_FRONTEND = (
        "\U0001F310",  # Globe
        "Web Frontend",
        "React, Vue, Angular, HTML/CSS/JS"
    )
    WEB_BACKEND = (
        "\u2699\uFE0F",  # Gear
        "Web Backend",
        "API REST, GraphQL, Microservizi"
    )
    MOBILE = (
        "\U0001F4F1",  # Mobile phone
        "Mobile App",
        "React Native, Flutter, iOS, Android"
    )
    DESKTOP = (
        "\U0001F5A5\uFE0F",  # Desktop computer
        "Desktop App",
        "Electron, PyQt, WPF, Swing"
    )
    DATA_SCIENCE = (
        "\U0001F4CA",  # Bar chart
        "Data Science",
        "ML, Analytics, Jupyter, Pandas"
    )
    DEVOPS = (
        "\U0001F433",  # Whale (Docker)
        "DevOps/Infra",
        "Docker, K8s, CI/CD, Terraform"
    )
    LIBRARY = (
        "\U0001F4DA",  # Books
        "Libreria/SDK",
        "Package, Plugin, Modulo riutilizzabile"
    )
    GENERIC = (
        "\U0001F4C1",  # Folder
        "Generico",
        "Progetto generico o misto"
    )

    def __init__(self, icon: str, label: str, description: str) -> None:
        self.icon = icon
        self.label = label
        self.description = description


class FocusArea(Enum):
    """
    Focus areas for documentation generation emphasis.

    Each focus area includes:
    - icon: Display emoji
    - label: Human-readable label
    - description: Detailed description
    """
    SECURITY = (
        "\U0001F512",  # Lock
        "Sicurezza",
        "Focus su vulnerabilità e best practices"
    )
    PERFORMANCE = (
        "\u26A1",  # Lightning
        "Performance",
        "Ottimizzazioni e scalabilità"
    )
    TESTING = (
        "\U0001F9EA",  # Test tube
        "Testing",
        "Copertura test e strategie QA"
    )
    MAINTAINABILITY = (
        "\U0001F527",  # Wrench
        "Manutenibilità",
        "Leggibilità e refactoring"
    )
    DOCUMENTATION = (
        "\U0001F4DD",  # Memo
        "Documentazione",
        "Commenti e documentazione inline"
    )
    ACCESSIBILITY = (
        "\u267F",  # Wheelchair
        "Accessibilità",
        "A11y e usabilità"
    )


@dataclass
class FileInfo:
    """
    Information about a single file in the project.

    Attributes:
        path: Absolute path to the file
        relative_path: Path relative to project root
        size: File size in bytes
        extension: File extension (including dot)
        included: Whether file is included in analysis
    """
    path: Path
    relative_path: str
    size: int
    extension: str
    included: bool = True


@dataclass
class ExistingDoc:
    """
    Information about an existing markdown documentation file.

    Attributes:
        path: Absolute path to the file
        relative_path: Path relative to project root
        filename: File name only
        content: File contents (loaded lazily)
        is_outdated: Whether the file appears outdated
    """
    path: Path
    relative_path: str
    filename: str
    content: str = ""
    is_outdated: bool = False


@dataclass
class ScanResult:
    """
    Result of a project directory scan.

    Attributes:
        root_path: Root directory that was scanned
        files: List of FileInfo objects found
        total_size: Total size of included files in bytes
        estimated_tokens: Estimated token count for AI processing
        content_map: Dictionary mapping relative paths to file contents
        existing_docs: Dictionary mapping doc type filenames to ExistingDoc
    """
    root_path: Path
    files: list[FileInfo] = field(default_factory=list)
    total_size: int = 0
    estimated_tokens: int = 0
    content_map: dict[str, str] = field(default_factory=dict)
    existing_docs: dict[str, ExistingDoc] = field(default_factory=dict)


@dataclass
class SmartPreset:
    """
    Configuration for smart documentation generation.

    This class holds all user-configurable options that influence
    how documentation is generated.

    Attributes:
        project_type: Type of project being documented
        focus_areas: List of areas to emphasize
        target_audience: Who will read the documentation
        additional_notes: Custom notes from user
    """
    project_type: ProjectType = ProjectType.GENERIC
    focus_areas: list[FocusArea] = field(default_factory=list)
    target_audience: str = "AI Agents (Claude, Copilot, Cursor, Jules)"
    additional_notes: str = ""

    def to_prompt_context(self) -> str:
        """
        Generate prompt context from preset settings.

        Returns:
            Formatted string containing all preset information
            suitable for inclusion in an AI prompt.
        """
        parts: list[str] = []

        parts.append(
            f"TIPO PROGETTO: {self.project_type.label} "
            f"({self.project_type.description})"
        )
        parts.append(
            "LIVELLO DETTAGLIO: ESAUSTIVO - Copertura completa e "
            "approfondita di ogni aspetto con molti esempi pratici"
        )

        if self.focus_areas:
            focus_str = ", ".join(f.value[1] for f in self.focus_areas)
            parts.append(f"FOCUS PRINCIPALE: {focus_str}")

        parts.append(f"TARGET AUDIENCE: {self.target_audience}")

        if self.additional_notes.strip():
            parts.append(f"NOTE SPECIFICHE: {self.additional_notes}")

        return "\n".join(parts)


@dataclass
class GenerationResult:
    """
    Result of a documentation generation attempt.

    Attributes:
        success: Whether generation succeeded
        doc_type: Type of document generated
        content: Generated content (if successful)
        error_message: Error message (if failed)
        tokens_used: Estimated tokens in output
        generation_time: Time taken in seconds
        retries: Number of retry attempts made
    """
    success: bool
    doc_type: GenerationType
    content: str = ""
    error_message: str = ""
    tokens_used: int = 0
    generation_time: float = 0.0
    retries: int = 0
