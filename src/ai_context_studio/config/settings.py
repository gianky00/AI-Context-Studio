from pathlib import Path

APP_NAME = "AI Context Studio"
APP_VERSION = "1.1.0"
APP_AUTHOR = "Giancarlo Allegretti"

# Estensioni file supportate per l'analisi
SUPPORTED_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.scss', '.sass',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
    '.java', '.kt', '.scala', '.cpp', '.c', '.h', '.hpp',
    '.go', '.rs', '.rb', '.php', '.swift', '.m',
    '.md', '.rst', '.txt', '.sql', '.graphql', '.proto',
    '.sh', '.bash', '.zsh', '.ps1', '.bat', '.cmd',
    '.xml', '.xsl', '.xslt'
}

# Cartelle da ignorare di default
DEFAULT_IGNORED_DIRS = {
    '.git', '.svn', '.hg',
    'node_modules', 'bower_components',
    '__pycache__', '.pytest_cache', '.mypy_cache',
    'venv', '.venv', 'env', '.env',
    '.idea', '.vscode', '.vs',
    'dist', 'build', 'out', 'target',
    '.tox', '.nox', 'htmlcov', '.coverage',
    'eggs', '.eggs',
    '.terraform', '.serverless',
    'vendor', 'packages',
}

# Path per configurazione locale
CONFIG_DIR = Path.home() / ".ai_context_studio"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEY_FILE = CONFIG_DIR / ".keyfile"

# Fattore approssimativo per stima token
TOKEN_FACTOR = 4
