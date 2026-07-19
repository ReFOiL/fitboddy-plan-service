from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from application.generation.policy import GenerationPolicyConfig
from application.models import (
    TrainerGenerationPolicyModel,
    TrainerPolicyExcludedPairModel,
    TrainerPolicySessionBoundsModel,
    TrainerPolicySplitDayModel,
    TrainerPolicyWorkoutsPerWeekModel,
)
from domain.value_objects import SessionBoundSlot, TrainingGoal, TrainingLevelName, WorkoutCategory


class TrainerGenerationPolicyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_config(self, trainer_user_id: str) -> GenerationPolicyConfig:
        model = self._session.get(TrainerGenerationPolicyModel, trainer_user_id)
        if model is None:
            return GenerationPolicyConfig()

        workouts = {
            row.level.value: int(row.workouts_per_week)
            for row in model.workouts_per_week
        }
        session_bounds = {
            row.slot.value: (int(row.min_exercises), int(row.max_exercises))
            for row in model.session_bounds
        }
        splits: dict[str, list[str]] = {}
        for row in sorted(model.split_days, key=lambda item: (item.goal.value, item.level.value, item.position)):
            key = f"{row.goal.value}|{row.level.value}"
            splits.setdefault(key, []).append(row.category.value)
        pairs = tuple((row.exercise_a_id, row.exercise_b_id) for row in model.excluded_pairs)

        return GenerationPolicyConfig(
            excluded_pairs=pairs,
            default_splits={key: tuple(value) for key, value in splits.items()},
            default_workouts_per_week=workouts,
            exercises_per_session=session_bounds,
        )

    def upsert_config(self, trainer_user_id: str, config: GenerationPolicyConfig) -> GenerationPolicyConfig:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        parent = self._session.get(TrainerGenerationPolicyModel, trainer_user_id)
        if parent is None:
            parent = TrainerGenerationPolicyModel(trainer_user_id=trainer_user_id, updated_at=now)
            self._session.add(parent)
        else:
            parent.updated_at = now

        self._session.execute(
            delete(TrainerPolicyWorkoutsPerWeekModel).where(
                TrainerPolicyWorkoutsPerWeekModel.trainer_user_id == trainer_user_id
            )
        )
        self._session.execute(
            delete(TrainerPolicySessionBoundsModel).where(
                TrainerPolicySessionBoundsModel.trainer_user_id == trainer_user_id
            )
        )
        self._session.execute(
            delete(TrainerPolicySplitDayModel).where(
                TrainerPolicySplitDayModel.trainer_user_id == trainer_user_id
            )
        )
        self._session.execute(
            delete(TrainerPolicyExcludedPairModel).where(
                TrainerPolicyExcludedPairModel.trainer_user_id == trainer_user_id
            )
        )
        self._session.flush()

        for level_raw, wpw in config.default_workouts_per_week.items():
            level = TrainingLevelName.from_raw(level_raw)
            if level is None:
                continue
            self._session.add(
                TrainerPolicyWorkoutsPerWeekModel(
                    trainer_user_id=trainer_user_id,
                    level=level,
                    workouts_per_week=int(wpw),
                )
            )

        for slot_raw, bounds in config.exercises_per_session.items():
            slot = SessionBoundSlot.from_raw(slot_raw)
            if slot is None:
                continue
            self._session.add(
                TrainerPolicySessionBoundsModel(
                    trainer_user_id=trainer_user_id,
                    slot=slot,
                    min_exercises=int(bounds[0]),
                    max_exercises=int(bounds[1]),
                )
            )

        known_goals = {item.value: item for item in TrainingGoal}
        for split_key, categories in config.default_splits.items():
            if "|" not in split_key:
                continue
            goal_raw, level_raw = split_key.split("|", 1)
            goal = known_goals.get(goal_raw.strip().lower())
            level = TrainingLevelName.from_raw(level_raw)
            if goal is None or level is None:
                continue
            for position, category_raw in enumerate(categories):
                category = WorkoutCategory.from_raw(category_raw)
                if category is None:
                    continue
                self._session.add(
                    TrainerPolicySplitDayModel(
                        trainer_user_id=trainer_user_id,
                        goal=goal,
                        level=level,
                        position=position,
                        category=category,
                    )
                )

        seen_pairs: set[tuple[str, str]] = set()
        for left, right in config.excluded_pairs:
            a_id, b_id = sorted((left.strip(), right.strip()))
            if not a_id or not b_id or a_id == b_id:
                continue
            pair = (a_id, b_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            self._session.add(
                TrainerPolicyExcludedPairModel(
                    trainer_user_id=trainer_user_id,
                    exercise_a_id=a_id,
                    exercise_b_id=b_id,
                )
            )

        self._session.flush()
        return self.get_config(trainer_user_id)
