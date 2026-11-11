# AI Context Studio — Knowledge Base & Architecture Generator per Agenti AI

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-CustomTkinter-0284C7?style=flat-square)
![AI SDK](https://img.shields.io/badge/AI-Google%20GenAI%20SDK-4285F4?style=flat-square&logo=google&logoColor=white)
![Quality](https://img.shields.io/badge/Quality-Pytest%20%7C%20MyPy%20%7C%20Ruff-0F172A?style=flat-square)

**AI Context Studio** è un'applicazione desktop progettata per analizzare repository software locali, redigere automaticamente informazioni sensibili e generare **Knowledge Base strutturate in Markdown** e **diagrammi architetturali Mermaid** ottimizzati per agenti di sviluppo AI (Claude, Cursor, GitHub Copilot, Gemini).

---

## Funzionalità Principali

- **Scansione Intelligente del Repository (`scanner.py`):** Esplorazione selettiva dell'albero dei file con filtri `.gitignore`, controllo di sicurezza sui percorsi (`path_safety.py`) ed esclusione automatica di artefatti binari o directory di build.
- **Redazione Automatica dei Segreti (`secret_redaction.py`):** Rilevamento e mascheramento preventivo di chiavi API, token e credenziali prima dell'invio del contesto ai modelli LLM.
- **Stima Token & Controllo Costi (`token_estimator.py`):** Calcolo preventivo del consumo di token e storico dettagliato delle sessioni di generazione (`cost_history_window.py`).
- **Prompt Engine Modulare (`prompt_engine.py`):** Template ingegnerizzati e personalizzabili per produrre documentazione architetturale, specifiche di dominio e contesti operativi.
- **Visualizzatore Mermaid Integrato (`visualizer_tab.py`):** Rendering interattivo dei diagrammi di architettura direttamente nell'interfaccia desktop tramite `pywebview` / `tkinterweb` con sanitizzazione automatica della sintassi.
- **Gestione Sicura Credenziali:** Salvataggio delle API key tramite il Credential Store di sistema (`keyring`) o cifratura simmetrica Fernet (`cryptography`).

---

## Stack Tecnologico

| Componente | Tecnologia |
| :--- | :--- |
| **Linguaggio** | Python 3.9+ |
| **Interfaccia Desktop** | CustomTkinter, TkinterWeb, PyWebView |
| **Integrazione LLM** | Google GenAI SDK (`google-genai`) |
| **Sicurezza Locale** | OS Keyring (`keyring`), Cifratura Fernet (`cryptography`) |
| **Testing & Linting** | Pytest, MyPy, Ruff, Pre-commit |

---

## Installazione e Avvio

### Setup in modalità sviluppo

```powershell
# Installazione del pacchetto in modalità editable con dipendenze di sviluppo
pip install -e ".[dev]"

# Avvio dell'applicazione
ai-context-studio
# oppure:
python -m ai_context_studio
```

Su Windows è possibile avviare direttamente l'interfaccia senza console tramite `Avvia_AI_Context_Studio.bat` (`launcher.pyw`).

### Esecuzione Test e Controlli Qualità

```powershell
python -m pytest tests -q
python -m mypy
python -m ruff check src/ tests/
```

---

## Struttura del Progetto

```text
AI-Context-Studio/
├── src/ai_context_studio/
│   ├── app.py                  # Entry point GUI e coordinamento tab
│   ├── api_client.py           # Client asincrono/sincrono per modelli GenAI
│   ├── scanner.py              # Scansione file system e filtri
│   ├── secret_redaction.py     # Sanitizzazione credenziali e segreti
│   ├── token_estimator.py      # Calcolo token e stima costi
│   ├── prompt_engine.py        # Costruzione prompt strutturati
│   └── ui/                     # Componenti grafici (File Tree, Preview, Visualizer)
├── tests/                      # Suite di test unitari e di integrazione
└── pyproject.toml              # Configurazione pacchetto, Ruff, MyPy e Pytest
```

---

## Autore
Sviluppato da **Giancarlo Allegretti** — Rilasciato sotto licenza MIT.
