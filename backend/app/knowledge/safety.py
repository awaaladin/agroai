"""Output audit against safety.yaml: banned chemicals, dosages, and missing safety wording.

The prompt asks the model to follow these rules; this module checks that it did, so a bad answer is
never shown to a farmer.
"""
import re

from app.knowledge import load_safety, snapshot
from app.schemas.diagnose import Diagnosis


_regex_cache: dict[int, tuple[re.Pattern, list[re.Pattern]]] = {}


def _regexes() -> tuple[re.Pattern, list[re.Pattern]]:
    """Compiled banned-name and dosage patterns for the current knowledge snapshot (rebuilt when it reloads)."""
    snap = snapshot()
    if snap.version not in _regex_cache:
        _regex_cache.clear()
        names = sorted(snap.safety["banned"], key=len, reverse=True)
        #  is not enough for names like "methyl parathion"; allow flexible whitespace/hyphens.
        parts = [re.escape(n).replace(r"\ ", r"[\s-]+") for n in names]
        banned = re.compile(r"(?<![a-z])(?:" + "|".join(parts) + r")(?![a-z])", re.I) if parts else re.compile(r"(?!x)x")
        _regex_cache[snap.version] = (banned, [re.compile(p, re.I) for p in snap.safety["dosage_patterns"]])
    return _regex_cache[snap.version]


def _contains_any(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(t.lower() in low for t in terms)


def audit_text(text: str) -> list[str]:
    """Return a list of human-readable violations (empty means the text is safe)."""
    safety = load_safety()
    problems: list[str] = []
    banned_rx, dosage_rxs = _regexes()
    for m in banned_rx.finditer(text):
        problems.append(f"mentions banned or restricted pesticide '{m.group(0)}'")
    for rx in dosage_rxs:
        m = rx.search(text)
        if m:
            problems.append(f"gives a dose or amount ('{m.group(0)}')")
    if _contains_any(text, safety["chemical_trigger_terms"]):
        if not _contains_any(text, safety["required_label_terms"]):
            problems.append("mentions chemicals without telling the farmer to follow the label")
        if not _contains_any(text, safety["required_protection_terms"]):
            problems.append("mentions chemicals without protective-gear or re-entry advice")
    return list(dict.fromkeys(problems))  # de-duplicate, keep order


def diagnosis_text(d: Diagnosis) -> str:
    """Everything a farmer could read or hear from a diagnosis, as one string."""
    a = d.assessment
    parts = [a.likely_problem, a.what_i_see, a.why_i_think_so, a.what_could_change_my_mind, d.spoken_text]
    parts += [x.what + " " + x.why for x in d.actions]
    parts += d.prevention + d.farmer_questions
    return "\n".join(parts)


def audit_diagnosis(d: Diagnosis) -> list[str]:
    return audit_text(diagnosis_text(d))
