"""
Clause detection for regulatory and legal documents.

Uses regex patterns for known clause types (definitions, obligations,
penalties, etc.) with an optional ML classifier for ambiguous regions.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from regulaforge.document_intelligence.domain.enums import ClauseType
from regulaforge.document_intelligence.domain.models import IdentifiedClause

DEFINITION_PATTERNS: list[str] = [
    r"(?i)(?:in this (?:regulation|directive|order|act|notification))",
    r"(?i)(?:for the purposes of this)",
    r"(?i)(?:the following terms shall)",
    r"(?i)(?:unless the context otherwise requires)",
    r"(?i)^\s*(?:definition|interpretation)",
]

CLAUSE_PATTERNS: dict[ClauseType, list[str]] = {
    ClauseType.DEFINITION: DEFINITION_PATTERNS + [
        r"(?i)^\s*(\"|'|`)(?:\w+\s*)+\1\s+means\s+",
        r"(?i)(?:means\s+a\s+n?|shall mean)",
        r"(?i)(?:shall\s+have\s+the\s+meaning\s+assigned)",
        r"(?i)(?:as defined in (?:section|regulation|clause|paragraph))",
    ],
    ClauseType.OBLIGATION: [
        r"(?i)(?:shall\s+(?:ensure|comply|maintain|provide|submit|obtain|notify|report))",
        r"(?i)(?:must\s+(?:ensure|comply|maintain|provide|submit|obtain))",
        r"(?i)(?:is\s+(?:required|obliged|bound)\s+to)",
        r"(?i)(?:it shall be the duty of)",
        r"(?i)(?:every\s+\w+\s+shall)",
    ],
    ClauseType.PROHIBITION: [
        r"(?i)(?:shall not\s+(?:engage|act|do|enter|make|use))",
        r"(?i)(?:no\s+\w+\s+shall)",
        r"(?i)(?:prohibited from)",
        r"(?i)(?:shall not be (?:permitted|allowed|entitled))",
    ],
    ClauseType.PENALTY: [
        r"(?i)(?:penalty|punishable|fine|imprisonment)",
        r"(?i)(?:shall be liable to)",
        r"(?i)(?:shall be punishable with)",
        r"(?i)(?:not exceeding)\s+(?:rupees|rs\.?|₹)",
        r"(?i)(?:offence under this)",
    ],
    ClauseType.COMPLIANCE: [
        r"(?i)(?:compliance\s+(?:with|of|report|officer|audit))",
        r"(?i)(?:conform(?:ity|ance)\s+(?:with|to))",
        r"(?i)(?:adherence\s+to)",
        r"(?i)(?:meeting the requirements)",
    ],
    ClauseType.REPORTING: [
        r"(?i)(?:shall\s+(?:submit|file|furnish|report|send|provide)\s+(?:to|the\s+board|the\s+authority))",
        r"(?i)(?:shall\s+(?:disclose|publish|notify))",
        r"(?i)(?:reporting\s+(?:requirements|obligations|frequency|period))",
        r"(?i)(?:filing\s+(?:of|deadline|requirements))",
    ],
    ClauseType.EFFECTIVE_DATE: [
        r"(?i)(?:this (?:regulation|directive|order|notification) shall come into force)",
        r"(?i)(?:effective\s+(?:from|date|on))",
        r"(?i)(?:shall\s+(?:take|come into)\s+effect)",
        r"(?i)(?:within\s+\d+\s+(?:day|month|year)s?\s+from)",
    ],
    ClauseType.AMENDMENT: [
        r"(?i)(?:substituted?|inserted?|omitted?|amended?)",
        r"(?i)(?:for the words|shall be substituted)",
        r"(?i)(?:the following shall be inserted)",
        r"(?i)(?:in the said (?:regulation|section|clause))",
    ],
    ClauseType.REPEAL: [
        r"(?i)(?:repealed?|revoked?|withdrawn?)",
        r"(?i)(?:is hereby repealed)",
        r"(?i)(?:shall cease to have effect)",
    ],
    ClauseType.SAVINGS: [
        r"(?i)(?:notwithstanding (?:such|the|any) repeal)",
        r"(?i)(?:savings\s+(?:provision|clause))",
        r"(?i)(?:shall not affect)",
        r"(?i)(?:anything done or omitted)",
    ],
}

COMMON_HEADINGS: dict[str, ClauseType] = {
    "definitions": ClauseType.DEFINITION,
    "interpretation": ClauseType.DEFINITION,
    "obligations": ClauseType.OBLIGATION,
    "prohibitions": ClauseType.PROHIBITION,
    "penalties": ClauseType.PENALTY,
    "penalty": ClauseType.PENALTY,
    "compliance": ClauseType.COMPLIANCE,
    "reporting": ClauseType.REPORTING,
    "amendments": ClauseType.AMENDMENT,
    "amendment": ClauseType.AMENDMENT,
    "repeal": ClauseType.REPEAL,
    "repeals": ClauseType.REPEAL,
    "savings": ClauseType.SAVINGS,
    "definitions and interpretation": ClauseType.DEFINITION,
}


@dataclass
class ClauseResult:
    clauses: list[IdentifiedClause] = field(default_factory=list)
    overall_confidence: float = 0.0


class ClauseDetector(ABC):
    @abstractmethod
    async def detect(
        self, text: str, section_boundaries: list[tuple[int, int, str]] | None = None,
        **kwargs: Any
    ) -> ClauseResult:
        """Detect clauses in document text.

        Args:
            text: Full document text.
            section_boundaries: Optional list of (start, end, heading) tuples.
            kwargs: Detector-specific options.

        Returns:
            A ``ClauseResult`` with identified clauses.
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class RegexClauseDetector(ClauseDetector):
    """Detects clauses using regex patterns and optional heading-based
    classification."""

    def __init__(self, min_confidence: float = 0.5) -> None:
        self._min_confidence = min_confidence
        self._compiled: dict[ClauseType, list[re.Pattern]] = {}
        self._available: bool = True

    @property
    def name(self) -> str:
        return "regex"

    async def is_available(self) -> bool:
        return True

    def _compile(self) -> None:
        if self._compiled:
            return
        for ct, patterns in CLAUSE_PATTERNS.items():
            self._compiled[ct] = [re.compile(p) for p in patterns]

    async def detect(
        self, text: str,
        section_boundaries: list[tuple[int, int, str]] | None = None,
        **kwargs: Any
    ) -> ClauseResult:
        self._compile()

        clauses: list[IdentifiedClause] = []

        if section_boundaries:
            for start, end, heading in section_boundaries:
                heading_key = heading.strip().lower()
                if heading_key in COMMON_HEADINGS:
                    ct = COMMON_HEADINGS[heading_key]
                    clauses.append(
                        IdentifiedClause(
                            id=f"cl-{len(clauses) + 1}",
                            clause_type=ct,
                            text=text[start:end].strip()[:200],
                            confidence=0.9,
                            metadata={"heading": heading, "start": start, "end": end},
                        )
                    )

        for ct, patterns in self._compiled.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    match_start = max(0, match.start() - 50)
                    match_end = min(len(text), match.end() + 200)
                    sentence_boundary = text.find(". ", match_end - 50)
                    if sentence_boundary != -1:
                        match_end = sentence_boundary + 1

                    clause_text = text[match_start:match_end].strip()
                    if any(existing.text == clause_text for existing in clauses):
                        continue

                    clauses.append(
                        IdentifiedClause(
                            id=f"cl-{len(clauses) + 1}",
                            clause_type=ct,
                            text=clause_text[:200],
                            confidence=0.6,
                            metadata={
                                "pattern": str(pattern.pattern[:60]),
                                "start": match.start(),
                                "end": match_end if match_end <= len(text) else len(text),
                            },
                        )
                    )

        overall_conf = (
            sum(c.confidence for c in clauses) / len(clauses)
            if clauses
            else 0.0
        )
        return ClauseResult(clauses=clauses, overall_confidence=overall_conf)
