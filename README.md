# AI Context Studio

Applicazione desktop per scansionare un progetto locale e generare knowledge base Markdown destinate ad agenti AI (Claude, Copilot, Cursor e simili).

## Requisiti

- Python 3.9 o superiore
- Una API key Google Gemini
- SDK Google Gen AI (`google-genai`, incluso nelle dipendenze del progetto)

## Installazione

Dalla root del repository:

```powershell
pip install -e .
```

Solo dipendenze (non installa il pacchetto né il comando `ai-context-studio`):

```powershell
pip install -r requirements.txt
```

Per i test:

```powershell
pip install -e ".[dev]"
python -m pytest tests -q
python -m mypy
```

`python -m mypy` controlla i moduli core (non-UI) elencati in `[tool.mypy]` `files` in `pyproject.toml`.

Hook pre-commit (incluso in `[dev]`): `pre-commit install`.

## Avvio

```powershell
python -m ai_context_studio
```

Dopo `pip install -e .` è disponibile anche il comando `ai-context-studio`.

Su Windows si può usare `Avvia_AI_Context_Studio.bat`, che lancia `launcher.pyw` con `pythonw`.

Flag di debug: `--debug` oppure `-d`.

## Configurazione

La configurazione persistente vive in `~/.ai_context_studio/` (`%USERPROFILE%\.ai_context_studio` su Windows):

- `config.json` — impostazioni e API key (cifrata se `cryptography` è disponibile)
- `.keyfile` — chiave Fernet per la cifratura
- `models_cache.json` — elenco modelli Gemini in cache
- `custom_prompts.json` — prompt personalizzati
- `cost_history.json` — storico stime di costo
- `logs/` — log applicazione

L'API key Gemini si inserisce dalla tab **Setup** dell'applicazione. Non va committata nel repository.

Le chiavi sono salvate preferibilmente nel credential store del sistema operativo.

I documenti generati vengono salvati in `{progetto}/docs/`.
