from __future__ import annotations

import random
from datetime import timedelta

from application.generation.contracts import AbstractSchedulingCalculator
from application.generation.models import (
    ExerciseCandidate,
    ExerciseLine,
    PlanGenerationInput,
    ScheduledSession,
    SetPrescription,
)
from application.weight_prescription import build_prescriptions, resolve_scheme_steps, scale_duration, scale_weight
from domain.value_objects import TrainingGoal, TrainingLevel


class WorkoutSchedulingCalculator(AbstractSchedulingCalculator):
    _DAY_PATTERNS: dict[int, list[list[int]]] = {
        1: [[0]],
        2: [[0, 3], [1, 4], [2, 5]],
        3: [[0, 2, 4], [1, 3, 5], [0, 3, 6]],
        4: [[0, 2, 4, 6], [0, 1, 3, 5], [1, 2, 4, 6]],
        5: [[0, 1, 3, 4, 6], [0, 2, 3, 5, 6], [1, 2, 4, 5, 6]],
        6: [[0, 1, 2, 3, 4, 5]],
        7: [[0, 1, 2, 3, 4, 5, 6]],
    }
    _WEEKLY_VOLUME: dict[int, float] = {1: 1.0, 2: 1.1, 3: 1.2, 4: 1.3}

    def build(self, pool: list[ExerciseCandidate], request: PlanGenerationInput) -> list[ScheduledSession]:
        if not pool:
            return []
        workouts_per_week = min(max(request.workouts_per_week, 1), 7)
        variation_seed = abs(hash((request.goal.value, request.level.value, request.start_date.isoformat()))) % 10_000_000

        result: list[ScheduledSession] = []
        for week in range(1, 5):
            week_start = request.start_date + timedelta(days=(week - 1) * 7)
            offsets = self._choose_offsets(workouts_per_week, variation_seed, week)
            anchors = self._select_anchors(pool, workouts_per_week, week, variation_seed, request.weekly_split)
            week_volume = self._WEEKLY_VOLUME.get(week, 1.2)
            if request.adherence_score <= 0.45:
                week_volume = round(week_volume * 0.9, 3)
            for slot_index, (offset, anchor) in enumerate(zip(offsets, anchors, strict=False)):
                scheduled_for = week_start + timedelta(days=offset)
                lines = self._compose_lines(pool, anchor, week, slot_index, request, variation_seed)
                result.append(
                    ScheduledSession(
                        scheduled_for=scheduled_for,
                        week=week,
                        day_of_week=scheduled_for.weekday(),
                        volume_multiplier=week_volume,
                        lines=lines,
                    )
                )
        return result

    def _choose_offsets(self, workouts_per_week: int, variation_seed: int, week: int) -> list[int]:
        options = self._DAY_PATTERNS.get(workouts_per_week, [[0, 2, 4]])
        pick = (variation_seed + week - 1) % len(options)
        return list(options[pick])

    @staticmethod
    def _select_anchors(
        pool: list[ExerciseCandidate],
        workouts_per_week: int,
        week: int,
        variation_seed: int,
        weekly_split: tuple[str, ...],
    ) -> list[ExerciseCandidate]:
        by_category: dict[str, list[ExerciseCandidate]] = {}
        for exercise in pool:
            by_category.setdefault(exercise.workout_category or "full_body", []).append(exercise)
        categories = sorted(by_category.keys())
        if not categories:
            return []
        rng = random.Random((variation_seed ^ 0x85EBCA6B) + week * 7919)
        anchors: list[ExerciseCandidate] = []
        for i in range(workouts_per_week):
            if weekly_split:
                preferred = weekly_split[i % len(weekly_split)]
                category = preferred if preferred in by_category else categories[(i + week - 1) % len(categories)]
            else:
                category = categories[(i + week - 1) % len(categories)]
            anchors.append(rng.choice(by_category[category]))
        return anchors

    def _compose_lines(
        self,
        pool: list[ExerciseCandidate],
        anchor: ExerciseCandidate,
        week: int,
        slot_index: int,
        request: PlanGenerationInput,
        variation_seed: int,
    ) -> list[ExerciseLine]:
        target = self._session_size(week, slot_index, request, variation_seed)
        rng = random.Random((variation_seed ^ 0x9E3779B9) + week * 1009 + slot_index * 97)
        by_category: dict[str, list[ExerciseCandidate]] = {}
        for exercise in pool:
            by_category.setdefault(exercise.workout_category or "full_body", []).append(exercise)
        categories = sorted(by_category.keys())
        picked: list[ExerciseCandidate] = [anchor]
        used = {anchor.exercise_id}
        cursor = (categories.index(anchor.workout_category) + 1) % len(categories) if anchor.workout_category in categories else 0
        idle_rounds = 0
        while len(picked) < target and categories:
            category = categories[cursor % len(categories)]
            cursor += 1
            candidates = [
                item
                for item in by_category.get(category, [])
                if item.exercise_id not in used
                and not self._conflicts_with_excluded(item.exercise_id, used, request.excluded_pairs)
            ]
            if not candidates:
                idle_rounds += 1
                if idle_rounds >= len(categories):
                    break
                continue
            idle_rounds = 0
            selected = rng.choice(candidates)
            picked.append(selected)
            used.add(selected.exercise_id)
        return [
            self._prescribe(item, sort_order=index + 1, request=request)
            for index, item in enumerate(picked)
        ]

    @staticmethod
    def _conflicts_with_excluded(
        exercise_id: str,
        used_ids: set[str],
        excluded_pairs: tuple[tuple[str, str], ...],
    ) -> bool:
        for left, right in excluded_pairs:
            if exercise_id == left and right in used_ids:
                return True
            if exercise_id == right and left in used_ids:
                return True
        return False

    @staticmethod
    def _session_size(week: int, slot_index: int, request: PlanGenerationInput, variation_seed: int) -> int:
        session_min = 4
        session_max = 7
        if request.is_first_plan:
            if request.goal == TrainingGoal.REHABILITATION:
                session_min, session_max = 3, 4
            elif request.level == TrainingLevel.BEGINNER:
                session_min, session_max = 3, 5
            elif request.level == TrainingLevel.INTERMEDIATE:
                session_min, session_max = 4, 6
        mix = (variation_seed + week * 17 + slot_index * 5) & 0xFFFFFFFF
        span = session_max - session_min + 1
        return session_min + (mix % span)

    @classmethod
    def _prescribe(cls, exercise: ExerciseCandidate, *, sort_order: int, request: PlanGenerationInput) -> ExerciseLine:
        is_beginner_profile = request.level == TrainingLevel.BEGINNER or request.goal == TrainingGoal.REHABILITATION
        is_advanced_profile = request.level == TrainingLevel.ADVANCED and request.goal == TrainingGoal.MUSCLE_GAIN

        sets = max(1, exercise.default_sets)
        rest = max(0, exercise.default_rest_seconds)
        working_weight = request.client_working_weights.get(exercise.exercise_id)
        if working_weight is None:
            working_weight = exercise.default_weight_kg
        weight = working_weight

        if exercise.is_hold:
            duration = max(5, exercise.default_duration_seconds or 35)
            if request.is_first_plan and is_beginner_profile:
                sets = max(1, sets - 1)
                duration = max(10, int(duration * 0.75))
                rest = rest + 15
            elif is_advanced_profile and not request.is_first_plan:
                duration = int(duration * 1.2)
            result = build_prescriptions(
                working_weight=weight,
                sets=sets,
                load_scheme=exercise.load_scheme,
                scheme_steps=exercise.scheme_steps,
                is_hold=True,
                reps=None,
                duration_seconds=duration,
                rest_seconds=rest,
            )
            prescriptions = tuple(
                SetPrescription(
                    set_index=item.set_index,
                    reps=item.reps,
                    duration_seconds=item.duration_seconds,
                    weight_kg=item.weight_kg,
                    rest_seconds=item.rest_seconds,
                )
                for item in result.set_prescriptions
            )
            return ExerciseLine(
                exercise=exercise,
                sort_order=sort_order,
                sets=sets,
                reps=None,
                duration_seconds=result.duration_seconds,
                rest_seconds=rest,
                weight_kg=result.weight_kg,
                set_prescriptions=prescriptions,
            )

        reps = max(1, exercise.default_reps or 10)
        if request.is_first_plan and is_beginner_profile:
            sets = max(1, sets - 1)
            reps = max(4, reps - 2)
            rest = rest + 15
        elif is_advanced_profile and not request.is_first_plan:
            sets = sets + 1
            rest = rest + 30
            if weight is not None and exercise.exercise_id not in request.client_working_weights:
                weight = round(weight * 1.1, 1)

        result = build_prescriptions(
            working_weight=weight,
            sets=sets,
            load_scheme=exercise.load_scheme,
            scheme_steps=exercise.scheme_steps,
            is_hold=False,
            reps=reps,
            duration_seconds=None,
            rest_seconds=rest,
        )
        prescriptions = tuple(
            SetPrescription(
                set_index=item.set_index,
                reps=item.reps,
                duration_seconds=item.duration_seconds,
                weight_kg=item.weight_kg,
                rest_seconds=item.rest_seconds,
            )
            for item in result.set_prescriptions
        )
        return ExerciseLine(
            exercise=exercise,
            sort_order=sort_order,
            sets=sets,
            reps=reps,
            duration_seconds=None,
            rest_seconds=rest,
            weight_kg=result.weight_kg,
            set_prescriptions=prescriptions,
        )

    @staticmethod
    def _resolve_scheme_steps(scheme: str, sets: int, custom_steps: tuple[float, ...]) -> list[float]:
        return resolve_scheme_steps(scheme, sets, custom_steps)

    @staticmethod
    def _scale_duration(base_duration: int, step: float) -> int:
        return scale_duration(base_duration, step)

    @staticmethod
    def _scale_weight(base_weight: float, step: float) -> float:
        return scale_weight(base_weight, step)
