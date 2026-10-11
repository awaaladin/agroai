"""Plain-text summary a farmer can send to an extension officer (WhatsApp/SMS). Deterministic: no AI, no image."""
from app.schemas.common import Language
from app.services.session_store import Session

_CONF_WORDS = [(0.8, "sure"), (0.6, "fairly sure"), (0.0, "not sure")]


def confidence_word(c: float) -> str:
    return next(word for floor, word in _CONF_WORDS if c >= floor)


def build_share_card(session: Session) -> str:
    """Written in English for the officer. Location is the session's already-rounded (~1 km) position."""
    d = session.diagnosis
    if d is None:
        raise ValueError("no diagnosis in this session")
    a = d.assessment
    lines = ["AgroAI Advisor: crop check", f"Crop: {d.crop.name}"]
    if session.lat is not None and session.lon is not None:
        lines.append(f"Location (about 1 km): {session.lat:.2f}, {session.lon:.2f}")
    lines.append(f"Likely problem: {a.likely_problem} ({confidence_word(a.confidence)}, {round(a.confidence * 100)}%)")
    if a.alternatives:
        lines.append("Other possibilities: " + ", ".join(x.name for x in a.alternatives))
    if session.symptoms_text:
        lines.append(f"Farmer observed: {session.symptoms_text.strip()}")
    lines.append(f"What the app saw: {a.what_i_see}")
    if d.escalate.recommended and d.escalate.reason:
        lines.append(f"Why I am sending this: {d.escalate.reason}")
    if d.farmer_questions:
        lines.append("Questions for the officer / to check on the farm:")
        lines += [f"{i}. {q}" for i, q in enumerate(d.farmer_questions, 1)]
    lines.append("This is an AI suggestion, not a final diagnosis. Please confirm.")
    return "\n".join(lines)
