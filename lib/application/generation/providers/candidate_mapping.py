from __future__ import annotations

import json

from application.generation.models import ExerciseCandidate


def parse_scheme_steps(raw: str | None) -> tuple[float, ...]:
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    steps: list[float] = []
    for item in parsed:
        try:
            value = float(item)
        except (TypeError, ValueError):
            continue
        if value > 0:
            steps.append(value)
    return tuple(steps)


def exercise_row_to_candidate(
    *,
    exercise_id: str,
    exercise_name: str,
    equipment: str,
    is_cardio: bool,
    difficulty: int,
    workout_category: str,
    is_hold: bool,
    default_sets: int,
    default_reps: int | None,
    default_duration_seconds: int | None,
    default_rest_seconds: int,
    default_weight_kg: float | None,
    load_scheme: str | None,
    scheme_steps_json: str | None,
) -> ExerciseCandidate:
    return ExerciseCandidate(
        exercise_id=exercise_id,
        name=exercise_name,
        equipment=equipment,
        is_cardio=is_cardio,
        difficulty=difficulty,
        workout_category=workout_category,
        is_hold=is_hold,
        default_sets=default_sets,
        default_reps=default_reps,
        default_duration_seconds=default_duration_seconds,
        default_rest_seconds=default_rest_seconds,
        default_weight_kg=default_weight_kg,
        load_scheme=load_scheme or "flat",
        scheme_steps=parse_scheme_steps(scheme_steps_json),
    )
