from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from application.generation.policy import GenerationPolicyConfig
from application.models import GenerationPolicyModel


class GenerationPolicyRepository:
    POLICY_ID = 1

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_config(self) -> GenerationPolicyConfig:
        model = self._session.get(GenerationPolicyModel, self.POLICY_ID)
        if model is None:
            return GenerationPolicyConfig()
        return GenerationPolicyConfig.from_json(model.config_json)

    def upsert_config(self, config: GenerationPolicyConfig) -> GenerationPolicyConfig:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        model = self._session.get(GenerationPolicyModel, self.POLICY_ID)
        if model is None:
            model = GenerationPolicyModel(
                policy_id=self.POLICY_ID,
                config_json=config.to_json(),
                updated_at=now,
            )
            self._session.add(model)
        else:
            model.config_json = config.to_json()
            model.updated_at = now
        self._session.flush()
        return config
