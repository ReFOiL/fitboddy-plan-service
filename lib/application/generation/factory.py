from sqlalchemy.orm import Session

from application.generation.calculators import CatalogMatchingCalculator, WorkoutSchedulingCalculator
from application.generation.orchestrator import GenerationOrchestrator
from application.generation.providers import (
    PlatformCatalogProvider,
    SeedCatalogProvider,
    SourceAwareCatalogProvider,
    TrainerCatalogProvider,
)
from application.repositories import PlatformExerciseRepository, TrainerExerciseRepository


def build_default_generation_orchestrator(session: Session) -> GenerationOrchestrator:
    bootstrap_provider = SeedCatalogProvider()
    platform_repo = PlatformExerciseRepository(session)
    trainer_repo = TrainerExerciseRepository(session)
    catalog_provider = SourceAwareCatalogProvider(
        trainer_provider=TrainerCatalogProvider(
            trainer_repo=trainer_repo,
            platform_repo=platform_repo,
            bootstrap_provider=bootstrap_provider,
        ),
        platform_provider=PlatformCatalogProvider(
            platform_repo=platform_repo,
            bootstrap_provider=bootstrap_provider,
        ),
    )
    return GenerationOrchestrator(
        catalog_provider=catalog_provider,
        matcher=CatalogMatchingCalculator(),
        scheduler=WorkoutSchedulingCalculator(),
    )
