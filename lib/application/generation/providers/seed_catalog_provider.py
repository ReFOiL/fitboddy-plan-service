from __future__ import annotations

from application.generation.contracts import AbstractCatalogProvider
from application.generation.models import ExerciseCandidate, PlanGenerationInput


def _candidate(
    exercise_id: str,
    name: str,
    equipment: str,
    is_cardio: bool,
    difficulty: int,
    workout_category: str,
    *,
    is_hold: bool = False,
    sets: int = 3,
    reps: int | None = 10,
    duration_seconds: int | None = None,
    rest_seconds: int | None = None,
    weight_kg: float | None = None,
    load_scheme: str = "flat",
    scheme_steps: tuple[float, ...] = (),
) -> ExerciseCandidate:
    if is_hold:
        return ExerciseCandidate(
            exercise_id=exercise_id,
            name=name,
            equipment=equipment,
            is_cardio=is_cardio,
            difficulty=difficulty,
            workout_category=workout_category,
            is_hold=True,
            default_sets=sets,
            default_reps=None,
            default_duration_seconds=duration_seconds if duration_seconds is not None else 35,
            default_rest_seconds=rest_seconds if rest_seconds is not None else 45,
            default_weight_kg=weight_kg,
            load_scheme=load_scheme,
            scheme_steps=scheme_steps,
        )
    return ExerciseCandidate(
        exercise_id=exercise_id,
        name=name,
        equipment=equipment,
        is_cardio=is_cardio,
        difficulty=difficulty,
        workout_category=workout_category,
        is_hold=False,
        default_sets=sets,
        default_reps=reps if reps is not None else 10,
        default_duration_seconds=None,
        default_rest_seconds=rest_seconds if rest_seconds is not None else 60,
        default_weight_kg=weight_kg,
        load_scheme=load_scheme,
        scheme_steps=scheme_steps,
    )


class SeedCatalogProvider(AbstractCatalogProvider):
    """Bootstrap-пул для пустого `platform_exercises`.

    Не источник для каталога тренера напрямую: тренеры клонируют базу из Support.
    Seed применяется только когда платформенный каталог ещё пуст (первый старт).
    """

    def list_exercises(self, request: PlanGenerationInput) -> list[ExerciseCandidate]:
        _ = request
        return [
            _candidate("pushups", "Отжимания", "none", False, 2, "upper"),
            _candidate("incline_pushups", "Отжимания с ногами на возвышении", "none", False, 1, "upper", reps=12),
            _candidate("dumbbell_press", "Жим гантелей стоя или сидя", "dumbbells", False, 3, "upper", weight_kg=12),
            _candidate(
                "barbell_bench",
                "Жим штанги лёжа",
                "barbell",
                False,
                4,
                "upper",
                sets=6,
                reps=5,
                weight_kg=100,
                rest_seconds=120,
                load_scheme="ascending",
            ),
            _candidate("air_squat", "Приседания без веса", "none", False, 1, "lower", reps=12),
            _candidate("goblet_squat", "Приседания гоблетом", "dumbbells", False, 2, "lower", weight_kg=12),
            _candidate("deadlift", "Становая тяга", "barbell", False, 4, "lower", sets=3, reps=8, weight_kg=50, rest_seconds=90),
            _candidate("reverse_lunge", "Обратные выпады", "none", False, 2, "lower"),
            _candidate("plank", "Планка", "none", False, 1, "core", is_hold=True, duration_seconds=40, load_scheme="ascending"),
            _candidate("dead_bug", 'Упражнение «мёртвый жук»', "none", False, 1, "core", reps=8),
            _candidate("russian_twist", "Скручивания на пресс (русский твист)", "none", False, 2, "core"),
            _candidate("jumping_jacks", "Прыжки «джеки»", "none", True, 1, "full_body", is_hold=True, duration_seconds=40, rest_seconds=30),
            _candidate("burpees", "Бёрпи", "none", True, 3, "full_body", reps=8, rest_seconds=75),
            _candidate("treadmill_run", "Бег на дорожке", "treadmill", True, 2, "full_body", is_hold=True, duration_seconds=60, rest_seconds=30),
            _candidate("kettlebell_swings", "Махи гирей двумя руками", "kettlebell", True, 3, "full_body", reps=12, weight_kg=12),
            _candidate("band_row", "Тяга резинкой", "resistance_bands", False, 2, "upper"),
            _candidate("dumbbell_row", "Тяга гантели в наклоне", "dumbbells", False, 2, "upper", weight_kg=10),
            _candidate("hip_bridge", "Мост для ягодиц", "none", False, 1, "lower", reps=12),
            _candidate("calf_raise", "Подъёмы на носки стоя", "none", False, 1, "lower", reps=15),
            _candidate("mountain_climbers", "«Альпинист»", "none", True, 2, "full_body", is_hold=True, duration_seconds=30, rest_seconds=30),
        ]
