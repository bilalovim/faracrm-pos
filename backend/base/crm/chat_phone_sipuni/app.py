# Copyright 2025 FARA CRM
# Chat Phone Sipuni module - application configuration

from typing import TYPE_CHECKING

from backend.base.system.core.app import App
from backend.base.crm.chat_phone.app import register_phone_crons

if TYPE_CHECKING:
    from fastapi import FastAPI


class ChatPhoneSipuniApp(App):
    """
    Интеграция с Sipuni (sipuni.com) для телефонии.

    Добавляет:
    - Тип коннектора 'phone_sipuni'
    - Стратегию обработки webhook событий Sipuni
    - API для получения звонков и записей

    Webhook события Sipuni:
    - event=1: начало внутреннего дозвона (is_inner_call=1)
    - event=2: завершение звонка (status=ANSWER|NOANSWER|BUSY|CANCEL...)
    - event=3: ответ на звонок (сняли трубку)

    Настройка:
    - login: логин Sipuni
    - password: пароль Sipuni
    - connector_url: https://sipuni.com/api
    """

    info = {
        "name": "Chat Phone Sipuni",
        "summary": "Sipuni telephony integration",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat_phone", "cron"],
        "sequence": 116,
        "post_init": True,
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_phone_sipuni.strategies import (
            SipuniPhoneStrategy,
        )

        register_strategy(SipuniPhoneStrategy)

    async def post_init(self, app: "FastAPI"):
        """Cron импорта истории звонков и синхронизации номеров (по умолчанию
        неактивны — включаются вручную в списке cron-задач)."""
        await super().post_init(app)
        await register_phone_crons(
            app.state.env, label="Sipuni", strategy_type="phone_sipuni"
        )
