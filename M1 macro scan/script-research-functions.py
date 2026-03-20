#!/usr/bin/env python3
"""Compatibility entrypoint for research helper functions."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.research_app.scans.macro_scan import (
    API_FUNCTIONS,
    invoke_api_function,
    main,
    research_macro_scan,
)

__all__ = [
    "API_FUNCTIONS",
    "invoke_api_function",
    "main",
    "research_macro_scan",
]


if __name__ == "__main__":
    main()
