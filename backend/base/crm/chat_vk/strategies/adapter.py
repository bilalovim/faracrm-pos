# Copyright 2025 FARA CRM
# Chat module - VK (ВКонтакте) message adapter

import mimetypes

from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter


class VkMessageAdapter(ChatMessageAdapter):
    """
    Адаптер для парсинга событий Callback API сообщества ВКонтакте.

    Формат входящего события (message_new, API v5.103+):
    {
        "type": "message_new",
        "v": "5.199",
        "group_id": 222222,
        "event_id": "abcdef...",
        "object": {
            "message": {
                "id": 12345,
                "conversation_message_id": 45,
                "from_id": 111111,      # id пользователя (>0)
                "peer_id": 111111,      # для лички peer_id == from_id
                "date": 1690000000,
                "text": "привет",
                "attachments": [
                    {"type": "photo", "photo": {"sizes": [
                        {"url": "https://...", "width": 130, "height": 90}, ...
                    ]}},
                    {"type": "doc", "doc": {"url": "https://...",
                                             "title": "file.pdf", "ext": "pdf"}}
                ]
            },
            "client_info": {...}
        }
    }

    ВАЖНО: имя отправителя VK в вебхуке НЕ присылает (только from_id) — оно
    докручивается стратегией через users.get (см. VkStrategy.resolve_partner).

    Документация: https://dev.vk.com/ru/api/community-events/json-schema
    """

    @property
    def event_type(self) -> str:
        """Тип события Callback API (message_new, confirmation, ...)."""
        return self.raw.get("type", "")

    @property
    def _object(self) -> dict:
        """Объект события (object)."""
        return self.raw.get("object", {}) or {}

    @property
    def _message(self) -> dict:
        """
        Объект сообщения.

        В API v5.103+ сообщение лежит в object.message; в старых версиях —
        прямо в object. Поддерживаем оба варианта.
        """
        obj = self._object
        if "message" in obj and isinstance(obj.get("message"), dict):
            return obj.get("message", {}) or {}
        return obj

    @property
    def _attachments(self) -> list[dict]:
        """Список вложений сообщения."""
        return self._message.get("attachments", []) or []

    @property
    def message_id(self) -> str:
        """
        ID сообщения в VK.

        Глобальный message.id надёжен для сообщений сообществу; при его
        отсутствии используем conversation_message_id (уникален в рамках
        диалога).
        """
        mid = self._message.get("id") or self._message.get(
            "conversation_message_id"
        )
        return str(mid or "")

    @property
    def chat_id(self) -> str:
        """
        Ключ диалога в VK — peer_id.

        Для личной переписки с пользователем peer_id == from_id (id
        пользователя). messages.send адресуется этим же peer_id.
        """
        peer_id = self._message.get("peer_id") or self._message.get("from_id")
        return str(peer_id or "")

    @property
    def author_id(self) -> str:
        """ID отправителя (from_id)."""
        return str(self._message.get("from_id", ""))

    @property
    def text(self) -> str | None:
        """Текст сообщения."""
        return self._message.get("text")

    @property
    def author_name(self) -> str | None:
        """
        Имя отправителя.

        В вебхуке VK имени нет — стратегия докручивает его через users.get и
        передаёт как display_name. Здесь возвращаем None (fallback на id).
        """
        return None

    @property
    def created_at(self) -> int:
        """Unix timestamp создания сообщения (секунды)."""
        return self._message.get("date", 0)

    @property
    def images(self) -> list[str]:
        """
        Список URL изображений (вложения type=photo, наибольший размер).

        Базовая стратегия скачает их через file_download по прямому url.
        """
        urls: list[str] = []
        for att in self._attachments:
            if att.get("type") != "photo":
                continue
            photo = att.get("photo") or {}
            sizes = photo.get("sizes") or []
            if not sizes:
                continue
            # Берём размер с наибольшей площадью.
            largest = max(
                sizes,
                key=lambda s: (s.get("width", 0) or 0)
                * (s.get("height", 0) or 0),
            )
            url = largest.get("url")
            if url:
                urls.append(url)
        return urls

    @property
    def files(self) -> list[dict]:
        """
        Список файлов (вложения type=doc/audio_message/video), у которых есть
        прямой url для скачивания.

        Каждый элемент — словарь {url, name, mime_type}. Базовая стратегия
        использует ключ `url`.
        """
        result: list[dict] = []
        for att in self._attachments:
            att_type = att.get("type")

            if att_type == "doc":
                doc = att.get("doc") or {}
                url = doc.get("url")
                if not url:
                    continue
                filename = doc.get("title") or "document"
                mime_type = (
                    mimetypes.guess_type(filename)[0]
                    or "application/octet-stream"
                )
                result.append(
                    {
                        "url": url,
                        "name": filename,
                        "mime_type": mime_type,
                        "file_size": doc.get("size", 0),
                    }
                )
            elif att_type == "audio_message":
                audio = att.get("audio_message") or {}
                url = audio.get("link_mp3") or audio.get("link_ogg")
                if not url:
                    continue
                result.append(
                    {
                        "url": url,
                        "name": "voice.mp3",
                        "mime_type": "audio/mpeg",
                        "file_size": 0,
                    }
                )
        return result

    @property
    def should_skip(self) -> bool:
        """
        Определить нужно ли пропустить обработку события.

        Пропускаем:
        - Все события кроме message_new (confirmation обрабатывается стратегией
          отдельно, прочие апдейты нам не нужны).
        - Сообщения без from_id / без id.
        - Сообщения от самого сообщества (from_id < 0 — это group_id со знаком
          минус, т.е. эхо нашего исходящего).
        """
        if self.event_type and self.event_type != "message_new":
            return True

        if not self._message.get("from_id"):
            return True

        # from_id < 0 → отправитель = сообщество (наше исходящее). Не заводим на
        # него партнёра.
        try:
            if int(self._message.get("from_id", 0)) < 0:
                return True
        except (TypeError, ValueError):
            return True

        if not self.message_id:
            return True

        return False

    @property
    def is_from_external(self) -> bool:
        """
        Сообщение от внешнего пользователя (не от нашего сообщества).

        VK при подписке только на message_new присылает вебхук лишь на входящие
        сообщения пользователей. Исходящие оператора приходят отдельным событием
        message_reply, на которое мы не подписываемся. Дополнительно
        страхуемся: from_id > 0 — это пользователь.
        """
        try:
            return int(self._message.get("from_id", 0)) > 0
        except (TypeError, ValueError):
            return True
