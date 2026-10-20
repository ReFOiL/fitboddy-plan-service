from __future__ import annotations

import httpx


class TelegramPermanentError(Exception):
    """Чат недоступен: повтор той же доставки ничего не изменит."""


class TelegramTransientError(Exception):
    """Сеть или лимит Telegram: ту же доставку можно повторить."""


class TelegramSender:
    def __init__(self, http_client: httpx.Client, token: str, api_base: str) -> None:
        self._http_client = http_client
        self._token = token.strip()
        self._api_base = api_base.rstrip("/")

    def send(self, chat_id: int, text: str) -> None:
        if not self._token:
            raise TelegramTransientError("telegram bot token is empty")
        url = f"{self._api_base}/bot{self._token}/sendMessage"
        try:
            response = self._http_client.post(
                url,
                json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            )
        except httpx.HTTPError as exc:
            raise TelegramTransientError("telegram request failed") from exc
        if response.status_code == 200:
            payload = response.json()
            if payload.get("ok") is True:
                return
        if response.status_code in {400, 403}:
            raise TelegramPermanentError(_safe_detail(response))
        raise TelegramTransientError(_safe_detail(response))


def _safe_detail(response: httpx.Response) -> str:
    # В лог не попадает токен: описание ошибки Telegram короткое и без секрета запроса.
    body = response.text.replace("\n", " ")
    return f"telegram status {response.status_code}: {body[:180]}"
