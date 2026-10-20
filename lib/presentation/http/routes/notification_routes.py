from fastapi import APIRouter, Header, Request, Response, status

from presentation.http.schemas import (
    ConfirmTelegramLinkRequest,
    NotificationSettingsResponse,
    TelegramLinkCodeResponse,
    UpdateNotificationSettingsRequest,
)


class NotificationRoutes:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/v1", tags=["notifications"])
        self.router.add_api_route(
            "/plans/me/notifications/settings",
            self.get_settings,
            methods=["GET"],
            response_model=NotificationSettingsResponse,
        )
        self.router.add_api_route(
            "/plans/me/notifications/settings",
            self.update_settings,
            methods=["PUT"],
            response_model=NotificationSettingsResponse,
        )
        self.router.add_api_route(
            "/plans/me/notifications/telegram/link-code",
            self.issue_link_code,
            methods=["POST"],
            response_model=TelegramLinkCodeResponse,
        )
        self.router.add_api_route(
            "/plans/me/notifications/telegram",
            self.unlink_telegram,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
            response_class=Response,
        )
        self.router.add_api_route(
            "/plans/internal/notifications/telegram",
            self.confirm_telegram,
            methods=["POST"],
        )

    @staticmethod
    def get_settings(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> NotificationSettingsResponse:
        return request.app.state.notification_handler.get_settings(authorization=authorization)

    @staticmethod
    def update_settings(
        request: Request,
        payload: UpdateNotificationSettingsRequest,
        authorization: str | None = Header(default=None),
    ) -> NotificationSettingsResponse:
        return request.app.state.notification_handler.update_settings(authorization=authorization, payload=payload)

    @staticmethod
    def issue_link_code(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> TelegramLinkCodeResponse:
        return request.app.state.notification_handler.issue_link_code(authorization=authorization)

    @staticmethod
    def unlink_telegram(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> Response:
        request.app.state.notification_handler.unlink_telegram(authorization=authorization)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def confirm_telegram(
        request: Request,
        payload: ConfirmTelegramLinkRequest,
        x_service_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        return request.app.state.notification_handler.confirm_telegram(
            service_token=x_service_token,
            payload=payload,
        )
