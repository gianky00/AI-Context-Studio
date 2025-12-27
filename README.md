# 🧠 AI Context Studio v1.1.0

> **Desktop Application per la generazione automatica di Knowledge Base per Agenti AI**

AI Context Studio è un'applicazione desktop moderna che analizza il codice sorgente dei tuoi progetti e genera documentazione strutturata ottimizzata per Agenti AI come Jules, Cursor, Windsurf e GitHub Copilot.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-green.svg)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange.svg)

## 🆕 Changelog v1.1.0
- **Performance 10x** - Scansione ottimizzata con `os.scandir()`
- **File Tree veloce** - Usa `ttk.Treeview` invece di checkbox individuali
- **Non si blocca più** - Threading migliorato per UI sempre reattiva
- **Launcher Windows** - File `.bat` per installazione automatica dipendenze

---

## ✨ Features

### 🔧 Tab 1: Configurazione & Scansione
- **Gestione API Key sicura** con cifratura locale (Fernet)
- **Selettore cartella** per scegliere la root del progetto
- **File Tree interattivo** con possibilità di includere/escludere file
- **Token Estimator** per verificare la compatibilità con la context window di Gemini
- **Filtri automatici** per ignorare node_modules, .git, __pycache__, ecc.

### 🤖 Tab 2: AI Documentation Generator
- **Selezione modello dinamica** - carica automaticamente i modelli disponibili dalla tua API
- **Generatori specializzati**:
  - 🏗️ **AI_ARCHITECTURE.md** - Stack tecnologico, architettura, mappa file
  - 📋 **AI_RULES.md** - Convenzioni di coding, pattern, best practices
  - 📖 **PROJECT_CONTEXT.md** - Obiettivo business, user stories, glossario
  - 📦 **Bundle** - Genera tutti i documenti in una volta
- **Custom Prompting** - Aggiungi istruzioni specifiche per la generazione
- **Progress tracking** con log in tempo reale

### 📝 Tab 3: Preview & Editor
- **Editor Markdown** per rivedere e modificare i documenti generati
- **Contatore token** in tempo reale
- **Salvataggio singolo o batch** nella cartella `docs/` del progetto
- **Copia negli appunti** per uso immediato

---

## 🚀 Installazione

