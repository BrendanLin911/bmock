"""Shared result types and the config loader."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import yaml

SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2, "good": 3}
DEFAULT_RULES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules.yaml")


class Config:
    """Thin dotted-path accessor over rules.yaml."""

    def __init__(self, data: Dict[str, Any], path: str = ""):
        self.data = data
        self.path = path

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        path = path or os.environ.get("VMOCK_RULES") or DEFAULT_RULES
        with open(path, encoding="utf-8") as f:
            return cls(yaml.safe_load(f), path)

    def get(self, dotted: str, default=None):
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node



@dataclass
class Finding:
    severity: str                  # error | warn | info | good
    message: str
    points_lost: float = 0.0
    evidence: str = ""
    fix: str = ""
    line_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SubScore:
    key: str
    label: str
    points: float
    max_points: float
    findings: List[Finding] = field(default_factory=list)
    detail: Dict[str, Any] = field(default_factory=dict)
    children: List["SubScore"] = field(default_factory=list)
    # VMock's own chip ("Good Job!" / "On Track!" / "Needs Work!"). Set
    # explicitly where observed; otherwise derived from the ratio.
    status: Optional[str] = None

    @property
    def ratio(self) -> float:
        return 0.0 if self.max_points <= 0 else self.points / self.max_points

    @property
    def derived_status(self) -> str:
        r = self.ratio
        return "Good Job!" if r >= 0.85 else "On Track!" if r >= 0.5 else "Needs Work!"

    @property
    def all_findings(self) -> List[Finding]:
        """This sub-score's findings plus every descendant's."""
        out = list(self.findings)
        for c in self.children:
            out.extend(c.all_findings)
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "points": round(self.points, 2),
            "max_points": round(self.max_points, 2),
            "ratio": round(self.ratio, 4),
            "status": self.status or self.derived_status,
            "findings": [f.to_dict() for f in self.findings],
            "children": [c.to_dict() for c in self.children],
            "detail": self.detail,
        }


@dataclass
class ModuleScore:
    key: str
    label: str
    points: float
    max_points: float
    subscores: List[SubScore] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)   # module-level

    @property
    def all_findings(self) -> List[Finding]:
        out = list(self.findings)
        for s in self.subscores:
            out.extend(s.all_findings)
        return sorted(out, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), -f.points_lost))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "points": round(self.points, 2),
            "max_points": round(self.max_points, 2),
            "ratio": round(0.0 if self.max_points <= 0 else self.points / self.max_points, 4),
            "subscores": [s.to_dict() for s in self.subscores],
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class BulletFeedback:
    """The six per-bullet parameters VMock names in its own guides."""

    index: int
    text: str
    section: str
    action_oriented: bool = False
    verb: str = ""
    verb_tier: str = "none"
    active_voice: bool = True
    specifics: bool = False
    quantifiers: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    overusage: List[str] = field(default_factory=list)
    filler_words: List[str] = field(default_factory=list)
    word_count: int = 0
    length_ok: bool = True
    flags: List[str] = field(default_factory=list)
    # Where the bullet sits on the page, in PDF points, so the UI can pin
    # feedback to the line it came from.
    page: int = 0
    top: float = 0.0
    bottom: float = 0.0
    x0: float = 0.0
    x1: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def clamp(value: float, lo: float = 0.0, hi: float = None) -> float:
    value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def reconcile_subscore(sub: SubScore) -> None:
    """Make each finding's `points_lost` sum to the points actually deducted.

    Sub-scores compute their total with one formula and emit findings with
    another, so the two drift apart. That matters because the UI presents
    `points_lost` as "+N points available" -- an advertised win the user cannot
    actually collect is worse than no advice at all. Rescale the claims to the
    real deficit, preserving their relative sizes.
    """
    for child in sub.children:
        reconcile_subscore(child)

    if sub.children:
        # A parent's score is its children's; only its own findings need fixing.
        deficit = 0.0
    else:
        deficit = max(0.0, sub.max_points - sub.points)

    claims = [f for f in sub.findings if f.points_lost > 0]
    claimed = sum(f.points_lost for f in claims)
    if not claims:
        return
    if deficit <= 0:
        for f in claims:
            f.points_lost = 0.0
        return
    scale = deficit / claimed if claimed > 0 else 0.0
    for f in claims:
        f.points_lost = round(f.points_lost * scale, 3)


def reconcile_module(mod: ModuleScore) -> None:
    for sub in mod.subscores:
        reconcile_subscore(sub)
    # Module-level penalties (the phone-parenthesis deduction) are applied after
    # the sub-scores are summed and are clamped at zero, so what they really
    # cost is the gap between the sub-score total and the module total.
    extra = max(0.0, sum(s.points for s in mod.subscores) - mod.points)
    claims = [f for f in mod.findings if f.points_lost > 0]
    claimed = sum(f.points_lost for f in claims)
    if not claims:
        return
    if extra <= 0 or claimed <= 0:
        for f in claims:
            f.points_lost = 0.0
        return
    for f in claims:
        f.points_lost = round(f.points_lost * (extra / claimed), 3)
