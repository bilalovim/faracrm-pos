# Copyright 2025 FARA CRM
# Chat Phone Sipuni module - Sipuni strategy

import csv
import io
import logging
from datetime import datetime
from hashlib import md5
from typing import TYPE_CHECKING, Any

import httpx

from backend.base.crm.chat_phone.strategies.strategy import PhoneStrategyBase
from .adapter import SipuniPhoneAdapter

if TYPE_CHECKING:
    from backend.project_setup import ChatConnector

logger = logging.getLogger(__name__)

# Колонки выгрузки /statistic/export (порядок фиксирован Sipuni).
HISTORY_COLUMNS = [
    "Тип",
    "Статус",
    "Время",
    "ID схемы звонка",
    "Схема",
    "Исходящая линия",
    "Откуда",
    "Куда",
    "Кому звонили",
    "Кто разговаривал",
    "Кто ответил",
    "Длительность звонка, сек",
    "Длительность разговора, сек",
    "Время ответа, сек",
    "Оценка",
    "ID записи",
    "Метка",
    "Теги",
    "Инициатор завершения звонка",
    "ID заказа звонка",
    "Запись существует",
    "Новый клиент",
    "Состояние перезвона",
    "Время перезвона",
    "Информация из CRM",
    "Ответственный из CRM",
]

OPERATOR_COLUMNS = ["Login", "Name", "Status", "Call state"]


