# Copyright 2025 FARA CRM
# Chat VK (ВКонтакте) module - connector mixin

import secrets
from typing import TYPE_CHECKING

from backend.base.system.core.enviroment import env
from backend.base.system.core.extensions import extend
from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.system.dotorm.dotorm.decorators import onchange
from backend.base.system.dotorm.dotorm.fields import Selection

# поддержка IDE, видны все аттрибуты базового класса
if TYPE_CHECKING:
    _Base = ChatConnector
else:
    _Base = object


@extend(ChatConnector)
class ChatConnectorVkMixin(_Base):
    """
    Миксин для ChatConnector с поддержкой мессенджера ВКонтакте.

    Добавляет:
    - Тип 'vk' в Selection поле type
    - Метод для генерации defaults при создании

    В IDE: наследует ChatConnector - видны все поля
    В runtime: @extend применяет расширение к ChatConnector

    Интеграция строится на СООБЩЕСТВЕ ВКонтакте (группа/публичная страница) и
    Callback API:
    - access_token — ключ доступа сообщества (Управление → Настройки → Работа с
      API → Ключи доступа). Нужны права `messages` (и `manage`, чтобы бэкенд мог
      сам зарегистрировать callback-сервер).
    - external_account_id — числовой id сообщества (group_id). Можно заполнить
      кнопкой «Получить данные сообщества» (метод groups.getById).
    - connector_url — https://api.vk.com/method (по умолчанию).

    В отличие от MAX/WhatsApp, у ВКонтакте НЕТ отдельного «бизнес»-канала с
    отправкой первым по номеру телефона: всё общение идёт через сообщество,
    получатель адресуется по user_id (peer_id), пришедшему в вебхуке. Поэтому
    модуль ОДИН (`vk`), а тип контакта — `vk` (не телефонного формата).
    """

    DEFAULT_CONNECTOR_URL_VK = "https://api.vk.com/method"

    # Расширяем Selection поле type
    type: str = Selection(selection_add=[("vk", "ВКонтакте")])

    @onchange("type")
    async def onchange_type_vk(self) -> dict:
        """
        Устанавливает значения по умолчанию при выборе типа vk.

        Returns:
            Словарь с connector_url, webhook_url, webhook_hash, category,
            contact_type_id.
        """
        if self.type == "vk":
            # webhook_hash используется как secret_key callback-сервера VK
            # (латиница/цифры/дефис — token_hex подходит) и как проверка в URL.
            webhook_hash = secrets.token_hex(20)
            webhook_url = f"YOUR_URL/chat/webhook/{webhook_hash}/CONNECTOR_ID"

            result = {
                "connector_url": self.DEFAULT_CONNECTOR_URL_VK,
                "webhook_url": webhook_url,
                "webhook_hash": webhook_hash,
                "category": "messenger",
            }

            # VK-сообщество адресует клиента по user_id (peer_id), НЕ по номеру →
            # тип контакта `vk` (is_phone_format=False, засеян в contact_type).
            vk_type = await env.models.contact_type.search(
                filter=[("name", "=", "vk")],
                fields=["id", "name"],
                limit=1,
            )
            if vk_type:
                result["contact_type_id"] = vk_type[0]
            return result
        return {}
