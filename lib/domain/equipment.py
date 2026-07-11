from __future__ import annotations

import re

_NAME_RE = re.compile(r"^[\w](?:[\w \-']{0,62}[\w])?$", re.UNICODE)

CANONICAL_EQUIPMENT: tuple[tuple[str, str], ...] = (
    ("dumbbells", "Гантели"),
    ("barbell", "Штанга"),
    ("kettlebell", "Гиря"),
    ("resistance_bands", "Эспандеры / резинки"),
    ("treadmill", "Беговая дорожка"),
)

CANONICAL_EQUIPMENT_VALUES = {value for value, _label in CANONICAL_EQUIPMENT}


def normalize_equipment_name(raw: str) -> str | None:
    """Normalize to a canonical slug or a cleaned custom display name."""
    value = " ".join(raw.strip().split())
    if not value:
        return None

    folded = value.casefold()
    if folded == "none":
        return None

    for slug, label in CANONICAL_EQUIPMENT:
        if folded == slug.casefold() or folded == label.casefold():
            return slug

    if len(value) < 2 or len(value) > 64:
        return None
    if not _NAME_RE.fullmatch(value):
        return None
    return value


def normalize_equipment_list(items: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = normalize_equipment_name(item)
        if value is None:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def is_valid_exercise_equipment(raw: str) -> bool:
    value = " ".join(raw.strip().split())
    if value.casefold() == "none":
        return True
    return normalize_equipment_name(value) is not None


def equipment_match_key(raw: str) -> str:
    value = " ".join((raw or "").strip().split())
    if not value:
        return "none"
    name = normalize_equipment_name(value)
    if name is not None:
        return name.casefold()
    if value.casefold() == "none":
        return "none"
    return value.casefold()


# Back-compat alias
normalize_equipment_slug = normalize_equipment_name
