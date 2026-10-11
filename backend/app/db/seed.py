"""First-run seeding. The YAML files in app/db/seed/ are only the starting rows: once the tables have data the
database is the source of truth, and seeding never overwrites it (edit rows in the database, then reload).
"""
from pathlib import Path

import yaml
from sqlalchemy import func, select

from app.db.models import Crop, CropAlias, CropProblem, Region, SafetyTerm

SEED_DIR = Path(__file__).parent / "seed"

# Extra names farmers use that are not already in a crop's local_names (alias -> crop key).
EXTRA_ALIASES = {
    "garri": "cassava", "manioc": "cassava", "coco yam": "cocoyam", "banana": "plantain", "corn": "maize",
    "chilli": "pepper", "chili": "pepper", "ata": "pepper",
}

# safety.yaml key -> SafetyTerm.kind (lists of strings)
LIST_KINDS = {
    "banned": "banned", "dosage_patterns": "dosage_pattern", "chemical_trigger_terms": "chemical_trigger",
    "required_label_terms": "required_label", "required_protection_terms": "required_protection",
}


def read_seed() -> tuple[dict, dict]:
    crops = yaml.safe_load((SEED_DIR / "crops.yaml").read_text(encoding="utf-8"))
    safety = yaml.safe_load((SEED_DIR / "safety.yaml").read_text(encoding="utf-8"))
    return crops, safety


async def seed_if_empty(db) -> None:
    crops_data, safety_data = read_seed()
    async with db.session() as s:
        if (await s.scalar(select(func.count()).select_from(Crop))) == 0:
            for k, v in crops_data["region"].items():
                s.add(Region(key=k, value=str(v)))
            seen_aliases: set[str] = set()
            for key, c in crops_data["crops"].items():
                s.add(Crop(key=key, local_names=c["local_names"], growth_stages=c["growth_stages"],
                           planting_calendar=c["planting_calendar"]))
                for i, p in enumerate(c["common_problems"]):
                    s.add(CropProblem(crop_key=key, position=i, name=p["name"], type=p["type"],
                                      serious=bool(p["serious"]), signs=p["signs"], low_cost_actions=p["low_cost_actions"]))
                for name in [key, *c["local_names"]]:
                    if name.lower() not in seen_aliases:
                        seen_aliases.add(name.lower())
                        s.add(CropAlias(alias=name.lower(), crop_key=key))
            for alias, key in EXTRA_ALIASES.items():
                if key in crops_data["crops"] and alias not in seen_aliases:
                    seen_aliases.add(alias)
                    s.add(CropAlias(alias=alias, crop_key=key))
        if (await s.scalar(select(func.count()).select_from(SafetyTerm))) == 0:
            for yaml_key, kind in LIST_KINDS.items():
                for i, value in enumerate(safety_data[yaml_key]):
                    s.add(SafetyTerm(kind=kind, value=value, position=i))
            for i, v in enumerate(safety_data["allowed"]["classes"]):
                s.add(SafetyTerm(kind="allowed_class", value=v, position=i))
            for i, v in enumerate(safety_data["allowed"]["active_ingredients"]):
                s.add(SafetyTerm(kind="allowed_ingredient", value=v, position=i))
            for i, v in enumerate(safety_data["out_of_scope"]["decline"]):
                s.add(SafetyTerm(kind="scope_decline", value=v, position=i))
            for i, v in enumerate(safety_data["out_of_scope"]["refer_to_professional"]):
                s.add(SafetyTerm(kind="scope_refer", value=v, position=i))
        await s.commit()
