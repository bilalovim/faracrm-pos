# Copyright 2025 FARA CRM
# Chat VK (ВКонтакте) module - application

from backend.base.system.core.app import App


class ChatVkApp(App):
    """Приложение для интеграции с сообществом ВКонтакте (VK Callback API)."""

    info = {
        "name": "Chat VK",
        "summary": "VK (ВКонтакте) community integration for chat module",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat"],
        "sequence": 120,
    }

    def __init__(self):
        super().__init__()

        # Регистрируем стратегию
        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_vk.strategies import VkStrategy

        register_strategy(VkStrategy)
