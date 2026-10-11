"""Map local and English crop names (akpu, isu, oka, corn...) to crop keys, using the aliases stored in the database."""
from app.knowledge import load_aliases


def normalize_crop(name: str | None) -> str | None:
    """Known crops return their key; anything else stays as lower-case text so the AI can still try."""
    if not name or not name.strip():
        return None
    cleaned = name.strip().lower()
    return load_aliases().get(cleaned, cleaned)
