# -*- coding: utf-8 -*-
"""
Prompt engine for AI Context Studio.

This module contains the PromptEngine class responsible for
building prompts for documentation generation.
"""

from __future__ import annotations

import logging
from typing import Optional

from .models import GenerationType, SmartPreset

logger = logging.getLogger(__name__)


class PromptEngine:
    """
    Engine for building AI prompts for documentation generation.

    Contains the base system prompt and specific prompts for each
    documentation type.
    """

    BASE_SYSTEM_PROMPT: str = """
Sei un Senior Software Architect con 20+ anni di esperienza, specializzato in "Context Engineering"
per AI Agents (Claude, GPT, Gemini, Copilot, Cursor, Jules, Windsurf).

Il tuo compito e' analizzare codice sorgente e generare documentazione di ALTISSIMA QUALITA' che:
1. Permetta ad altri Agenti AI di comprendere COMPLETAMENTE il progetto
2. Segua standard professionali di documentazione tecnica
3. Sia immediatamente utilizzabile senza ambiguita'
4. Sia ESAUSTIVA e DETTAGLIATA - non risparmiare dettagli!

REGOLE FONDAMENTALI:
- Scrivi SEMPRE in italiano professionale
- Usa Markdown formattato correttamente
- Includi MOLTI esempi di codice pratici
- Sii ESTREMAMENTE preciso e specifico, mai generico
- Se qualcosa non e' chiaro dal codice, segnalalo come "DA VERIFICARE"
- Aggiungi diagrammi Mermaid dove utile
- Includi tabelle per organizzare informazioni complesse
"""

    # Generation-specific prompts (abbreviated for readability)
    GENERATION_PROMPTS: dict[GenerationType, str] = {}

    @classmethod
    def _init_prompts(cls) -> None:
        """Initialize the generation prompts dictionary."""
        cls.GENERATION_PROMPTS = {
            GenerationType.ARCHITECTURE: cls._get_architecture_prompt(),
            GenerationType.RULES: cls._get_rules_prompt(),
            GenerationType.CONTEXT: cls._get_context_prompt(),
            GenerationType.API_DOCS: cls._get_api_docs_prompt(),
            GenerationType.TESTING: cls._get_testing_prompt(),
            GenerationType.SECURITY: cls._get_security_prompt(),
            GenerationType.ONBOARDING: cls._get_onboarding_prompt(),
        }

    @classmethod
    def build_prompt(
        cls,
        doc_type: GenerationType,
        code_content: str,
        smart_preset: Optional[SmartPreset] = None
    ) -> str:
        """
        Build a complete prompt for documentation generation.

        Args:
            doc_type: Type of documentation to generate.
            code_content: Source code to analyze.
            smart_preset: Optional preset configuration.

        Returns:
            Complete prompt string.
        """
        # Initialize prompts if not done
        if not cls.GENERATION_PROMPTS:
            cls._init_prompts()

        parts: list[str] = [cls.BASE_SYSTEM_PROMPT]

        if smart_preset:
            parts.append("\n=== CONTESTO PROGETTO ===")
            parts.append(smart_preset.to_prompt_context())

        parts.append("\n=== ISTRUZIONI SPECIFICHE ===")
        parts.append(cls.GENERATION_PROMPTS[doc_type])

        parts.append("\n=== CODICE SORGENTE DA ANALIZZARE ===")
        parts.append(code_content)

        logger.debug(
            "Built prompt for %s: %d chars",
            doc_type.label,
            sum(len(p) for p in parts)
        )

        return "\n".join(parts)

    @staticmethod
    def _get_architecture_prompt() -> str:
        """Get the architecture documentation prompt."""
        return """
## GENERA: AI_ARCHITECTURE.md - DOCUMENTAZIONE ARCHITETTURALE ESAUSTIVA

Crea una documentazione architetturale COMPLETA e DETTAGLIATA che includa:

### 1. Executive Summary
- Nome progetto e versione (se rilevabile)
- Obiettivo principale dell'applicazione (2-3 frasi chiare)
- Tipo di architettura (monolite, microservizi, serverless, event-driven, etc.)
- Punti di forza architetturali

### 2. Stack Tecnologico Completo
Tabella DETTAGLIATA con TUTTE le tecnologie rilevate:
| Categoria | Tecnologia | Versione | Scopo | Note |
|-----------|------------|----------|-------|------|

### 3. Struttura Directory Completa
Mappa DETTAGLIATA con spiegazione di OGNI cartella significativa.

### 4. Componenti e Moduli Principali
Per OGNI componente/modulo core descrivi responsabilita', dipendenze e pattern.

### 5. Diagramma Architetturale (Mermaid)
Includi diagrammi graph e sequence dove utile.

### 6. Flusso Dati Dettagliato
Descrivi OGNI flusso principale.

### 7. Configurazione e Ambiente
Variabili ambiente, file di configurazione, secrets.

### 8. Setup Sviluppo Passo-Passo
Comandi completi per clone, install, configure, run.

### 9. Build e Deploy
Processo di build, ambienti, pipeline CI/CD.

### 10. Decisioni Architetturali (ADR)
Tabella con decisioni, motivazioni, alternative.
"""

    @staticmethod
    def _get_rules_prompt() -> str:
        """Get the coding rules prompt."""
        return """
## GENERA: AI_RULES.md - REGOLE DI CODING ESAUSTIVE

Crea un documento di regole RIGIDE e COMPLETE per la codebase:

### 1. Filosofia del Codice
Principi guida rilevati dal codice.

### 2. Convenzioni Naming COMPLETE
Tabelle per file, directory, variabili, funzioni, classi.

### 3. Struttura File Standard
Template da seguire per ogni nuovo file.

### 4. Pattern Obbligatori
Error handling, logging, type hints, docstrings.

### 5. DO - Pratiche CORRETTE
Tabella con pratiche, esempi, motivazioni.

### 6. DON'T - Pratiche da EVITARE
Tabella con anti-pattern, alternative, motivazioni.

### 7. Checklist Pre-Commit
Lista di verifiche prima di ogni commit.

### 8. Code Review Checklist
Verifiche per area (funzionalita', design, performance, sicurezza, test).
"""

    @staticmethod
    def _get_context_prompt() -> str:
        """Get the project context prompt."""
        return """
## GENERA: PROJECT_CONTEXT.md - CONTESTO PROGETTO ESAUSTIVO

Crea documentazione di contesto business COMPLETA:

### 1. Executive Summary
3-5 frasi che spiegano cosa fa, per chi, quale problema risolve.

### 2. Problema e Soluzione
Pain points, value proposition, before/after.

### 3. Utenti Target (Personas)
Descrizione dettagliata per ogni tipo di utente.

### 4. Funzionalita' Principali
Per ogni feature: descrizione, user story, acceptance criteria.

### 5. Roadmap e Backlog
TODO/FIXME dal codice, miglioramenti suggeriti.

### 6. Glossario Completo
Tabella con termini, definizioni, contesto.

### 7. Integrazioni Esterne
API terze parti, database, storage.

### 8. Metriche di Successo (KPI)
Metriche, target, come misurarle.

### 9. Rischi e Mitigazioni
Tabella con rischi, probabilita', impatto, mitigazione.

### 10. Contatti e Risorse
Repository, documentazione, issue tracker.
"""

    @staticmethod
    def _get_api_docs_prompt() -> str:
        """Get the API documentation prompt."""
        return """
## GENERA: API_DOCUMENTATION.md - DOCUMENTAZIONE API ESAUSTIVA

Crea documentazione API COMPLETA:

### 1. Overview API
Informazioni generali, autenticazione, rate limiting.

### 2. Endpoints
Per OGNI endpoint: method, path, descrizione, parametri, request/response, errori, esempi cURL e Python.

### 3. Modelli Dati (Schemas)
Per ogni modello: struttura JSON, validazioni.

### 4. Codici di Errore Globali
Tabella con codici, nomi, descrizioni.

### 5. Webhooks
Se presenti, documenta webhooks.

### 6. SDK e Librerie Client
Esempi di integrazione.

### 7. Changelog API
Versioni, date, cambiamenti.
"""

    @staticmethod
    def _get_testing_prompt() -> str:
        """Get the testing guide prompt."""
        return """
## GENERA: TESTING_GUIDE.md - GUIDA TESTING ESAUSTIVA

Crea guida COMPLETA al testing:

### 1. Strategia di Test
Piramide dei test, obiettivi coverage.

### 2. Setup Ambiente Test
Prerequisiti, installazione, configurazione.

### 3. Struttura Directory Test
Organizzazione file di test.

### 4. Convenzioni Test
Naming convention, struttura AAA, test parametrizzati.

### 5. Fixtures Comuni
Esempi di fixtures condivise.

### 6. Scenari da Testare
Test critici, importanti, utili.

### 7. Mocking Guidelines
Quando mockare, cosa non mockare, esempi.

### 8. Comandi Test
Tutti i comandi pytest utili.

### 9. CI/CD Testing
Configurazione pipeline.

### 10. Performance Testing
Se applicabile.
"""

    @staticmethod
    def _get_security_prompt() -> str:
        """Get the security audit prompt."""
        return """
## GENERA: SECURITY_AUDIT.md - AUDIT SICUREZZA ESAUSTIVO

Crea audit di sicurezza COMPLETO:

### 1. Executive Summary
Stato generale, vulnerabilita' critiche, raccomandazioni.

### 2. Autenticazione & Autorizzazione
Meccanismo auth, gestione sessioni, controllo accessi.

### 3. Gestione Secrets
Secrets nel codice, in config, .gitignore check.

### 4. Input Validation & Sanitization
SQL Injection, XSS, CSRF.

### 5. Dipendenze
Vulnerabilita' note, dipendenze outdated.

### 6. OWASP Top 10 Checklist
Verifica per ogni voce OWASP.

### 7. Crittografia
Algoritmi utilizzati, TLS/SSL.

### 8. Logging & Monitoring
Security logging, PII nei log.

### 9. Raccomandazioni Prioritarie
Critico, alto, medio, basso.

### 10. Compliance Checklist
GDPR, PCI-DSS se applicabili.
"""

    @staticmethod
    def _get_onboarding_prompt() -> str:
        """Get the developer onboarding prompt."""
        return """
## GENERA: DEVELOPER_ONBOARDING.md - GUIDA ONBOARDING ESAUSTIVA

Crea guida onboarding COMPLETA per nuovi sviluppatori:

# Benvenuto nel Team!

## Checklist Primo Giorno
Prima di iniziare, setup ambiente.

## Prerequisiti Software
Tabella con software, versioni, download, verifica.

## Step-by-Step Setup
Comandi completi da clone a run.

## Troubleshooting Setup Comuni
Tabella problemi e soluzioni.

## Architettura in 5 Minuti
Spiegazione semplice, struttura, flusso principale.

## Workflow Sviluppo
Git branching, come sviluppare feature, convenzioni commit.

## Chi Contattare
Tabella con ruoli e contatti.

## Risorse Utili
Link importanti, documentazione da leggere.

## Primi Task Suggeriti
Settimana 1 e 2, good first issues.

## FAQ
Domande frequenti con risposte.
"""


# Initialize prompts on module load
PromptEngine._init_prompts()
