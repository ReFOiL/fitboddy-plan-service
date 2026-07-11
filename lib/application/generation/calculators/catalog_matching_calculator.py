from __future__ import annotations

from application.generation.contracts import AbstractMatchingCalculator
from application.generation.models import ExerciseCandidate, PlanGenerationInput
from domain.equipment import equipment_match_key
from domain.value_objects import TrainingGoal


class CatalogMatchingCalculator(AbstractMatchingCalculator):
    def match(
        self,
        catalog: list[ExerciseCandidate],
        request: PlanGenerationInput,
        *,
        limit: int = 24,
    ) -> list[ExerciseCandidate]:
        eligible = [exercise for exercise in catalog if self._is_eligible(exercise, request)]
        if not eligible:
            return []
        scored = [(exercise, self._score(exercise, request)) for exercise in eligible]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return self._pick_with_novelty_control(scored, limit=limit, recent_exercise_ids=request.recent_exercise_ids)

    @staticmethod
    def _is_eligible(exercise: ExerciseCandidate, request: PlanGenerationInput) -> bool:
        available = {equipment_match_key(item) for item in request.available_equipment}
        if equipment_match_key(exercise.equipment) not in available:
            return False
        if exercise.difficulty > int(request.level):
            return False
        return True

    @staticmethod
    def _score(exercise: ExerciseCandidate, request: PlanGenerationInput) -> int:
        score = 10
        if request.goal in {TrainingGoal.WEIGHT_LOSS, TrainingGoal.ENDURANCE} and exercise.is_cardio:
            score += 8
        if request.goal in {TrainingGoal.MUSCLE_GAIN, TrainingGoal.MAINTENANCE} and not exercise.is_cardio:
            score += 5
        if equipment_match_key(exercise.equipment) == "none":
            score += 2
        return score

    def _pick_with_novelty_control(
        self,
        scored: list[tuple[ExerciseCandidate, int]],
        *,
        limit: int,
        recent_exercise_ids: set[str],
    ) -> list[ExerciseCandidate]:
        if not recent_exercise_ids:
            return self._diversify_by_category(scored, limit)

        novelty_penalty = 3
        reweighted: list[tuple[ExerciseCandidate, int]] = []
        for exercise, base in scored:
            adjusted = base - novelty_penalty if exercise.exercise_id in recent_exercise_ids else base
            reweighted.append((exercise, adjusted))
        reweighted.sort(key=lambda pair: pair[1], reverse=True)

        fresh = [pair for pair in reweighted if pair[0].exercise_id not in recent_exercise_ids]
        repeated = [pair for pair in reweighted if pair[0].exercise_id in recent_exercise_ids]
        minimum_new = min(len(fresh), max(1, int(limit * 0.35)))

        picked_new = self._diversify_by_category(fresh, minimum_new)
        remaining = max(0, limit - len(picked_new))
        picked_old = self._diversify_by_category(repeated, remaining)
        if len(picked_new) + len(picked_old) < limit:
            already = {exercise.exercise_id for exercise in [*picked_new, *picked_old]}
            fill_pool = [exercise for exercise, _score in reweighted if exercise.exercise_id not in already]
            picked_old.extend(fill_pool[: max(0, limit - len(picked_new) - len(picked_old))])
        return [*picked_new, *picked_old][:limit]

    @staticmethod
    def _diversify_by_category(scored: list[tuple[ExerciseCandidate, int]], limit: int) -> list[ExerciseCandidate]:
        by_category: dict[str, list[ExerciseCandidate]] = {}
        for exercise, _score in scored:
            by_category.setdefault(exercise.workout_category or "full_body", []).append(exercise)
        categories = sorted(by_category.keys())
        result: list[ExerciseCandidate] = []
        cursor = 0
        while len(result) < limit and categories:
            category = categories[cursor % len(categories)]
            cursor += 1
            bucket = by_category[category]
            if not bucket:
                continue
            result.append(bucket.pop(0))
            if not bucket:
                categories.remove(category)
        return result