class SipuniPhoneStrategy(PhoneStrategyBase):
    """
    Стратегия для интеграции с Sipuni (sipuni.com).

    API документация: https://sipuni.com/ru_RU/integration

    Транспорт как у прочих телефоний: события звонков Sipuni шлёт на webhook
    FARA (event 1/2/3), а историю, записи и список операторов FARA тянет из
    REST API. Авторизация: login + password → MD5-подпись запроса.
    """

    strategy_type = "phone_sipuni"
    TIMEOUT = 30.0

    # ========================================================================
    # Абстрактные методы ChatStrategyBase
    # ========================================================================

    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """Sipuni использует login/password, токен не нужен."""
        return None

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Sipuni не имеет API для установки webhook.
        Webhook URL настраивается вручную в личном кабинете Sipuni.

        Возвращаем True — URL уже сгенерирован.
        """
        logger.info(
            "Sipuni webhook URL generated: %s. "
            "Configure it manually in Sipuni dashboard.",
            connector.webhook_url,
        )
        return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """Sipuni webhook удаляется вручную в ЛК."""
        return {"ok": True}

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> SipuniPhoneAdapter:
        """Создать адаптер для webhook события Sipuni."""
        return SipuniPhoneAdapter(connector, raw_message)

    # ========================================================================
    # Sipuni API — авторизация и запросы
    # ========================================================================

    def _build_sign(self, connector: "ChatConnector", params: dict) -> str:
        """
        Построить HMAC MD5 подпись для API запроса Sipuni.

        Алгоритм:
        1. Добавить user= в params
        2. Сортировать ключи
        3. Склеить значения через '+'
        4. Добавить пароль в конец
        5. MD5 хеш
        """
        params["user"] = connector.access_token or connector.client_app_id
        sorted_values = [str(params[key]) for key in sorted(params.keys())]
        data = "+".join([*sorted_values, connector.refresh_token or ""])
        return md5(data.encode("utf-8")).hexdigest()

    async def _api_request(
        self,
        connector: "ChatConnector",
        path: str,
        params: dict | None = None,
        binary: bool = False,
        csv_content: bool = False,
        csv_fields: list[str] | None = None,
    ):
        """
        Выполнить авторизованный запрос к API Sipuni.

        Args:
            connector: Коннектор с credentials
            path: Путь API (например '/statistic/export')
            params: Параметры запроса
            binary: Вернуть bytes (для скачивания файлов)
            csv_content: Парсить ответ как CSV
            csv_fields: Названия колонок CSV
        """
        params = params or {}
        sign = self._build_sign(connector, params)

        data = {"hash": sign}
        data.update(params)

        base_url = connector.connector_url or "https://sipuni.com/api"
        url = f"{base_url}{path}"

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, data=data)

            if response.status_code == 401:
                raise ValueError(f"Sipuni auth error: {response.text}")
            if response.status_code == 404:
                return {} if not csv_content else []

            if binary:
                return response.content

            if csv_content:
                return self._parse_csv(response.text, csv_fields or [])

            return response.json() if response.text else []

    @staticmethod
    def _parse_csv(text: str, fields: list[str]) -> list[dict]:
        """Парсинг CSV ответа Sipuni."""
        data_file = io.StringIO(text)
        reader = csv.reader(data_file, delimiter=";")
        rows = list(reader)

        if len(rows) <= 1:
            return []

        # Используем переданные fields как ключи
        result = []
        for row in rows[1:]:
            # Расширяем fields если в CSV больше колонок
            keys = fields[:]
            while len(keys) < len(row):
                keys.append(f"col_{len(keys)}")
            result.append(dict(zip(keys, row)))

        return result

    # ========================================================================
    # Номера (операторы Sipuni)
    # ========================================================================

    async def fetch_numbers(self, connector: "ChatConnector") -> list[dict]:
        """
        Операторы (внутренние номера) Sipuni → линии телефонии.

        /statistic/operators отдаёт Login (внутренний номер), Name, Status,
        Call state. Login и есть extension: по нему матчится sip-контакт
        сотрудника и распознаётся «наша нога» звонка.
        """
        operators = await self._api_request(
            connector,
            "/statistic/operators",
            csv_content=True,
            csv_fields=OPERATOR_COLUMNS,
        )

        records = []
        for rec in operators or []:
            login = (rec.get("Login") or "").strip()
            if not login:
                continue
            records.append(
                {
                    "external_id": f"operator:{login}",
                    "kind": "number",
                    "number": login,
                    "extension": login,
                    "name": rec.get("Name") or login,
                    "user_key": login,
                    "raw": rec,
                }
            )
        return records

    # ========================================================================
    # Скачивание записей разговоров
    # ========================================================================

    async def _download_call_record(
        self,
        connector: "ChatConnector",
        adapter: SipuniPhoneAdapter,
    ) -> bytes | None:
        """
        Скачать запись разговора через Sipuni API.

        В webhook Sipuni кладёт call_record_link — прямой URL на запись; в
        выгрузке истории ссылки нет, только признак наличия (адаптер отдаёт
        маркер), и файл тянется по id через /statistic/record.
        """
        # Вариант 1: прямая ссылка из webhook
        record_link = adapter.call_record_url
        if record_link and record_link.startswith("http"):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(record_link)
                    if response.status_code == 200 and response.content:
                        return response.content
            except Exception as e:
                logger.warning(
                    "[phone_sipuni] Direct download failed: %s, trying API",
                    e,
                )

        # Вариант 2: через API
        call_id = adapter.message_id
        if call_id:
            try:
                content = await self._api_request(
                    connector,
                    "/statistic/record",
                    params={"id": call_id},
                    binary=True,
                )
                if content and len(content) > 100:  # Минимальный размер MP3
                    return content
            except Exception as e:
                logger.error(
                    "[phone_sipuni] API download failed for %s: %s",
                    call_id,
                    e,
                )

        return None

    # ========================================================================
    # История звонков (импорт вручную / cron)
    # ========================================================================

    async def fetch_call_history(
        self,
        connector: "ChatConnector",
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        """
        История звонков через /statistic/export (CSV) за период.

        Даты Sipuni принимает как DD.MM.YYYY + ОТДЕЛЬНО время суток HH:MM, и
        время применяется к КАЖДОМУ дню периода. Поэтому у окна через полночь
        (23:40..00:40) пара timeFrom > timeTo противоречива и час до полуночи
        не пришёл бы никогда — а именно так выглядит окно крона в 00:40.
        Для такого окна просим сутки целиком, а лишнее отсекаем по времени
        записи (_within): границы периода всё равно соблюдаются.
        """
        start = start_date.astimezone()
        end = end_date.astimezone()
        same_day = start.date() == end.date()
        params = {
            "from": f"{start:%d.%m.%Y}",
            "to": f"{end:%d.%m.%Y}",
            "timeFrom": f"{start:%H:%M}" if same_day else "00:00",
            "timeTo": f"{end:%H:%M}" if same_day else "23:59",
            "type": "0",  # Все звонки
            "state": "0",  # Все статусы
            "tree": "",
            "rating": "",
            "showTreeId": "1",
            "fromNumber": "",
            "toNumber": "",
            "numbersRinged": 1,
            "numbersInvolved": 1,
            "names": 1,
            "outgoingLine": 1,
            "toAnswer": "",
            "anonymous": "0",
            "firstTime": "0",
            "dtmfUserAnswer": 0,
            "hangupinitor": "1",
            "crmLinks": 0,
            "ignoreSpecChar": "0",
        }

        rows = await self._api_request(
            connector,
            "/statistic/export",
            params=params,
            csv_content=True,
            csv_fields=HISTORY_COLUMNS,
        )
        events = [self._history_row_to_event(row) for row in rows or []]
        return [
            event
            for event in events
            if event and self._within(event, start, end)
        ]

    @staticmethod
    def _within(event: dict, start: datetime, end: datetime) -> bool:
        """Запись попадает в запрошенное окно. Время не распознали — оставляем
        (лучше лишняя запись, чем молча потерянный звонок)."""
        started = event.get("call_start_timestamp") or 0
        if not started:
            return True
        return start.timestamp() <= started <= end.timestamp()

    @staticmethod
    def _history_row_to_event(row: dict) -> dict | None:
        """
        Строка выгрузки статистики → событие ЗАВЕРШЕНИЯ звонка (event=2), т.е.
        та же форма, что приходит на webhook, — её разбирает тот же адаптер.

        Статус берём не из локализованной колонки, а по факту разговора
        (длительность разговора > 0 → ANSWER), чтобы не зависеть от языка ЛК.
        """
        call_id = (row.get("ID записи") or "").strip()
        if not call_id:
            return None

        def as_int(value) -> int:
            try:
                return int(float(str(value).replace(",", ".")))
            except (TypeError, ValueError):
                return 0

        duration = as_int(row.get("Длительность звонка, сек"))
        talk = as_int(row.get("Длительность разговора, сек"))
        start_ts = SipuniPhoneStrategy._parse_history_time(row.get("Время"))
        operator = (row.get("Кто разговаривал") or "").strip()

        return {
            "event": 2,  # завершение звонка
            "call_id": call_id,
            "src_num": (row.get("Откуда") or "").strip(),
            "dst_num": (row.get("Куда") or "").strip(),
            # Оператор — «наша нога»: в выгрузке это внутренний номер.
            "short_src_num": operator if row.get("Тип") == "Исходящий" else "",
            "short_dst_num": "" if row.get("Тип") == "Исходящий" else operator,
            "status": "ANSWER" if talk else "NOANSWER",
            "call_start_timestamp": start_ts,
            "call_answer_timestamp": (
                start_ts + max(0, duration - talk) if start_ts and talk else 0
            ),
            "timestamp": start_ts + duration if start_ts else 0,
            # Ссылки на запись в выгрузке нет — только признак её наличия;
            # файл тянется по id через API (см. _download_call_record).
            "call_record_link": "",
            "has_record": SipuniPhoneStrategy._as_bool(
                row.get("Запись существует")
            ),
        }

    @staticmethod
    def _as_bool(value) -> bool:
        """Флаг выгрузки («1» / «Да» / «true») → bool."""
        return str(value or "").strip().lower() in ("1", "да", "yes", "true")

    @staticmethod
    def _parse_history_time(value: str | None) -> int:
        """Время звонка из выгрузки → unix timestamp (0, если не распознали)."""
        raw = (value or "").strip()
        if not raw:
            return 0
        for fmt in (
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return int(datetime.strptime(raw, fmt).timestamp())
            except ValueError:
                continue
        try:
            return int(datetime.fromisoformat(raw).timestamp())
        except ValueError:
            logger.warning(
                "[phone_sipuni] не распознали время звонка: %r", raw
            )
            return 0
