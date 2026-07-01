from __future__ import annotations

from application.generation.contracts import AbstractCatalogProvider
from application.generation.models import ExerciseCandidate, PlanGenerationInput


class SeedCatalogProvider(AbstractCatalogProvider):
    """Временный каталог для MVP plan-service.

    До выделения отдельного exercise-service используем встроенный пул упражнений.
    """

    def list_exercises(self, request: PlanGenerationInput) -> list[ExerciseCandidate]:
        _ = request
        # Имена — для пользователя по-русски; exercise_id и equipment — стабильные коды для API/генератора.
        return [
            ExerciseCandidate("pushups", "Отжимания", "none", False, 2, "upper"),
            ExerciseCandidate("incline_pushups", "Отжимания с ногами на возвышении", "none", False, 1, "upper"),
            ExerciseCandidate("dumbbell_press", "Жим гантелей стоя или сидя", "dumbbells", False, 3, "upper"),
            ExerciseCandidate("barbell_bench", "Жим штанги лёжа", "barbell", False, 4, "upper"),
            ExerciseCandidate("air_squat", "Приседания без веса", "none", False, 1, "lower"),
            ExerciseCandidate("goblet_squat", "Приседания гоблетом", "dumbbells", False, 2, "lower"),
            ExerciseCandidate("deadlift", "Становая тяга", "barbell", False, 4, "lower"),
            ExerciseCandidate("reverse_lunge", "Обратные выпады", "none", False, 2, "lower"),
            ExerciseCandidate("plank", "Планка", "none", False, 1, "core"),
            ExerciseCandidate("dead_bug", 'Упражнение «мёртвый жук»', "none", False, 1, "core"),
            ExerciseCandidate("russian_twist", "Скручивания на пресс (русский твист)", "none", False, 2, "core"),
            ExerciseCandidate("jumping_jacks", "Прыжки «джеки»", "none", True, 1, "full_body"),
            ExerciseCandidate("burpees", "Бёрпи", "none", True, 3, "full_body"),
            ExerciseCandidate("treadmill_run", "Бег на дорожке", "treadmill", True, 2, "full_body"),
            ExerciseCandidate("kettlebell_swings", "Махи гирей двумя руками", "kettlebell", True, 3, "full_body"),
            ExerciseCandidate("band_row", "Тяга резинкой", "resistance_bands", False, 2, "upper"),
            ExerciseCandidate("dumbbell_row", "Тяга гантели в наклоне", "dumbbells", False, 2, "upper"),
            ExerciseCandidate("hip_bridge", "Мост для ягодиц", "none", False, 1, "lower"),
            ExerciseCandidate("calf_raise", "Подъёмы на носки стоя", "none", False, 1, "lower"),
            ExerciseCandidate("mountain_climbers", "«Альпинист»", "none", True, 2, "full_body"),
        ]
