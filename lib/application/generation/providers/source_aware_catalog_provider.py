from __future__ import annotations

from application.generation.contracts import AbstractCatalogProvider
from application.generation.models import ExerciseCandidate, PlanGenerationInput


class SourceAwareCatalogProvider(AbstractCatalogProvider):
    """Выбирает каталог по `PlanGenerationInput.source`."""

    def __init__(
        self,
        *,
        trainer_provider: AbstractCatalogProvider,
        platform_provider: AbstractCatalogProvider,
    ) -> None:
        self._trainer_provider = trainer_provider
        self._platform_provider = platform_provider

    def list_exercises(self, request: PlanGenerationInput) -> list[ExerciseCandidate]:
        if request.source == "system":
            return self._platform_provider.list_exercises(request)
        return self._trainer_provider.list_exercises(request)
