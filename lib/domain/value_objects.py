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
    RESISTANCE_BANDS = "resistance_bands"
    KETTLEBELL = "kettlebell"
    TREADMILL = "treadmill"
    OTHER = "other"

    @classmethod
    def from_raw(cls, raw: str | "EquipmentName" | None) -> "EquipmentName | None":
        if isinstance(raw, EquipmentName):
            return raw
        normalized = (raw or "").strip().lower()
        for item in cls:
            if item.value == normalized:
                return item
        return None
