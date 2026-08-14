#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allow running as a module: python -m ai_context_studio
"""

from __future__ import annotations

from . import main

if __name__ == "__main__":
    raise SystemExit(main.main())
