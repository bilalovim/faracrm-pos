# Copyright 2025 FARA CRM
# Chat MAX (business) module - application

from backend.base.system.core.app import App


class ChatMaxBusinessApp(App):
    """Канал «MAX для бизнеса» (platform-api.max.ru).

    По факту это тот же MAX Bot API, что и бот-коннектор (chat_max_bot):
    получатель адресуется по chat_id из вебхука, отправка POST /messages.
    Официального write-first по номеру телефона у MAX-API НЕТ (см.
    MaxBusinessStrategy) — стратегия наследует поведение max_bot целиком,
    поэтому «бот» и «бизнес» для клиента работают одинаково. Отправка первым
    по номеру возможна только через сторонний агрегатор (chat_max_wamm).
    """

    info = {
        "name": "Chat MAX Business",
        "summary": (
            "MAX for Business (platform-api.max.ru) — тот же Bot API, что и "
            "max_bot; адресация по chat_id из вебхука"
        ),
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        # chat_max_bot — стратегия наследует MaxBotStrategy.
        "depends": ["chat", "chat_max_bot"],
        "sequence": 122,
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_max_business.strategies import (
            MaxBusinessStrategy,
        )

        register_strategy(MaxBusinessStrategy)
