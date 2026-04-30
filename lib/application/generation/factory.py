from sqlalchemy.orm import Session

from application.generation.calculators import CatalogMatchingCalculator, WorkoutSchedulingCalculator
from application.generation.orchestrator import GenerationOrchestrator
from application.generation.providers import SeedCatalogProvider, TrainerCatalogProvider
from application.repositories import TrainerExerciseRepository


def build_default_generation_orchestrator(session: Session) -> GenerationOrchestrator:
    seed_provider = SeedCatalogProvider()
    trainer_provider = TrainerCatalogProvider(
        trainer_repo=TrainerExerciseRepository(session),
        fallback_provider=seed_provider,
    )
    return GenerationOrchestrator(
        catalog_provider=trainer_provider,
        matcher=CatalogMatchingCalculator(),
        scheduler=WorkoutSchedulingCalculator(),
    )
