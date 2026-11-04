"""
The structuring manual handed to the model in pass 2 (``structuring_manual.md``).

Each top-level heading of the manual is one block: ``Guardrails`` (always sent),
one block per top-level schema section, and ``findings index``. Only the blocks a
call needs are sent, so each prompt carries the rules for exactly the fields it
asks for.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable

MANUAL_PATH = Path(__file__).resolve().parent / "structuring_manual.md"

GUARDRAILS = "Guardrails"
FINDINGS_INDEX = "findings index"


@lru_cache(maxsize=None)
def blocks() -> Dict[str, str]:
    """``{heading: body}`` for every top-level heading (text before the first is the maintainers' note)."""
    text = MANUAL_PATH.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^# (.+?)\s*$", text)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def guardrails() -> str:
    return blocks()[GUARDRAILS]


def field_guide(sections: Iterable[str]) -> str:
    """Field guidance for the given top-level schema sections."""
    return "\n\n".join(f"{name}:\n{blocks()[name]}" for name in sections)
