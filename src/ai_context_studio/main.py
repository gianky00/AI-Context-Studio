#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Context Studio - Entry Point.

This module provides the main entry point for running the application.
It sets up logging and launches the GUI.
"""

from __future__ import annotations

import logging
import sys

from .constants import APP_AUTHOR, APP_NAME, APP_VERSION


def setup_logging(debug: bool = False) -> None:
    """
    Configure application logging.

    Args:
        debug: If True, set log level to DEBUG.
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    logger = logging.getLogger(__name__)
    missing: list[str] = []

    try:
        import customtkinter  # noqa: F401
    except ImportError:
        missing.append("customtkinter")
        logger.error("CustomTkinter not found. Install with: pip install customtkinter")

    try:
        import google.generativeai  # noqa: F401
    except ImportError:
        missing.append("google-generativeai")
        logger.error("Google Generative AI not found. Install with: pip install google-generativeai")

    if missing:
        logger.error("Missing dependencies: %s", ", ".join(missing))
        return False

    return True


def print_banner() -> None:
    """Print application banner."""
    print(f"""
{'=' * 60}
  {APP_NAME} v{APP_VERSION}
  by {APP_AUTHOR}
{'=' * 60}
""")


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    debug = "--debug" in sys.argv or "-d" in sys.argv

    setup_logging(debug=debug)
    logger = logging.getLogger(__name__)

    print_banner()

    if not check_dependencies():
        logger.error("Cannot start: missing required dependencies")
        return 1

    try:
        from .app import AIContextStudioApp

        logger.info("Launching application")
        app = AIContextStudioApp()
        app.mainloop()
        logger.info("Application closed normally")
        return 0

    except Exception as e:
        logger.exception("Fatal error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
