from __future__ import annotations

from enum import IntEnum, StrEnum


class TrainingLevel(IntEnum):
    BEGINNER = 2
    INTERMEDIATE = 3
    ADVANCED = 4

    @classmethod
    def from_raw(cls, raw: str | "TrainingLevel" | None) -> "TrainingLevel":
        if isinstance(raw, TrainingLevel):
            return raw
        mapping = {
            "beginner": cls.BEGINNER,
            "intermediate": cls.INTERMEDIATE,
            "advanced": cls.ADVANCED,
        }
        return mapping.get((raw or "").strip().lower(), cls.INTERMEDIATE)

    def as_name(self) -> "TrainingLevelName":
        return {
            TrainingLevel.BEGINNER: TrainingLevelName.BEGINNER,
            TrainingLevel.INTERMEDIATE: TrainingLevelName.INTERMEDIATE,
            TrainingLevel.ADVANCED: TrainingLevelName.ADVANCED,
        }[self]


class TrainingLevelName(StrEnum):
    """String level keys used in generation policy storage/API."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

    @classmethod
    def from_raw(cls, raw: str | "TrainingLevelName" | None) -> "TrainingLevelName | None":
        if isinstance(raw, TrainingLevelName):
            return raw
        normalized = (raw or "").strip().lower()
        for item in cls:
            if item.value == normalized:
                return item
        return None


class WorkoutCategory(StrEnum):
    UPPER = "upper"
    LOWER = "lower"
    CORE = "core"
    FULL_BODY = "full_body"

    @classmethod
    def from_raw(cls, raw: str | "WorkoutCategory" | None) -> "WorkoutCategory | None":
        if isinstance(raw, WorkoutCategory):
            return raw
        normalized = (raw or "").strip().lower()
        for item in cls:
            if item.value == normalized:
                return item
        return None


class SessionBoundSlot(StrEnum):
    DEFAULT = "default"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    REHABILITATION = "rehabilitation"

    @classmethod
    def from_raw(cls, raw: str | "SessionBoundSlot" | None) -> "SessionBoundSlot | None":
        if isinstance(raw, SessionBoundSlot):
            return raw
        normalized = (raw or "").strip().lower()
        for item in cls:
            if item.value == normalized:
                return item
        return None


class WorkoutLocation(StrEnum):
    HOME = "home"
    GYM = "gym"
    BOTH = "both"

    @classmethod
    def from_raw(cls, raw: str | "WorkoutLocation" | None) -> "WorkoutLocation | None":
        if isinstance(raw, WorkoutLocation):
            return raw
        normalized = (raw or "").strip().lower()
        for item in cls:
            if item.value == normalized:
                return item
        return None


class TrainingGoal(StrEnum):
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    ENDURANCE = "endurance"
    MAINTENANCE = "maintenance"
    REHABILITATION = "rehabilitation"

    @classmethod
    def from_raw(cls, raw: str | "TrainingGoal" | None) -> "TrainingGoal":
        if isinstance(raw, TrainingGoal):
            return raw
        normalized = (raw or "").strip().lower()
        for item in cls:
            if item.value == normalized:
                return item
        return cls.MAINTENANCE


class EquipmentName(StrEnum):
    NONE = "none"
    DUMBBELLS = "dumbbells"
    BARBELL = "barbell"
    KETTLEBELL = "kettlebell"
    RESISTANCE_BANDS = "resistance_bands"
    TREADMILL = "treadmill"

    @classmethod
    def from_raw(cls, raw: str | "EquipmentName" | None) -> "EquipmentName | None":
        if isinstance(raw, EquipmentName):
            return raw
        normalized = (raw or "").strip().lower()
        for item in cls:
            if item.value == normalized:
                return item
        return None
