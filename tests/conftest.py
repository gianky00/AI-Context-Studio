import sys
from pathlib import Path

# Aggiungi src al path per facilitare i test senza installazione
sys.path.append(str(Path(__file__).parent.parent / "src"))
