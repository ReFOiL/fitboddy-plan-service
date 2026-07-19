from __future__ import annotations

import json
from dataclasses import dataclass, field


_ALLOWED_CATEGORIES = {"upper", "lower", "core", "full_body"}
_ALLOWED_LEVELS = {"beginner", "intermediate", "advanced"}
_SESSION_KEYS = {"default", "beginner", "intermediate", "advanced", "rehabilitation"}

_DEFAULT_SESSION_BOUNDS: dict[str, tuple[int, int]] = {
    "default": (4, 7),
    "beginner": (3, 5),
    "intermediate": (4, 6),
    "advanced": (4, 7),
    "rehabilitation": (3, 4),
}


def _clamp_session_bound(value: int) -> int:
    return min(12, max(1, value))


def _parse_session_bounds(raw: object) -> tuple[int, int] | None:
    if not isinstance(raw, dict):
        return None
    try:
        low = int(raw.get("min"))
        high = int(raw.get("max"))
    except (TypeError, ValueError):
        return None
    low = _clamp_session_bound(low)
    high = _clamp_session_bound(high)
    if high < low:
        low, high = high, low
    return low, high


@dataclass(frozen=True)
class GenerationPolicyConfig:
    excluded_pairs: tuple[tuple[str, str], ...] = ()
    default_splits: dict[str, tuple[str, ...]] = field(default_factory=dict)
    default_workouts_per_week: dict[str, int] = field(default_factory=dict)
    exercises_per_session: dict[str, tuple[int, int]] = field(default_factory=dict)

    @classmethod
    def from_json(cls, raw: str | None) -> GenerationPolicyConfig:
        if not raw:
            return cls()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return cls()
        if not isinstance(payload, dict):
            return cls()
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict) -> GenerationPolicyConfig:
        pairs: list[tuple[str, str]] = []
        for item in payload.get("excluded_pairs") or []:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            left, right = str(item[0]).strip(), str(item[1]).strip()
            if left and right and left != right:
                pairs.append((left, right))

        splits: dict[str, tuple[str, ...]] = {}
        for key, value in (payload.get("default_splits") or {}).items():
            if not isinstance(key, str) or not isinstance(value, list):
                continue
            categories = tuple(
                str(item).strip().lower()
                for item in value
                if str(item).strip().lower() in _ALLOWED_CATEGORIES
            )
            if categories:
                splits[key.strip().lower()] = categories

        defaults: dict[str, int] = {}
        for key, value in (payload.get("default_workouts_per_week") or {}).items():
            level = str(key).strip().lower()
            if level not in _ALLOWED_LEVELS:
                continue
            try:
                wpw = int(value)
            except (TypeError, ValueError):
                continue
            defaults[level] = min(7, max(1, wpw))

        session_bounds: dict[str, tuple[int, int]] = {}
        for key, value in (payload.get("exercises_per_session") or {}).items():
            slot = str(key).strip().lower()
            if slot not in _SESSION_KEYS:
                continue
            parsed = _parse_session_bounds(value)
            if parsed is not None:
                session_bounds[slot] = parsed

        return cls(
            excluded_pairs=tuple(pairs),
            default_splits=splits,
            default_workouts_per_week=defaults,
            exercises_per_session=session_bounds,
        )

    def to_dict(self) -> dict:
        session_payload = {
            key: {"min": bounds[0], "max": bounds[1]}
            for key, bounds in self.exercises_per_session.items()
        }
        # Always expose resolved defaults so admin UI has full form.
        for key, bounds in _DEFAULT_SESSION_BOUNDS.items():
            session_payload.setdefault(key, {"min": bounds[0], "max": bounds[1]})
        return {
            "excluded_pairs": [list(pair) for pair in self.excluded_pairs],
            "default_splits": {key: list(value) for key, value in self.default_splits.items()},
            "default_workouts_per_week": dict(self.default_workouts_per_week),
            "exercises_per_session": session_payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def split_for(self, *, goal: str, level: str) -> tuple[str, ...]:
        key = f"{goal.strip().lower()}|{level.strip().lower()}"
        return self.default_splits.get(key, ())

    def workouts_per_week_for(self, level: str) -> int | None:
        return self.default_workouts_per_week.get(level.strip().lower())

    def session_bounds_for(self, *, level: str, goal: str, is_first_plan: bool) -> tuple[int, int]:
        resolved = {**_DEFAULT_SESSION_BOUNDS, **self.exercises_per_session}
        fallback = resolved.get("default", (4, 7))
        if not is_first_plan:
            return fallback
        goal_key = goal.strip().lower()
        if goal_key == "rehabilitation":
            return resolved.get("rehabilitation", fallback)
        level_key = level.strip().lower()
        return resolved.get(level_key, fallback)
