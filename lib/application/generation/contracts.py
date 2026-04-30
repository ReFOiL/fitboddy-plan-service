from __future__ import annotations

from abc import ABC, abstractmethod

from application.generation.models import ExerciseCandidate, PlanGenerationInput, ScheduledSession


class AbstractCatalogProvider(ABC):
    @abstractmethod
    def list_exercises(self, request: PlanGenerationInput) -> list[ExerciseCandidate]:
        raise NotImplementedError


class AbstractMatchingCalculator(ABC):
    @abstractmethod
    def match(
        self,
        catalog: list[ExerciseCandidate],
        request: PlanGenerationInput,
        *,
        limit: int = 24,
    ) -> list[ExerciseCandidate]:
        raise NotImplementedError


class AbstractSchedulingCalculator(ABC):
    @abstractmethod
    def build(
        self,
        pool: list[ExerciseCandidate],
        request: PlanGenerationInput,
    ) -> list[ScheduledSession]:
        raise NotImplementedError
