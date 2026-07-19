from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.entities import PlanSetPrescription


@dataclass(frozen=True)
class WeightPrescriptionResult:
    weight_kg: float | None
    duration_seconds: int | None
    set_prescriptions: tuple[PlanSetPrescription, ...]


def resolve_scheme_steps(scheme: str, sets: int, custom_steps: Sequence[float] = ()) -> list[float]:
    normalized = (scheme or "flat").strip().lower()
    if custom_steps and normalized == "custom":
        steps = list(custom_steps)
        if len(steps) >= sets:
            return steps[:sets]
        if steps:
            return steps + [steps[-1]] * (sets - len(steps))
    if normalized == "ascending":
        if sets <= 1:
            return [1.0]
        return [round(0.7 + (0.3 * index / (sets - 1)), 3) for index in range(sets)]
    if normalized == "descending":
        if sets <= 1:
            return [1.0]
        return [round(1.0 - (0.3 * index / (sets - 1)), 3) for index in range(sets)]
    if custom_steps:
        steps = list(custom_steps)
        if len(steps) >= sets:
            return steps[:sets]
        if steps:
            return steps + [steps[-1]] * (sets - len(steps))
    return [1.0] * sets


def scale_duration(base_duration: int, step: float) -> int:
    raw = base_duration * step
    return max(5, int(round(raw)))


def scale_weight(base_weight: float, step: float) -> float:
    raw = base_weight * step
    # Preserve exact working/default weight on top-set (step=1.0); round ramps to 2.5 kg plates.
    if abs(step - 1.0) < 1e-9:
        return round(raw, 1)
    return round(round(raw / 2.5) * 2.5, 1)


def build_prescriptions(
    *,
    working_weight: float | None,
    sets: int,
    load_scheme: str,
    scheme_steps: Sequence[float] = (),
    is_hold: bool,
    reps: int | None,
    duration_seconds: int | None,
    rest_seconds: int | None,
) -> WeightPrescriptionResult:
    """Build set prescriptions from scratch (generation after volume tweaks)."""
    sets = max(1, sets)
    rest = max(0, rest_seconds or 0)
    steps = resolve_scheme_steps(load_scheme, sets, scheme_steps)

    if is_hold:
        duration = max(5, duration_seconds or 35)
        flat_weight = scale_weight(working_weight, 1.0) if working_weight is not None else None
        prescriptions = tuple(
            PlanSetPrescription(
                set_index=index + 1,
                reps=None,
                duration_seconds=scale_duration(duration, step),
                weight_kg=flat_weight,
                rest_seconds=rest,
            )
            for index, step in enumerate(steps)
        )
        summary_duration = prescriptions[-1].duration_seconds if prescriptions else duration
        return WeightPrescriptionResult(
            weight_kg=flat_weight,
            duration_seconds=summary_duration,
            set_prescriptions=prescriptions,
        )

    reps_value = max(1, reps or 10)
    prescriptions = tuple(
        PlanSetPrescription(
            set_index=index + 1,
            reps=reps_value,
            duration_seconds=None,
            weight_kg=scale_weight(working_weight, step) if working_weight is not None else None,
            rest_seconds=rest,
        )
        for index, step in enumerate(steps)
    )
    summary_weight = prescriptions[-1].weight_kg if prescriptions else working_weight
    return WeightPrescriptionResult(
        weight_kg=summary_weight,
        duration_seconds=None,
        set_prescriptions=prescriptions,
    )


def rescale_plan_line_weights(
    *,
    working_weight: float,
    load_scheme: str,
    scheme_steps: Sequence[float] = (),
    is_hold: bool,
    sets: int | None,
    reps: int | None,
    duration_seconds: int | None,
    rest_seconds: int | None,
    existing_prescriptions: Sequence[PlanSetPrescription] = (),
) -> WeightPrescriptionResult:
    """Rescale weights for an existing plan line without volume tweaks.

    Preserves per-set reps/duration/rest when prescriptions already exist.
    """
    if existing_prescriptions:
        ordered = sorted(existing_prescriptions, key=lambda item: item.set_index)
        set_count = len(ordered)
        steps = resolve_scheme_steps(load_scheme, set_count, scheme_steps)
        prescriptions: list[PlanSetPrescription] = []
        for index, presc in enumerate(ordered):
            step = steps[index] if index < len(steps) else 1.0
            if is_hold or presc.duration_seconds is not None:
                weight = scale_weight(working_weight, 1.0)
            else:
                weight = scale_weight(working_weight, step)
            prescriptions.append(
                PlanSetPrescription(
                    set_index=presc.set_index,
                    reps=presc.reps,
                    duration_seconds=presc.duration_seconds,
                    weight_kg=weight,
                    rest_seconds=presc.rest_seconds,
                )
            )
        summary_weight = prescriptions[-1].weight_kg if prescriptions else working_weight
        summary_duration = None
        if is_hold or any(item.duration_seconds is not None for item in prescriptions):
            summary_duration = prescriptions[-1].duration_seconds if prescriptions else duration_seconds
        return WeightPrescriptionResult(
            weight_kg=summary_weight,
            duration_seconds=summary_duration,
            set_prescriptions=tuple(prescriptions),
        )

    return build_prescriptions(
        working_weight=working_weight,
        sets=sets or 1,
        load_scheme=load_scheme,
        scheme_steps=scheme_steps,
        is_hold=is_hold,
        reps=reps,
        duration_seconds=duration_seconds,
        rest_seconds=rest_seconds,
    )
