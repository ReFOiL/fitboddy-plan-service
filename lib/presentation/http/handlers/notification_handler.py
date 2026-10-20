from __future__ import annotations

import hmac

from application.errors import PlanError, UnauthorizedError
from application.notifications.settings_service import NotificationSettingsService
from application.runtime import PlanApplicationRuntime
from presentation.http.error_translator import ErrorTranslator
from presentation.http.schemas import (
    ConfirmTelegramLinkRequest,
    NotificationSettingsResponse,
    TelegramLinkCodeResponse,
    UpdateNotificationSettingsRequest,
)


class NotificationHttpHandler:
    def __init__(self, runtime: PlanApplicationRuntime, error_translator: ErrorTranslator) -> None:
        self._runtime = runtime
        self._error_translator = error_translator

    def get_settings(self, *, authorization: str | None) -> NotificationSettingsResponse:
        try:
            user = self._require_current_user(authorization)
            with self._runtime.notification_session() as session:
                view = NotificationSettingsService(session, self._runtime.settings).get_settings(user.user_id)
            return _to_response(view)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def update_settings(
        self,
        *,
        authorization: str | None,
        payload: UpdateNotificationSettingsRequest,
    ) -> NotificationSettingsResponse:
        try:
            user = self._require_current_user(authorization)
            fields = payload.model_fields_set
            with self._runtime.notification_session() as session:
                view = NotificationSettingsService(session, self._runtime.settings).update_settings(
                    user.user_id,
                    timezone_specified="timezone" in fields,
                    timezone_name=payload.timezone,
                    enabled_specified="notifications_enabled" in fields,
                    notifications_enabled=payload.notifications_enabled,
                )
            return _to_response(view)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def issue_link_code(self, *, authorization: str | None) -> TelegramLinkCodeResponse:
        try:
            user = self._require_current_user(authorization)
            with self._runtime.notification_session() as session:
                issued = NotificationSettingsService(session, self._runtime.settings).issue_link_code(user.user_id)
            return TelegramLinkCodeResponse(code=issued.code, expires_at=issued.expires_at)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def unlink_telegram(self, *, authorization: str | None) -> None:
        try:
            user = self._require_current_user(authorization)
            with self._runtime.notification_session() as session:
                NotificationSettingsService(session, self._runtime.settings).unlink_telegram(user.user_id)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)

    def confirm_telegram(self, *, service_token: str | None, payload: ConfirmTelegramLinkRequest) -> dict[str, bool]:
        try:
            self._require_service_token(service_token)
            with self._runtime.notification_session() as session:
                NotificationSettingsService(session, self._runtime.settings).confirm_telegram(
                    payload.code,
                    payload.chat_id,
                )
            return {"telegram_linked": True}
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def _require_current_user(self, authorization: str | None):
        token = _extract_bearer_token(authorization)
        return self._runtime.auth_gateway.get_current_user(token)

    def _require_service_token(self, service_token: str | None) -> None:
        expected = self._runtime.settings.internal_service_token
        if not expected or not service_token or not hmac.compare_digest(service_token, expected):
            raise UnauthorizedError("invalid service token")


def _extract_bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise UnauthorizedError("missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise UnauthorizedError("empty bearer token")
    return token


def _to_response(view) -> NotificationSettingsResponse:
    return NotificationSettingsResponse(
        timezone=view.timezone,
        timezone_is_default=view.timezone_is_default,
        notifications_enabled=view.notifications_enabled,
        telegram_linked=view.telegram_linked,
    )
