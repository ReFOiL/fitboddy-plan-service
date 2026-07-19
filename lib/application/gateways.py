from __future__ import annotations

from dataclasses import dataclass

import httpx

from application.errors import ForbiddenError, IntegrationError, UnauthorizedError


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    tenant_id: str
    role: str


class AuthGateway:
    def __init__(self, http_client: httpx.Client, auth_service_url: str) -> None:
        self._http_client = http_client
        self._auth_service_url = auth_service_url.rstrip("/")

    def get_current_user(self, access_token: str) -> AuthUser:
        try:
            response = self._http_client.get(
                f"{self._auth_service_url}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError as exc:
            raise IntegrationError("auth-service is unavailable") from exc

        if response.status_code == 401:
            raise UnauthorizedError("invalid access token")
        if response.status_code >= 500:
            raise IntegrationError("auth-service returned server error")
        if response.status_code != 200:
            raise IntegrationError("auth-service returned unexpected response")

        payload = response.json()
        return AuthUser(user_id=payload["user_id"], tenant_id=payload["tenant_id"], role=payload["role"])

    def require_platform_admin(self, access_token: str) -> AuthUser:
        user = self.get_current_user(access_token)
        if user.role != "platform_admin":
            raise ForbiddenError("platform_admin role required")
        return user


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


class TenantGateway:
    def __init__(self, http_client: httpx.Client, tenant_service_url: str) -> None:
        self._http_client = http_client
        self._tenant_service_url = tenant_service_url.rstrip("/")

    def get_client_active_trainer_id(self, client_user_id: str) -> str | None:
        try:
            response = self._http_client.get(
                f"{self._tenant_service_url}/api/v1/marketplace/clients/{client_user_id}/active-relation"
            )
        except httpx.HTTPError as exc:
            raise IntegrationError("tenant-service is unavailable") from exc

        if response.status_code == 404:
            return None
        if response.status_code >= 500:
            raise IntegrationError("tenant-service returned server error")
        if response.status_code != 200:
            raise IntegrationError("tenant-service returned unexpected response")
        payload = response.json()
        trainer_user_id = payload.get("trainer_user_id")
        if not isinstance(trainer_user_id, str) or not trainer_user_id.strip():
            return None
        return trainer_user_id.strip()
