# -*- coding: utf-8 -*-
"""AI Context Studio - Windows GUI Launcher."""
import sys
from pathlib import Path

# Add src to path so the package is importable without installation.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_context_studio.main import main

if __name__ == "__main__":
    raise SystemExit(main())
