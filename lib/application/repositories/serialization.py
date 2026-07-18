from __future__ import annotations

import json

from domain.entities import PlanSetPrescription


def parse_scheme_steps(raw: str | None) -> list[float]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    steps: list[float] = []
    for item in parsed:
        try:
            value = float(item)
        except (TypeError, ValueError):
            continue
        if value > 0:
            steps.append(value)
    return steps


def dumps_scheme_steps(steps: list[float]) -> str | None:
    if not steps:
        return None
    return json.dumps(steps)


def parse_set_prescriptions(raw: str | None) -> list[PlanSetPrescription]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    result: list[PlanSetPrescription] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        try:
            set_index = int(item.get("set_index", 0))
        except (TypeError, ValueError):
            continue
        if set_index < 1:
            continue
        result.append(
            PlanSetPrescription(
                set_index=set_index,
                reps=item.get("reps"),
                duration_seconds=item.get("duration_seconds"),
                weight_kg=item.get("weight_kg"),
                rest_seconds=item.get("rest_seconds"),
            )
        )
    return sorted(result, key=lambda row: row.set_index)


def dumps_set_prescriptions(prescriptions: list[PlanSetPrescription] | tuple) -> str | None:
    if not prescriptions:
        return None
    payload = [
        {
            "set_index": item.set_index,
            "reps": item.reps,
            "duration_seconds": item.duration_seconds,
            "weight_kg": item.weight_kg,
            "rest_seconds": item.rest_seconds,
        }
        for item in prescriptions
    ]
    return json.dumps(payload)
