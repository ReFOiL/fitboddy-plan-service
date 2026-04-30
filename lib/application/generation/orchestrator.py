from __future__ import annotations

from dataclasses import dataclass

from application.generation.contracts import (
    AbstractCatalogProvider,
    AbstractMatchingCalculator,
    AbstractSchedulingCalculator,
)
from application.generation.models import ExerciseCandidate, PlanGenerationInput, ScheduledSession


@dataclass(frozen=True)
class GenerationOutcome:
    matched_pool: list[ExerciseCandidate]
    sessions: list[ScheduledSession]


class GenerationOrchestrator:
    """Оркестратор pipeline генерации тренировочного плана.

    Pipeline:
    1) provider -> каталог упражнений
    2) matcher -> персонализированный пул
    3) scheduler -> 4-недельное расписание
    """

    def __init__(
        self,
        *,
        catalog_provider: AbstractCatalogProvider,
        matcher: AbstractMatchingCalculator,
        scheduler: AbstractSchedulingCalculator,
    ) -> None:
        self._catalog_provider = catalog_provider
        self._matcher = matcher
        self._scheduler = scheduler

    def generate(self, request: PlanGenerationInput, *, match_limit: int = 24) -> GenerationOutcome:
        catalog = self._catalog_provider.list_exercises(request)
        if not catalog:
            return GenerationOutcome(matched_pool=[], sessions=[])

        matched_pool = self._matcher.match(catalog, request, limit=match_limit)
        if not matched_pool:
            return GenerationOutcome(matched_pool=[], sessions=[])

        sessions = self._scheduler.build(matched_pool, request)
        return GenerationOutcome(matched_pool=matched_pool, sessions=sessions)
