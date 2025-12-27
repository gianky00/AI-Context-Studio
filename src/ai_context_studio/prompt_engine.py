# -*- coding: utf-8 -*-
"""
Prompt engine for AI Context Studio.

This module contains the PromptEngine class responsible for
building prompts for documentation generation.
"""

from __future__ import annotations

import logging
from typing import Optional

from .models import ExistingDoc, GenerationType, SmartPreset

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
            GenerationType.DATABASE: cls._get_database_prompt(),
            GenerationType.DEPLOYMENT: cls._get_deployment_prompt(),
            GenerationType.DEPENDENCIES: cls._get_dependencies_prompt(),
            GenerationType.PERFORMANCE: cls._get_performance_prompt(),
        }

    @classmethod
    def build_prompt(
        cls,
        doc_type: GenerationType,
        code_content: str,
        smart_preset: Optional[SmartPreset] = None,
        existing_doc: Optional[ExistingDoc] = None
    ) -> str:
        """
        Build a complete prompt for documentation generation.

        Args:
            doc_type: Type of documentation to generate.
            code_content: Source code to analyze.
            smart_preset: Optional preset configuration.
            existing_doc: Optional existing documentation to update.

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

        # Add existing document context if available
        if existing_doc:
            parts.append("\n=== DOCUMENTAZIONE ESISTENTE ===")
            parts.append(cls._get_existing_doc_context(existing_doc))

        parts.append("\n=== ISTRUZIONI SPECIFICHE ===")
        parts.append(cls.GENERATION_PROMPTS[doc_type])

        parts.append("\n=== CODICE SORGENTE DA ANALIZZARE ===")
        parts.append(code_content)

        logger.debug(
            "Built prompt for %s: %d chars (existing doc: %s)",
            doc_type.label,
            sum(len(p) for p in parts),
            existing_doc.filename if existing_doc else "none"
        )

        return "\n".join(parts)

    @staticmethod
    def _get_existing_doc_context(existing_doc: ExistingDoc) -> str:
        """
        Build context about existing documentation.

        Args:
            existing_doc: The existing documentation file.

        Returns:
            Context string to include in the prompt.
        """
        context_parts: list[str] = []

        if existing_doc.is_outdated:
            context_parts.append(
                f"ATTENZIONE: Esiste gia' il file '{existing_doc.filename}' ma sembra OBSOLETO o incompleto.\n"
                "Il tuo compito e' SOSTITUIRLO COMPLETAMENTE con una versione aggiornata e completa.\n"
                "Mantieni la stessa struttura generale se valida, ma aggiorna tutto il contenuto.\n"
            )
        else:
            context_parts.append(
                f"ATTENZIONE: Esiste gia' il file '{existing_doc.filename}'.\n"
                "Il tuo compito e' AGGIORNARE questa documentazione esistente:\n"
                "- Mantieni le sezioni valide e aggiornale se necessario\n"
                "- Aggiungi nuove sezioni per funzionalita' mancanti\n"
                "- Rimuovi riferimenti a codice obsoleto\n"
                "- Migliora la qualita' dove possibile\n"
            )

        # Include a preview of the existing content (truncated)
        if existing_doc.content:
            preview_length = 2000
            content_preview = existing_doc.content[:preview_length]
            if len(existing_doc.content) > preview_length:
                content_preview += "\n... [contenuto troncato] ..."

            context_parts.append("\n--- CONTENUTO ATTUALE ---\n")
            context_parts.append(content_preview)
            context_parts.append("\n--- FINE CONTENUTO ATTUALE ---\n")

        return "\n".join(context_parts)

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

    @staticmethod
    def _get_database_prompt() -> str:
        """Get the database schema prompt."""
        return """
## GENERA: DATABASE_SCHEMA.md - DOCUMENTAZIONE DATABASE ESAUSTIVA

Crea documentazione database COMPLETA:

### 1. Overview Database
Tipo database, versione, hosting, pool connections.

### 2. Schema ER (Mermaid)
Diagramma Entity-Relationship completo.

