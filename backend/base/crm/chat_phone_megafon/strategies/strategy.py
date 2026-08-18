# Copyright 2025 FARA CRM
# Chat Phone MegaFon module - MegaFon VATS strategy

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Tuple

import httpx

from backend.base.crm.chat_phone.strategies.strategy import PhoneStrategyBase
from .adapter import MegafonPhoneAdapter

if TYPE_CHECKING:
    from backend.project_setup import ChatConnector
    from backend.base.crm.partners.models.contact import Contact

logger = logging.getLogger(__name__)


class MegafonPhoneStrategy(PhoneStrategyBase):
    """
    Стратегия для интеграции с МегаФон ВАТС (Виртуальная АТС).

    MegaFon REST API:
    - Base URL: https://{domain}/crmapi/v1/
    - Auth: X-API-KEY header
    - Docs: https://api.megapbx.ru/

    Webhook (входящие от MegaFon → FARA):
    - Один URL для всех команд: /chat/webhook/{hash}/{connector_id}
      (секрет — webhook_hash в самом URL, как у остальных коннекторов)
    - Команды: history, event, contact, rating

    Поддерживает:
    - Приём событий звонков (event: INCOMING/ACCEPTED/COMPLETED/CANCELLED)
    - Приём завершённых звонков с записью (history)
    - Получение истории звонков через API
    - Синхронизация операторов/номеров
    - Инициация исходящих звонков (make_call)

    Настройка полей ChatConnector:
    - connector_url: https://{domain}/crmapi/v1
    - access_token: API ключ (X-API-KEY для исходящих запросов)
    """

    strategy_type = "phone_megafon"
    TIMEOUT = 30.0

    # ========================================================================
    # Абстрактные методы ChatStrategyBase
    # ========================================================================

    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """MegaFon использует статичный API ключ, обновление не требуется."""
        return connector.access_token

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        MegaFon VATS webhook настраивается в личном кабинете.
        URL: https://your-domain/chat/webhook/{hash}/{connector_id}

        Проверяем доступность API для валидации настроек.
        """
        try:
            # Проверяем что API доступен
            users = await self._api_request(connector, "/users")
            logger.info(
                "MegaFon API accessible, %d users found. "
                "Configure webhook URL in MegaFon VATS cabinet: %s",
                len(users) if isinstance(users, list) else 0,
                connector.webhook_url,
            )
            return True
        except Exception as e:
            logger.warning(
                "MegaFon API check failed: %s. "
                "Webhook URL still generated: %s",
                e,
                connector.webhook_url,
            )
            return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """MegaFon webhook удаляется вручную в ЛК."""
        return {"ok": True}

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "Contact",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
        thread_message_id: str | None = None,
        attachments: list | None = None,
    ) -> Tuple[str, str]:
        """
        Инициация исходящего звонка через MegaFon VATS API.

        POST /crmapi/v1/makecall
        Body: {"phone": "79991234567", "user": "operator_login", "clid": "71117772211"}

        Args:
            connector: Коннектор MegaFon
            user_from: Контакт оператора (содержит логин/extension)
            body: Не используется для звонков
            chat_id: Номер телефона для звонка
            recipients_ids: Альтернативный способ передачи номера

        Returns:
            Tuple[callid, phone_number]
        """
        phone = chat_id
        if not phone and recipients_ids:
            phone = recipients_ids[0].get("contact_value")

        if not phone:
            raise ValueError("Cannot make call without phone number")

        # Определяем логин оператора из контакта
        operator_login = user_from.name if user_from else None
        if not operator_login:
            raise ValueError("Cannot make call without operator login")

        payload = {
            "phone": phone,
            "user": operator_login,
        }

        result = await self._api_request(
            connector, "/makecall", method="POST", json_data=payload
        )

        callid = ""
        if isinstance(result, dict):
            callid = result.get("callid", "")

        logger.info(
            "MegaFon makecall: %s → %s, callid=%s",
            operator_login,
            phone,
            callid,
        )

        return str(callid), str(phone)

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> MegafonPhoneAdapter:
        """Создать адаптер для webhook команды MegaFon."""
        return MegafonPhoneAdapter(connector, raw_message)

    # ========================================================================
    # MegaFon REST API — авторизованные запросы
    # ========================================================================

    def _get_headers(self, connector: "ChatConnector") -> dict:
        """Заголовки авторизации для запросов к MegaFon VATS API."""
        return {
            "X-API-KEY": connector.access_token or "",
            "Content-Type": "application/json",
        }

    async def _api_request(
        self,
        connector: "ChatConnector",
        path: str,
        method: str = "GET",
        params: dict | None = None,
        json_data: dict | None = None,
    ):
        """
        Выполнить авторизованный запрос к MegaFon VATS REST API.

        Args:
            connector: Коннектор с credentials
            path: Путь API (например '/users', '/history/json', '/makecall')
            method: HTTP метод
            params: URL query параметры
            json_data: JSON body для POST/PUT
        """
        base_url = (connector.connector_url or "").rstrip("/")
        url = f"{base_url}{path}"
        headers = self._get_headers(connector)

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
            )

            if response.status_code == 401:
                raise ValueError(f"MegaFon VATS auth error: {response.text}")
            if response.status_code == 404:
                return {}

            if response.text:
                return response.json()
            return {}

    # ========================================================================
    # Скачивание записей разговоров
    # ========================================================================

    async def _download_call_record(
        self,
        connector: "ChatConnector",
        adapter: MegafonPhoneAdapter,
    ) -> bytes | None:
        """
        Скачать запись разговора по ссылке из history.

        MegaFon предоставляет прямую ссылку на MP3 файл
        в поле 'link' команды history.
        """
        record_url = adapter.call_record_url
        if not record_url:
            return None

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(record_url)
                if response.status_code == 200 and len(response.content) > 100:
                    return response.content
                logger.warning(
                    "[phone_megafon] Record download returned %d, %d bytes",
                    response.status_code,
                    len(response.content),
                )
        except Exception as e:
            logger.error("[phone_megafon] Failed to download record: %s", e)

        return None

    # ========================================================================
    # Пакетный импорт (cron)
    # ========================================================================

    async def fetch_call_history(
        self,
        connector: "ChatConnector",
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        """
        Получить историю звонков через MegaFon API.

        GET /crmapi/v1/history/json?start={from}&end={to}&type=all

        Записи истории — та же форма, что у webhook-команды `history`, поэтому
        помечаем их cmd='history' и отдаём как есть: разбирает тот же адаптер.
        Даты MegaFon принимает в UTC-формате 20260101T000000Z.
        """
        params = {
            "start": f"{start_date.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}",
            "end": f"{end_date.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}",
            "type": "all",
            "limit": 1000,
        }
        result = await self._api_request(
            connector, "/history/json", params=params
        )

        if isinstance(result, dict):
            result = result.get("items") or []
        if not isinstance(result, list):
            return []
        return [{**row, "cmd": "history"} for row in result]

    async def fetch_users(self, connector: "ChatConnector") -> list[dict]:
        """
        Получить список пользователей (операторов) из MegaFon VATS.

        GET /crmapi/v1/users

        Returns:
            Список пользователей с полями: login, name, telnum, ext, etc.
        """
        result = await self._api_request(connector, "/users")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return []

    async def fetch_numbers(self, connector: "ChatConnector") -> list[dict]:
        """
        Линии MegaFon ВАТС: extension'ы операторов (из /users) и сами номера
        ВАТС (telnum) как транки.

        Extension — «наша нога» разговора, по нему матчится sip-контакт
        сотрудника; telnum — линия, на которую приходит входящий (diversion),
        она общая для нескольких операторов, поэтому заводится один раз и без
        привязки к сотруднику.
        """
        users = await self.fetch_users(connector)

        records: list[dict] = []
        trunks: set[str] = set()
        for rec in users:
            login = str(rec.get("login") or "").strip()
            ext = str(rec.get("ext") or "").strip()
            telnum = str(rec.get("telnum") or "").strip()

            if ext:
                records.append(
                    {
                        "external_id": f"ext:{ext}",
                        "kind": "number",
                        "number": ext,
                        "extension": ext,
                        "name": rec.get("name") or login or ext,
                        "user_key": ext,
                        "raw": rec,
                    }
                )
            if telnum and telnum not in trunks:
                trunks.add(telnum)
                records.append(
                    {
                        "external_id": f"line:{telnum}",
                        "kind": "trunk",
                        "number": telnum,
                        "extension": None,
                        "name": telnum,
                        "user_key": None,
                        "raw": {"telnum": telnum},
                    }
                )
        return records

    async def make_call(
        self,
        connector: "ChatConnector",
        phone: str,
        user_login: str,
        clid: str | None = None,
    ) -> dict:
        """
        Инициировать исходящий звонок.

        POST /crmapi/v1/makecall

        Args:
            connector: Коннектор
            phone: Номер для звонка
            user_login: Логин оператора
            clid: Caller ID (какой номер показать клиенту)

        Returns:
            Ответ API: {"callid": "...", "clid": "..."}
        """
        payload = {"phone": phone, "user": user_login}
        if clid:
            payload["clid"] = clid

        result = await self._api_request(
            connector, "/makecall", method="POST", json_data=payload
        )
        return result if isinstance(result, dict) else {}
