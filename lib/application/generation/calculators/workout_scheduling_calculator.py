from __future__ import annotations

import random
from datetime import timedelta

from application.generation.contracts import AbstractSchedulingCalculator
from application.generation.models import ExerciseCandidate, ExerciseLine, PlanGenerationInput, ScheduledSession
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
            anchors = self._select_anchors(pool, workouts_per_week, week, variation_seed)
            for slot_index, (offset, anchor) in enumerate(zip(offsets, anchors, strict=False)):
                scheduled_for = week_start + timedelta(days=offset)
                lines = self._compose_lines(pool, anchor, week, slot_index, request, variation_seed)
                result.append(
                    ScheduledSession(
                        scheduled_for=scheduled_for,
                        week=week,
                        day_of_week=scheduled_for.weekday(),
                        volume_multiplier=self._WEEKLY_VOLUME.get(week, 1.2),
                        lines=lines,
                    )
                )
        return result

    def _choose_offsets(self, workouts_per_week: int, variation_seed: int, week: int) -> list[int]:
        options = self._DAY_PATTERNS.get(workouts_per_week, [[0, 2, 4]])
        pick = (variation_seed + week - 1) % len(options)
        return list(options[pick])

    @staticmethod
    def _select_anchors(pool: list[ExerciseCandidate], workouts_per_week: int, week: int, variation_seed: int) -> list[ExerciseCandidate]:
        by_category: dict[str, list[ExerciseCandidate]] = {}
        for exercise in pool:
            by_category.setdefault(exercise.workout_category or "full_body", []).append(exercise)
        categories = sorted(by_category.keys())
        if not categories:
            return []
        rng = random.Random((variation_seed ^ 0x85EBCA6B) + week * 7919)
        anchors: list[ExerciseCandidate] = []
        for i in range(workouts_per_week):
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
        while len(picked) < target and categories:
            category = categories[cursor % len(categories)]
            cursor += 1
            candidates = [item for item in by_category.get(category, []) if item.exercise_id not in used]
            if not candidates:
                continue
            selected = rng.choice(candidates)
            picked.append(selected)
            used.add(selected.exercise_id)
        return [
            self._prescribe(item, sort_order=index + 1, request=request)
            for index, item in enumerate(picked)
        ]

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

    @staticmethod
    def _prescribe(exercise: ExerciseCandidate, *, sort_order: int, request: PlanGenerationInput) -> ExerciseLine:
        is_beginner_profile = request.level == TrainingLevel.BEGINNER or request.goal == TrainingGoal.REHABILITATION
        is_advanced_profile = request.level == TrainingLevel.ADVANCED and request.goal == TrainingGoal.MUSCLE_GAIN
        if exercise.is_cardio:
            duration = 40
            rest = 30
            sets = 3
            if request.is_first_plan and is_beginner_profile:
                duration = 30
                rest = 45
                sets = 2
            elif is_advanced_profile and not request.is_first_plan:
                duration = 50
            return ExerciseLine(
                exercise=exercise,
                sort_order=sort_order,
                sets=sets,
                reps=None,
                duration_seconds=duration,
                rest_seconds=rest,
            )
        sets = 3
        reps = 10
        rest = 60
        if request.is_first_plan and is_beginner_profile:
            sets, reps, rest = 2, 8, 75
        elif is_advanced_profile and not request.is_first_plan:
            sets, reps, rest = 4, 8, 90
        return ExerciseLine(
            exercise=exercise,
            sort_order=sort_order,
            sets=sets,
            reps=reps,
            duration_seconds=None,
            rest_seconds=rest,
        )
