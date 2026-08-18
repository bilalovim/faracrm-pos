# Copyright 2025 FARA CRM
# Chat Phone Asterisk module - application configuration

from typing import TYPE_CHECKING

from backend.base.system.core.app import App
from backend.base.crm.chat_phone.app import register_phone_crons
from backend.base.crm.security.acl_post_init_mixin import ACL

if TYPE_CHECKING:
    from fastapi import FastAPI


class ChatPhoneAsteriskApp(App):
    """
    Интеграция с Asterisk / FreePBX через внешний Asterisk-agent (FastAPI рядом
    с АТС): ARI-события агент шлёт на универсальный webhook FARA, а историю (CDR),
    записи разговоров и номера FARA тянет из REST API агента по HTTP Basic-auth.
    """

    info = {
        "name": "Chat Phone Asterisk",
        "summary": "Asterisk / FreePBX telephony integration",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.2.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat_phone", "cron"],
        "sequence": 118,
        "post_init": True,
    }

    # asterisk_log — журнал телефонии (экран «События»): правит система (запись
    # ведёт приём ARI-событий), юзерам — чтение. Без ACL модель default-deny.
    BASE_USER_ACL = {
        "asterisk_log": ACL.READ_ONLY,
    }
    ROLE_ACL = {
        "system_admin": {
            "asterisk_log": ACL.FULL,
        },
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_phone_asterisk.strategies import (
            AsteriskPhoneStrategy,
        )

        register_strategy(AsteriskPhoneStrategy)

    async def post_init(self, app: "FastAPI"):
        """Cron импорта истории звонков и синхронизации номеров (по умолчанию
        неактивны — включаются вручную в списке cron-задач)."""
        await super().post_init(app)
        await register_phone_crons(
            app.state.env, label="Asterisk", strategy_type="phone_asterisk"
        )
