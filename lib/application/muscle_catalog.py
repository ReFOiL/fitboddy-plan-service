"""Fixed muscle dictionary for exercise targeting (display-only)."""

from __future__ import annotations

from typing import Literal

BodyView = Literal["front", "back"]

# slug, name_ru, sort_order, body_view, region_key (SVG zone)
MUSCLE_SEED: list[tuple[str, str, int, BodyView, str]] = [
    # Front — neck / torso
    ("neck", "Шея", 10, "front", "neck"),
    ("traps_upper", "Трапеции (верх)", 20, "front", "traps_upper"),
    ("chest_upper", "Грудь (верх)", 30, "front", "chest"),
    ("chest", "Грудь", 40, "front", "chest"),
    ("chest_lower", "Грудь (низ)", 50, "front", "chest"),
    ("serratus", "Передняя зубчатая", 60, "front", "serratus"),
    ("anterior_deltoid", "Передняя дельта", 70, "front", "shoulders_front"),
    ("lateral_deltoid", "Средняя дельта", 80, "front", "shoulders_front"),
    ("biceps", "Бицепс", 90, "front", "biceps"),
    ("brachialis", "Плечевая мышца", 100, "front", "biceps"),
    ("forearms", "Предплечья", 110, "front", "forearms"),
    ("abs", "Пресс", 120, "front", "abs"),
    ("obliques", "Косые мышцы живота", 130, "front", "obliques"),
    ("hip_flexors", "Сгибатели бедра", 140, "front", "hip_flexors"),
    ("quadriceps", "Квадрицепсы", 150, "front", "quadriceps"),
    ("adductors", "Приводящие бедра", 160, "front", "adductors"),
    ("tibialis", "Передняя большеберцовая", 170, "front", "tibialis"),
    # Back
    ("traps", "Трапеции", 200, "back", "traps"),
    ("traps_mid", "Трапеции (середина)", 210, "back", "traps"),
    ("rear_deltoid", "Задняя дельта", 220, "back", "shoulders_back"),
    ("rhomboids", "Ромбовидные", 230, "back", "rhomboids"),
    ("lats", "Широчайшие", 240, "back", "lats"),
    ("teres", "Круглая мышца спины", 250, "back", "lats"),
    ("lower_back", "Разгибатели спины", 260, "back", "lower_back"),
    ("triceps", "Трицепс", 270, "back", "triceps"),
    ("glutes", "Ягодицы", 280, "back", "glutes"),
    ("hamstrings", "Бицепс бедра", 290, "back", "hamstrings"),
    ("calves", "Икры", 300, "back", "calves"),
    ("soleus", "Камбаловидная", 310, "back", "calves"),
    # Additional / both-view chips (mapped to nearest region)
    ("rotator_cuff", "Вращательная манжета", 320, "back", "shoulders_back"),
    ("pectoralis_minor", "Малая грудная", 330, "front", "chest"),
    ("core", "Кор (стабилизаторы)", 340, "front", "abs"),
    ("abductors", "Отводящие бедра", 350, "front", "quadriceps"),
    ("gastrocnemius", "Икроножная", 360, "back", "calves"),
    ("wrist_flexors", "Сгибатели запястья", 370, "front", "forearms"),
    ("wrist_extensors", "Разгибатели запястья", 380, "back", "forearms"),
    ("levator_scapulae", "Мышца, поднимающая лопатку", 390, "back", "traps"),
    ("infraspinatus", "Подостная", 400, "back", "shoulders_back"),
    ("subscapularis", "Подлопаточная", 410, "front", "shoulders_front"),
    ("brachioradialis", "Плечелучевая", 420, "front", "forearms"),
]

# region_key → default slug when clicking the SVG zone
REGION_DEFAULT_SLUG: dict[str, str] = {
    "neck": "neck",
    "traps_upper": "traps_upper",
    "chest": "chest",
    "serratus": "serratus",
    "shoulders_front": "anterior_deltoid",
    "biceps": "biceps",
    "forearms": "forearms",
    "abs": "abs",
    "obliques": "obliques",
    "hip_flexors": "hip_flexors",
    "quadriceps": "quadriceps",
    "adductors": "adductors",
    "tibialis": "tibialis",
    "traps": "traps",
    "shoulders_back": "rear_deltoid",
    "rhomboids": "rhomboids",
    "lats": "lats",
    "lower_back": "lower_back",
    "triceps": "triceps",
    "glutes": "glutes",
    "hamstrings": "hamstrings",
    "calves": "calves",
}

MUSCLE_SLUGS: frozenset[str] = frozenset(item[0] for item in MUSCLE_SEED)


def is_known_muscle_slug(slug: str) -> bool:
    return slug in MUSCLE_SLUGS
