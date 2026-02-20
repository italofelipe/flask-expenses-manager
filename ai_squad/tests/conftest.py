"""
Pytest configuration for ai_squad tests.

Adds ai_squad/ to sys.path so that 'from tools.tool_security import ...'
works regardless of where pytest is invoked from.
"""

import sys
from pathlib import Path

_AI_SQUAD_DIR = Path(__file__).resolve().parent.parent
if str(_AI_SQUAD_DIR) not in sys.path:
    sys.path.insert(0, str(_AI_SQUAD_DIR))
