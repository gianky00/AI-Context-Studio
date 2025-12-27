from typing import Optional
from .models import GenerationType

class PromptEngine:
    """Gestisce la costruzione dei prompt per Gemini."""

    BASE_CONTEXT = """
Sei un Senior Software Architect esperto in "Context Engineering" per AI Agents.
Analizza il codice sorgente e genera documentazione che permetta ad altri Agenti AI
(Jules, Cursor, Windsurf, Copilot) di comprendere e lavorare sul progetto.

{custom_instructions}

CODICE SORGENTE:
{code_content}

---
"""

    PROMPT_TEMPLATES = {
        GenerationType.ARCHITECTURE: """
GENERA: AI_ARCHITECTURE.md

Includi:
1. **Stack Tecnologico** - Linguaggi, framework, database, servizi
2. **Architettura Sistema** - Pattern, diagramma componenti (Mermaid), flusso dati
3. **Mappa File Critici** - Entry point, config, moduli core
4. **Dipendenze e Interazioni** - Come i moduli comunicano
5. **Setup Sviluppo** - Requisiti, comandi avvio, variabili ambiente

Formato: Markdown tecnico e preciso.
""",

        GenerationType.RULES: """
GENERA: AI_RULES.md

Estrai regole di coding RIGIDE:
1. **Convenzioni Naming** - Variabili, funzioni, classi, costanti, file
2. **Struttura Codice** - Import, organizzazione classi, docstring, type hints
3. **Pattern e Best Practices** - Gestione errori, logging, config, testing
4. **Regole Sicurezza** - Gestione secrets, validazione input
5. **Anti-pattern da Evitare** - Pratiche deprecate

Formato: Lista DO/DON'T chiara e imperativa.
""",

        GenerationType.CONTEXT: """
GENERA: PROJECT_CONTEXT.md

Crea overview alto livello:
1. **Obiettivo Business** - Problema risolto, utenti target, value proposition
2. **Funzionalità Principali** - Feature list, user stories, casi d'uso
3. **Stato Progetto** - Fase sviluppo, TODO, debito tecnico
4. **Glossario** - Termini dominio, acronimi, entità principali
5. **Dipendenze Esterne** - Servizi terze parti, API, integrazioni

Formato: Markdown orientato al contesto business.
""",

        GenerationType.BUNDLE: """
GENERA TUTTI I DOCUMENTI

Restituisci JSON valido:
{
    "AI_ARCHITECTURE.md": "<contenuto architettura>",
    "AI_RULES.md": "<contenuto regole>",
    "PROJECT_CONTEXT.md": "<contenuto contesto>"
}

Output: SOLO JSON valido, nessun wrapper markdown.
"""
    }

    FILENAME_MAP = {
        GenerationType.ARCHITECTURE: "AI_ARCHITECTURE.md",
        GenerationType.RULES: "AI_RULES.md",
        GenerationType.CONTEXT: "PROJECT_CONTEXT.md",
        GenerationType.BUNDLE: "docs_bundle.json"
    }

    @classmethod
    def build_prompt(cls, doc_type: GenerationType, code_content: str, custom_instructions: str = "") -> str:
        """Costruisce il prompt completo combinando contesto base e template specifico."""
        formatted_instructions = "ISTRUZIONI AGGIUNTIVE: " + custom_instructions if custom_instructions else ""

        base = cls.BASE_CONTEXT.format(
            custom_instructions=formatted_instructions,
            code_content=code_content
        )

        template = cls.PROMPT_TEMPLATES.get(doc_type, cls.PROMPT_TEMPLATES[GenerationType.CONTEXT])

        return base + template

    @classmethod
    def get_filename(cls, doc_type: GenerationType) -> str:
        """Restituisce il nome file per il tipo di documento."""
        return cls.FILENAME_MAP.get(doc_type, "AI_DOCUMENT.md")
