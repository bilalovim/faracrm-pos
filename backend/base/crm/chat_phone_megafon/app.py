# Copyright 2025 FARA CRM
# Chat Phone MegaFon module - application configuration

from typing import TYPE_CHECKING

from backend.base.system.core.app import App
from backend.base.crm.chat_phone.app import register_phone_crons

if TYPE_CHECKING:
    from fastapi import FastAPI


class ChatPhoneMegafonApp(App):
    """
    Интеграция с МегаФон ВАТС (Виртуальная АТС).

    Добавляет:
    - Тип коннектора 'phone_megafon'
    - Стратегию обработки webhook команд MegaFon VATS
    - API для получения звонков, записей и инициации исходящих

    MegaFon VATS API:
    - Base URL: https://{domain}/crmapi/v1/
    - Auth: X-API-KEY header
    - Webhooks: POST с полем 'cmd' (history/event/contact/rating)

    Webhook команды:
    - history: завершённый звонок с записью
    - event: real-time события (INCOMING, ACCEPTED, COMPLETED, CANCELLED, OUTGOING, TRANSFERRED)
    - contact: запрос имени контакта по номеру
    - rating: оценка качества звонка

    Настройка коннектора:
    - connector_url: https://{domain}/crmapi/v1 (из ЛК МегаФон ВАТС)
    - access_token: API ключ (X-API-KEY)
    """

    info = {
        "name": "Chat Phone MegaFon",
        "summary": "MegaFon VATS telephony integration",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat_phone", "cron"],
        "sequence": 117,
        "post_init": True,
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_phone_megafon.strategies import (
            MegafonPhoneStrategy,
        )

        register_strategy(MegafonPhoneStrategy)

    async def post_init(self, app: "FastAPI"):
        """Cron импорта истории звонков и синхронизации номеров (по умолчанию
        неактивны — включаются вручную в списке cron-задач)."""
        await super().post_init(app)
        await register_phone_crons(
            app.state.env, label="MegaFon", strategy_type="phone_megafon"
        )
