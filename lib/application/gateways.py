from __future__ import annotations

import httpx

from application.errors import IntegrationError


class ProfileGateway:
    def __init__(self, http_client: httpx.Client, profile_service_url: str) -> None:
        self._http_client = http_client
        self._profile_service_url = profile_service_url.rstrip("/")

    def is_questionnaire_completed(self, user_id: str) -> bool:
        try:
            response = self._http_client.get(
                f"{self._profile_service_url}/api/v1/profiles/internal/{user_id}/questionnaire-status"
            )
        except httpx.HTTPError as exc:
            raise IntegrationError("profile-service is unavailable") from exc

        if response.status_code >= 500:
            raise IntegrationError("profile-service returned server error")
        if response.status_code != 200:
            raise IntegrationError("profile-service returned unexpected response")
        payload = response.json()
        return bool(payload.get("is_completed"))