### 3. Tabelle e Collezioni
Per OGNI tabella/collezione:
- Nome, scopo, colonne/campi
- Tipi dati, constraints
- Indici, chiavi primarie/foreign

### 4. Relazioni
Tutte le relazioni con cardinalita'.

### 5. Query Comuni
Query SQL/NoSQL piu' utilizzate con spiegazioni.

### 6. Stored Procedures/Functions
Se presenti, documentale.

### 7. Migration Strategy
Come gestire le migrazioni schema.

### 8. Backup e Recovery
Strategie backup, retention policy.

### 9. Performance Considerations
Indici raccomandati, query optimization.

### 10. Seed Data
Dati di esempio per development.
"""

    @staticmethod
    def _get_deployment_prompt() -> str:
        """Get the deployment guide prompt."""
        return """
## GENERA: DEPLOYMENT_GUIDE.md - GUIDA DEPLOYMENT ESAUSTIVA

Crea guida deployment COMPLETA:

### 1. Ambienti
Development, staging, production con differenze.

### 2. Prerequisiti Infrastruttura
Server, risorse, servizi cloud necessari.

### 3. Configurazione per Ambiente
Variabili ambiente, secrets management.

### 4. Build Process
Comandi build, bundling, optimization.

### 5. CI/CD Pipeline
Descrizione pipeline, stages, triggers.

### 6. Deployment Steps
Procedura passo-passo per deploy.

### 7. Rollback Procedure
Come fare rollback in caso di problemi.

### 8. Health Checks
Endpoint health, monitoring.

### 9. Scaling
Horizontal/vertical scaling, auto-scaling.

### 10. Troubleshooting
Problemi comuni post-deploy e soluzioni.

### 11. Post-Deployment Checklist
Verifiche da fare dopo ogni deploy.
"""

    @staticmethod
    def _get_dependencies_prompt() -> str:
        """Get the dependencies analysis prompt."""
        return """
## GENERA: DEPENDENCIES_ANALYSIS.md - ANALISI DIPENDENZE ESAUSTIVA

Crea analisi dipendenze COMPLETA:

### 1. Overview Dipendenze
Numero totale, categorie, package manager.

### 2. Dipendenze Runtime
Tabella con: nome, versione, scopo, licenza.

### 3. Dipendenze Development
Dev dependencies con scopo.

### 4. Albero Dipendenze
Dipendenze transitive principali.

### 5. Analisi Licenze
Compatibilita' licenze, rischi legali.

### 6. Vulnerabilita' Note
CVE noti, severita', remediation.

### 7. Dipendenze Outdated
Versioni obsolete, upgrade path.

### 8. Alternative Suggerite
Librerie alternative piu' leggere o mantenute.

### 9. Lock File Analysis
Stato del lock file, consistency.

### 10. Raccomandazioni
Azioni prioritarie per migliorare le dipendenze.
"""

    @staticmethod
    def _get_performance_prompt() -> str:
        """Get the performance guide prompt."""
        return """
## GENERA: PERFORMANCE_GUIDE.md - GUIDA PERFORMANCE ESAUSTIVA

Crea guida performance COMPLETA:

### 1. Performance Overview
Stato attuale, metriche chiave.

### 2. Bottleneck Identificati
Punti critici nel codice con spiegazioni.

### 3. Ottimizzazioni Codice
Pattern inefficienti trovati, come fixarli.

### 4. Caching Strategies
Cosa cachare, TTL, invalidation.

### 5. Database Performance
Query lente, indici mancanti, N+1 problems.

### 6. Bundle Size (se frontend)
Analisi bundle, code splitting, lazy loading.

### 7. Memory Management
Memory leaks potenziali, garbage collection.

### 8. Async/Concurrency
Uso corretto di async, parallelismo.

### 9. Profiling Guide
Come profilare l'applicazione, tools consigliati.

### 10. Monitoring Setup
Metriche da monitorare, alerting.

### 11. Performance Budget
Target performance da rispettare.

### 12. Quick Wins
Ottimizzazioni facili ad alto impatto.
"""


# Initialize prompts on module load
PromptEngine._init_prompts()
