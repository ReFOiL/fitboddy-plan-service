from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from application.models import ClientExerciseLoadModel


class ClientExerciseLoadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_client_trainer(self, client_user_id: str, trainer_user_id: str) -> list[ClientExerciseLoadModel]:
        statement = select(ClientExerciseLoadModel).where(
            ClientExerciseLoadModel.client_user_id == client_user_id,
            ClientExerciseLoadModel.exercise_scope == "trainer",
            ClientExerciseLoadModel.trainer_user_id == trainer_user_id,
        )
        return list(self._session.scalars(statement).all())

    def list_for_client_platform(self, client_user_id: str) -> list[ClientExerciseLoadModel]:
        statement = select(ClientExerciseLoadModel).where(
            ClientExerciseLoadModel.client_user_id == client_user_id,
            ClientExerciseLoadModel.exercise_scope == "platform",
        )
        return list(self._session.scalars(statement).all())

    def find(
        self,
        client_user_id: str,
        trainer_user_id: str,
        exercise_row_id: str,
    ) -> ClientExerciseLoadModel | None:
        statement = select(ClientExerciseLoadModel).where(
            ClientExerciseLoadModel.client_user_id == client_user_id,
            ClientExerciseLoadModel.exercise_scope == "trainer",
            ClientExerciseLoadModel.trainer_user_id == trainer_user_id,
            ClientExerciseLoadModel.exercise_row_id == exercise_row_id,
        )
        return self._session.scalar(statement)

    def find_platform(self, client_user_id: str, exercise_row_id: str) -> ClientExerciseLoadModel | None:
        statement = select(ClientExerciseLoadModel).where(
            ClientExerciseLoadModel.client_user_id == client_user_id,
            ClientExerciseLoadModel.exercise_scope == "platform",
            ClientExerciseLoadModel.exercise_row_id == exercise_row_id,
        )
        return self._session.scalar(statement)

    def upsert(
        self,
        *,
        client_user_id: str,
        trainer_user_id: str,
        exercise_row_id: str,
        working_weight_kg: float,
    ) -> ClientExerciseLoadModel:
        existing = self.find(client_user_id, trainer_user_id, exercise_row_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if existing is None:
            model = ClientExerciseLoadModel(
                load_id=str(uuid4()),
                client_user_id=client_user_id,
                exercise_scope="trainer",
                trainer_user_id=trainer_user_id,
                exercise_row_id=exercise_row_id,
                working_weight_kg=working_weight_kg,
                updated_at=now,
            )
            self._session.add(model)
            self._session.flush()
            return model
        existing.working_weight_kg = working_weight_kg
        existing.updated_at = now
        self._session.flush()
        return existing

    def upsert_platform(
        self,
        *,
        client_user_id: str,
        exercise_row_id: str,
        working_weight_kg: float,
    ) -> ClientExerciseLoadModel:
        existing = self.find_platform(client_user_id, exercise_row_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if existing is None:
            model = ClientExerciseLoadModel(
                load_id=str(uuid4()),
                client_user_id=client_user_id,
                exercise_scope="platform",
                trainer_user_id=None,
                exercise_row_id=exercise_row_id,
                working_weight_kg=working_weight_kg,
                updated_at=now,
            )
            self._session.add(model)
            self._session.flush()
            return model
        existing.working_weight_kg = working_weight_kg
        existing.updated_at = now
        self._session.flush()
        return existing
