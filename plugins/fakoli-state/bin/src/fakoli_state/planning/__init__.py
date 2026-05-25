"""fakoli-state.planning — PRD template parser and rule-based scoring engine.

Public surface:
- ``template`` — deterministic markdown PRD parser; no LLM, no I/O.
- ``scoring``  — six-dimension rule-based scorer; no LLM, no I/O.
- ``llm``      — Phase 7 LLM provider abstraction (Protocol + Anthropic impl
  + Recorded test double).  Augmentation only — never required.
"""

from __future__ import annotations

import fakoli_state.planning.llm as llm
import fakoli_state.planning.scoring as scoring
import fakoli_state.planning.template as template

__all__ = ["template", "scoring", "llm"]