### Prerequisiti
- Python 3.10 o superiore
- Una API Key di Google Gemini ([Ottienila qui](https://makersuite.google.com/app/apikey))

### Setup

```bash
# 1. Clona o scarica il progetto
git clone <repository-url>
cd ai-context-studio

# 2. Installa le dipendenze
pip install -r requirements.txt

# 3. Avvia l'applicazione
python ai_context_studio.py
```

### Dipendenze
```
customtkinter>=5.2.0
google-generativeai>=0.5.0
cryptography>=41.0.0  # Opzionale, per cifratura API Key
```

---

## 📖 Guida Rapida

### 1️⃣ Configura API Key
1. Apri il tab **⚙️ Configurazione**
2. Inserisci la tua Google Gemini API Key
3. Clicca **💾 Salva** per memorizzarla in modo sicuro
4. Clicca **🔌 Test Connessione** per verificare

### 2️⃣ Scansiona il Progetto
1. Clicca **📁 Sfoglia...** e seleziona la cartella root del progetto
2. Clicca **🔍 Scansiona**
3. Usa il File Tree per escludere file non necessari
4. Verifica il **Token Estimator** (idealmente < 80% della context window)

### 3️⃣ Genera Documentazione
1. Vai al tab **🤖 AI Generator**
2. Clicca **🔄 Carica Modelli** per popolare il dropdown
3. Seleziona il modello desiderato (es. `gemini-1.5-pro`)
4. (Opzionale) Espandi le **Istruzioni Custom** per aggiungere direttive
5. Clicca uno dei pulsanti generatore

### 4️⃣ Rivedi e Salva
1. Il tab **📝 Preview & Editor** si aprirà automaticamente
2. Rivedi il contenuto generato
3. Modifica se necessario
4. Clicca **💾 Salva su Disco** o **📦 Salva Tutti**

---

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER (UI)                                                │
│  └── AIContextStudioApp (CustomTkinter MainWindow)                      │
│       ├── ConfigurationTab    → Selezione progetto, filtri, token est.  │
│       ├── GeneratorTab        → Generazione documenti AI                │
│       └── PreviewTab          → Anteprima e salvataggio                 │
├─────────────────────────────────────────────────────────────────────────┤
│  BUSINESS LOGIC LAYER                                                   │
│  ├── GeminiAPIClient          → Comunicazione con Google Gemini         │
│  ├── FileSystemScanner        → Scansione ricorsiva del repository      │
│  ├── TokenEstimator           → Stima token per context window          │
│  └── ConfigManager            → Persistenza configurazioni e API Key    │
├─────────────────────────────────────────────────────────────────────────┤
│  DATA LAYER                                                             │
│  └── Models (dataclasses)     → FileNode, ScanResult, GenerationResult  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Design Patterns
- **Observer Pattern**: Aggiornamenti UI asincroni via UIEventQueue
- **Strategy Pattern**: Diversi tipi di generazione documenti
- **Singleton Pattern**: ConfigManager unico per tutta l'app
- **MVC-like**: Separazione netta UI/Logic/Data

---

## 📁 Output Generato

L'applicazione crea una cartella `docs/` nella root del progetto con:

```
your-project/
├── docs/
│   ├── AI_ARCHITECTURE.md    # Architettura tecnica del progetto
│   ├── AI_RULES.md           # Regole e convenzioni di coding
│   └── PROJECT_CONTEXT.md    # Contesto business e funzionale
└── ...
```

Questi file sono ottimizzati per essere caricati come contesto in:
- **Jules** (Google)
- **Cursor** (AI Code Editor)
- **Windsurf** (Codeium)
- **GitHub Copilot** (Workspace)
- **Claude** (Anthropic Projects)

---

## ⚙️ Configurazione Avanzata

### File di Configurazione
L'app salva le configurazioni in:
- **Linux/Mac**: `~/.ai_context_studio/config.json`
- **Windows**: `%USERPROFILE%\.ai_context_studio\config.json`

### Estensioni Supportate
```python
SUPPORTED_EXTENSIONS = (
    '.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.scss',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
    '.java', '.kt', '.scala', '.cpp', '.c', '.h', '.hpp',
    '.go', '.rs', '.rb', '.php', '.swift',
    '.md', '.rst', '.txt', '.sql', '.graphql', '.proto',
    '.sh', '.bash', '.dockerfile', '.xml'
)
```

### Cartelle Ignorate di Default
```python
DEFAULT_IGNORED_DIRS = {
    '.git', 'node_modules', '__pycache__', 'venv', '.venv',
    '.idea', '.vscode', 'dist', 'build', 'out', 'target',
    '.pytest_cache', '.mypy_cache', 'htmlcov', ...
}
```

---

## 🔐 Sicurezza

- **API Key cifrata** localmente con Fernet (AES-128-CBC)
- **Chiave di cifratura** salvata in file separato con permessi restrittivi (0600)
- **Nessun dato inviato** a server esterni oltre a Google Gemini API
- **Fallback sicuro** se cryptography non è installato (warning)

---

## 🐛 Troubleshooting

### "Nessun modello trovato"
- Verifica che la API Key sia corretta
- Assicurati di avere accesso a Gemini API
- Controlla la connessione internet

### "Token stimati troppo alti"
- Escludi file non necessari dal File Tree
- Ignora cartelle di test o documentazione
- Considera di usare un modello con context window maggiore (es. Gemini 1.5 Pro)

### "Errore generazione"
- Riduci il numero di file inclusi
- Prova con un modello diverso
- Verifica i log per dettagli specifici

---

## 📜 License

MIT License - Vedi file LICENSE per dettagli.

---

## 🙏 Credits

- **Google Gemini API** - Motore AI per la generazione
- **CustomTkinter** - Framework GUI moderno
- **COEMI S.r.l.** - Sviluppo e manutenzione

---

*Creato con ❤️ per rendere ogni repository AI-ready*
