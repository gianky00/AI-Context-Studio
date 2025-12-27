# -*- coding: utf-8 -*-
"""AI Context Studio - Windows GUI Launcher."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Start app
from ai_context_studio.main import main
main()
