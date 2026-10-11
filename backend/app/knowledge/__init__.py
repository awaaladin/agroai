"""Crop and safety knowledge. The database is the source of truth; this module holds a snapshot of it in memory.

The snapshot is loaded when the app is ready (and refreshed every KNOWLEDGE_REFRESH_SECONDS), so prompts and the
safety audit stay fast and synchronous while edits made in the database still reach the running app.
Shapes are plain dicts so the prompt and audit code do not care where the data came from.
"""
from dataclasses import dataclass, field

from sqlalchemy import select


@dataclass
class Snapshot:
    crops: dict  # {"region": {...}, "crops": {key: {local_names, growth_stages, planting_calendar, common_problems}}}
    safety: dict
    aliases: dict[str, str] = field(default_factory=dict)  # lower-case alias -> crop key
    version: int = 0


_current: Snapshot | None = None
_counter = 0


def set_snapshot(crops: dict, safety: dict, aliases: dict[str, str]) -> Snapshot:
    global _current, _counter
    _counter += 1
    _current = Snapshot(crops=crops, safety=safety, aliases=aliases, version=_counter)
    return _current


def snapshot() -> Snapshot:
    if _current is None:
        raise RuntimeError("Knowledge is not loaded yet: the database must be ready first (Database.ensure_ready).")
    return _current


def load_crops() -> dict:
    return snapshot().crops


def load_safety() -> dict:
    return snapshot().safety


def load_aliases() -> dict[str, str]:
    return snapshot().aliases


def crop_entry(name: str | None) -> dict | None:
    """The knowledge entry for an MVP crop key, or None for any other crop."""
    if not name:
        return None
    return load_crops()["crops"].get(name.lower())


def is_known_crop(name: str | None) -> bool:
    return crop_entry(name) is not None


async def reload_knowledge(db) -> Snapshot:
    """Read the knowledge tables and replace the in-memory snapshot."""
    from app.db.models import Crop, CropAlias, Region, SafetyTerm

    async with db.session() as s:
        region = {r.key: r.value for r in (await s.scalars(select(Region))).all()}
        crops = {}
        for c in (await s.scalars(select(Crop))).all():
            crops[c.key] = {
                "local_names": list(c.local_names), "growth_stages": list(c.growth_stages),
                "planting_calendar": c.planting_calendar,
                "common_problems": [{"name": p.name, "type": p.type, "serious": p.serious, "signs": p.signs,
                                     "low_cost_actions": p.low_cost_actions} for p in c.problems],
            }
        aliases = {a.alias: a.crop_key for a in (await s.scalars(select(CropAlias))).all()}
        terms: dict[str, list[str]] = {}
        for t in (await s.scalars(select(SafetyTerm).order_by(SafetyTerm.kind, SafetyTerm.position))).all():
            terms.setdefault(t.kind, []).append(t.value)
    safety = {
        "banned": terms.get("banned", []),
        "allowed": {"classes": terms.get("allowed_class", []), "active_ingredients": terms.get("allowed_ingredient", [])},
        "dosage_patterns": terms.get("dosage_pattern", []),
        "chemical_trigger_terms": terms.get("chemical_trigger", []),
        "required_label_terms": terms.get("required_label", []),
        "required_protection_terms": terms.get("required_protection", []),
        "out_of_scope": {"decline": terms.get("scope_decline", []), "refer_to_professional": terms.get("scope_refer", [])},
    }
    return set_snapshot({"region": region, "crops": crops}, safety, aliases)
