# Copyright 2025 FARA CRM
# Chat module - base strategy pattern

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, Tuple
import json
import logging
import mimetypes

from backend.base.crm.users.models.users import SYSTEM_USER_ID
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.partners.models.contact import Contact
    from backend.base.crm.attachments.models.attachments import Attachment
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter

logger = logging.getLogger(__name__)


class IncomingRoute(str, Enum):
    """
    Судьба входящего сообщения — ВСЕ возможные исходы, по одному имени на исход.

    Порядок принятия решения: ПЕРЕПИСКА → СВЯЗЬ → ХОЛОДНЫЙ СТАРТ.
    Он важен: только переписка различает два наших чата с одним адресатом
    (личный и групповой) — адрес у них общий. Не менять местами.
    """

    # Не поняли, КТО ИЗ ДВОИХ клиент: resolve_partner вернул (None, None).
    #
    # ЭТО НЕ «незнакомый отправитель» — незнакомый как раз обрабатывается и
    # попадает в NEW_CHAT_NEW_PARTNER. Здесь мы не смогли определить
    # контрагента ВООБЩЕ, и до создания контакта дело не доходит.
    # Пример: Avito шлёт вебхук и на наши СОБСТВЕННЫЕ исходящие и не отличает
    # нас от клиента в author_id — он лезет за участниками чата, и если не
    # вышло, отдаёт пусто. Пропускаем, чтобы не завести партнёра и лид на наш
    # же магазин.
    SKIP_COUNTERPARTY_NOT_RESOLVED = "skip_counterparty_not_resolved"

    # Сообщение само сказало, куда лечь: «я ответ вон на те». Только email.
    ROUTED_BY_THREAD = "routed_by_thread"

    # Адрес/тред уже привязан к чату (chat_external_chat). Основной путь.
    ROUTED_BY_LINK = "routed_by_link"

    # Переписки нет, контакта раньше не было → завели партнёра и его чат.
    NEW_CHAT_NEW_PARTNER = "new_chat_new_partner"

    # Переписки нет, но партнёр уже известен → открыли/нашли его чат.
    NEW_CHAT_KNOWN_PARTNER = "new_chat_known_partner"

    # Наш сотрудник написал на общий адрес, переписки с ним ещё нет. Класть
    # некуда: адрес общий, конкретного чата он не выбрал. Партнёра и лида на
    # сотрудника не заводим. Если МЫ написали первыми — сюда не дойдёт,
    # сработает ROUTED_BY_THREAD/ROUTED_BY_LINK.
    SKIP_OWN_USER = "skip_own_user"

    # Контакт есть, но у него не заполнен ни партнёр, ни пользователь. XOR-
    # констрейнта на модели нет, поэтому случай представим. Раньше здесь
    # бросался ValueError — по решению владельца это тоже пропуск: одно битое
    # сообщение не должно блокировать очередь коннектора.
    SKIP_NO_PARTNER_NO_USER = "skip_no_partner_no_user"


# Исходы, при которых чата нет и обрабатывать нечего.
_SKIP_ROUTES = frozenset(
    {
        IncomingRoute.SKIP_COUNTERPARTY_NOT_RESOLVED,
        IncomingRoute.SKIP_OWN_USER,
        IncomingRoute.SKIP_NO_PARTNER_NO_USER,
    }
)


class ChatStrategyBase(ABC):
    """
    Базовый класс стратегии для работы с внешними сервисами.

    Реализует паттерн Strategy для легкого добавления новых провайдеров
    (Telegram, WhatsApp, Avito и т.д.) без изменения основного кода.

    Каждый провайдер реализует свой класс стратегии, наследуя от этого.

    Шаблонный метод handle_webhook содержит общую логику обработки
    входящих сообщений. Конкретные стратегии переопределяют только
    create_message_adapter для парсинга специфичного формата.
    """

    # Уникальный тип стратегии (должен совпадать с connector.type)
    strategy_type: str = ""

    # Умеет ли стратегия слать вложения ВНУТРИ сообщения (одним отправлением).
    #
    # False (дефолт) — база шлёт каждое вложение отдельным вызовом
    # chat_send_message_binary. Для мессенджеров это верно: в Telegram/Avito
    # файл — самостоятельное сообщение.
    # True — база НЕ крутит цикл, а передаёт список в chat_send_message, и
    # стратегия сама укладывает файлы в одно отправление. Так делает email:
    # формат письма ровно для этого и придуман (multipart/mixed), а раньше
    # «текст + 2 файла» уходило ТРЕМЯ письмами.
    attachments_inline: bool = False

    # Умеет ли канал нести в самом сообщении пометку «это ответ на такое-то».
    #
    # True только у email: письмо несёт её заголовком In-Reply-To, и почтовик
    # получателя собирает переписку в одну ветку. У мессенджеров такого нет и
    # не нужно — там тред задаёт платформа, а приложить свой заголовок к
    # сообщению Telegram/Avito нельзя.
    #
    # НА МАРШРУТИЗАЦИЮ НЕ ВЛИЯЕТ: ответ клиента несёт In-Reply-To с нашим
    # Message-ID в любом случае — его ставит почтовик клиента, а не мы. Этот
    # флаг нужен только чтобы НАШИ письма не рассыпались у клиента в ящике.
    supports_thread: bool = False

    # Нужен ли коннектору outbox-аккаунт (chat_external_account) для отправки.
    # Для большинства провайдеров (Telegram, Avito, WhatsApp) — да: исходящие
    # идут «от» конкретного внешнего аккаунта, и send_outgoing_message без него
    # молча ничего не шлёт. Email адресуется своими полями (email_from/
    # email_username), внешний аккаунт ему не нужен — стратегия ставит False.
    requires_outbox_account: bool = True

    # ========================================================================
    # Абстрактные методы - должны быть реализованы в каждой стратегии
    # ========================================================================

    @abstractmethod
    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """
        Получить существующий access token или сгенерировать новый.

        Должен проверить срок действия текущего токена и при необходимости
        использовать refresh_token для получения нового.

        Args:
            connector: Экземпляр коннектора

        Returns:
            Access token или None если не удалось получить
        """

    @abstractmethod
    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Установить webhook URL для получения сообщений от провайдера.

        Args:
            connector: Экземпляр коннектора

        Returns:
            True если успешно, иначе выбрасывает исключение
        """

    @abstractmethod
    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """
        Удалить webhook.

        Args:
            connector: Экземпляр коннектора

        Returns:
            Ответ от API провайдера
        """

    @abstractmethod
    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
        thread_message_id: str | None = None,
        attachments: list | None = None,
    ):
        """
        Отправить текстовое сообщение.

        Последние два параметра база передаёт ВСЕГДА, но заполняет только тем
        стратегиям, которые это объявили (см. supports_thread и
        attachments_inline). Остальные получают None и просто их игнорируют —
        так интерфейс честно говорит, ЧТО конвейер умеет дать, а стратегия
        берёт что нужно.

        Args:
            connector: Экземпляр коннектора
            user_from: Контакт отправителя
            body: Текст сообщения
            chat_id: ID внешнего чата (если известен)
            recipients_ids: Список получателей (если нет chat_id)
            thread_message_id: внешний id предыдущего сообщения чата — чтобы пометить
                исходящее ответом на него (у email → заголовок In-Reply-To).
                Не None только при supports_thread.
            attachments: файлы В ЭТО ЖЕ сообщение. Не None только при
                attachments_inline; иначе они уже ушли отдельными вызовами
                chat_send_message_binary.

        Returns:
            Tuple[external_message_id, external_chat_id]
        """

    # async def chat_send_file(
    #     self,
    #     connector: "ChatConnector",
    #     user_from: "ChatExternalAccount",
    #     chat_id: str,
    #     file_content: bytes,
    #     filename: str,
    #     mimetype: str,
    #     caption: str | None = None,
    # ) -> str | None:
    #     """
    #     Отправить файл/изображение.

    #     Args:
    #         connector: Экземпляр коннектора
    #         user_from: Аккаунт отправителя
    #         chat_id: ID внешнего чата
    #         file_content: Содержимое файла в байтах
    #         filename: Имя файла
    #         mimetype: MIME-тип файла
    #         caption: Подпись к файлу (опционально)

    #     Returns:
    #         external_message_id или None
    #     """
    #     # По умолчанию не поддерживается - стратегии переопределяют
    #     logger.warning(
    #         f"[{self.strategy_type}] chat_send_file not implemented"
    #     )
    #     return None

    # ========================================================================
    # Абстрактные методы (продолжение)
    # ========================================================================

    @abstractmethod
    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> "ChatMessageAdapter":
        """
        Создать адаптер для парсинга сырого сообщения от провайдера.

        Каждая стратегия реализует свой адаптер для преобразования
        специфичного формата сообщения в унифицированный.

        Args:
            connector: Экземпляр коннектора
            raw_message: Сырые данные сообщения

        Returns:
            Адаптер сообщения
        """

    # ========================================================================
    # Webhook обработка - шаблонный метод с общей логикой
    # ========================================================================

    async def handle_webhook(
        self,
        connector: "ChatConnector",
        payload: dict,
        env: "Environment",
    ) -> dict:
        """
        Шаблонный метод обработки входящего webhook запроса.

        Содержит общую логику:
        1. Создание адаптера сообщения
        2. Проверка на пропуск
        3. Проверка дубликатов
        4. Обработка сообщения
        5. Отправка в WebSocket

        Конкретные стратегии могут переопределить для особой логики,
        но обычно достаточно реализовать create_message_adapter.

        Args:
            connector: Экземпляр коннектора
            payload: Данные от провайдера
            env: Environment с доступом к моделям

        Returns:
            Ответ для провайдера
        """
        try:
            # 1. Создаём адаптер сообщения
            adapter = self.create_message_adapter(connector, payload)

            # 2. Проверяем нужно ли пропустить
            if adapter.should_skip:
                logger.info(
                    "[%s] Skipping message %s",
                    self.strategy_type,
                    adapter.message_id,
                )
                return {"ok": True}

            # 3. Проверяем дубликат
            if await self._is_duplicate_message(env, connector, adapter):
                logger.info(
                    "[%s] Duplicate message %s",
                    self.strategy_type,
                    adapter.message_id,
                )
                return {"ok": True}

            # 4. Обрабатываем сообщение в транзакции
            async with env.apps.db.get_transaction():
                await self._process_incoming_message(env, connector, adapter)

            return {"ok": True}

        except NotImplementedError as e:
            logger.warning("[%s] Not implemented: %s", self.strategy_type, e)
            return {"ok": True}
        except Exception as e:
            logger.error(
                "[%s] Error processing webhook: %s",
                self.strategy_type,
                e,
                exc_info=True,
            )
            # Возвращаем OK чтобы провайдер не повторял запрос
            return {"ok": True}

    async def _is_duplicate_message(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ) -> bool:
        """Проверить является ли сообщение дубликатом."""
        return await env.models.chat_external_message.exists(
            external_id=adapter.message_id,
            connector_id=connector.id,
        )

    async def _process_incoming_message(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ) -> None:
        """
        Обработать входящее сообщение от внешнего сервиса.

        1. Найти или создать внешний аккаунт отправителя
        2. Найти или создать внутренний чат
        3. Создать сообщение
        4. Создать связь с внешним сообщением
        5. Обработать вложения
        6. Создать/обновить лид по правилам (lead generation)
        7. Отправить через WebSocket
        """

        # Клиент-контрагент чата: его id и имя одним хуком. Обычно это автор
        # сообщения, но в некоторых интеграциях (Avito) webhook приходит и на
        # наши исходящие — тогда клиента вычисляем из участников чата, а не из
        # author_id (это будет наш аккаунт).
        counterparty_external_id, partner_display_name = (
            await self.resolve_partner(connector, adapter)
        )
        if not counterparty_external_id:
            logger.info(
                "[%s] Message %s → %s",
                self.strategy_type,
                adapter.message_id,
                IncomingRoute.SKIP_COUNTERPARTY_NOT_RESOLVED.value,
            )
            return

        # 1. Контакт (+ партнёр, если адрес незнакомый). Первый элемент —
        # ExternalAccount, он здесь не нужен.
        _, contact, created = (
            await env.models.chat_external_account.find_or_create_for_webhook(
                connector=connector,
                external_id=counterparty_external_id,
                contact_value=counterparty_external_id,
                display_name=partner_display_name,
                raw=json.dumps(adapter.raw) if adapter.raw else None,
            )
        )

        # Имя контрагента. Связываем ЗДЕСЬ и БЕЗУСЛОВНО: его читает блок
        # WS-уведомления в самом конце (author_data), и на любом пути, где имя
        # не связано, там был бы NameError. Контакт полиморфен — имя берём у
        # того владельца, который есть.
        counterparty_name = None
        if contact.partner_id:
            counterparty_name = contact.partner_id.name
        elif contact.user_id:
            counterparty_name = contact.user_id.name

        # Связь ищем ВСЕГДА, даже если чат определится перепиской: external_chat
        # нужен лидогенерации ниже. По external_id ЛИБО address (write-first мог
        # создать связь по номеру).
        external_chat = (
            await env.models.chat_external_chat.find_by_id_or_address(
                key=adapter.chat_id,
                connector_id=connector.id,
            )
        )

        # 2. Куда класть сообщение: ПЕРЕПИСКА → СВЯЗЬ → ХОЛОДНЫЙ СТАРТ.
        # Плоская цепочка: как только route назначен, следующие ветки молчат.
        # Порядок важен — только переписка различает два наших чата с одним
        # адресатом (личный и групповой). Не менять местами.
        route = None
        chat_id = None

        # Переписка: сообщение само сказало «я ответ вон на те». Только email —
        # у прочих адаптеров thread_message_ids пуст по дефолту.
        if adapter.thread_message_ids:
            chat_id = (
                await env.models.chat_external_message.thread_incoming_chat(
                    external_ids=adapter.thread_message_ids,
                    connector_id=connector.id,
                )
            )
            if chat_id:
                route = IncomingRoute.ROUTED_BY_THREAD

        # Связь: тред уже привязан к чату.
        if route is None and external_chat and external_chat.chat_id:
            chat_id = (
                external_chat.chat_id.id
                if hasattr(external_chat.chat_id, "id")
                else external_chat.chat_id
            )
            route = IncomingRoute.ROUTED_BY_LINK

        # Холодный старт с клиентом: его единственный внешний чат (модель 1:1),
        # и сразу привязываем к нему тред.
        if route is None and contact.partner_id:
            chat = await env.models.chat.get_or_create_partner_chat(
                contact.partner_id.id,
                connector=connector,
                partner_name=counterparty_name,
            )
            chat_id = chat.id
            route = (
                IncomingRoute.NEW_CHAT_NEW_PARTNER
                if created
                else IncomingRoute.NEW_CHAT_KNOWN_PARTNER
            )
            item_title, item_url = await self._fetch_item_info(
                connector, adapter
            )
            await env.models.chat_external_chat.create_link(
                external_id=adapter.chat_id,
                connector_id=connector.id,
                chat_id=chat_id,
                item_title=item_title,
                item_url=item_url,
            )
            external_chat = (
                await env.models.chat_external_chat.find_by_external_id(
                    external_id=adapter.chat_id,
                    connector_id=connector.id,
                )
            )

        # Ни то ни другое — класть некуда, см. комменты у членов IncomingRoute.
        if route is None:
            route = (
                IncomingRoute.SKIP_OWN_USER
                if contact.user_id
                else IncomingRoute.SKIP_NO_PARTNER_NO_USER
            )

        # Одна строка на исход — по ней видно судьбу ЛЮБОГО сообщения.
        logger.info(
            "[%s] Message %s → %s (chat=%s, contact=%s)",
            self.strategy_type,
            adapter.message_id,
            route.value,
            chat_id,
            contact.id,
        )

        if route in _SKIP_ROUTES:
            return

        # Лидогенерация — ДО создания сообщения, чтобы сразу проставить
        # message.lead_id (тег «ленты» лида). Лид резолвится по клиенту-
        # контрагенту чата; при исходящем автор — оператор, но лид всё равно
        # на клиента (contact.partner_id). Раньше этот блок стоял ПОСЛЕ
        # post_message (сообщение, породившее лид, тегировалось NULL) — теперь
        # синхронно. Сбой лидогенерации не валит обработку: lead_id=None,
        # сообщение остаётся видно в партнёр-скоупе ленты.
        lead_id = None
        if connector.lead_generation:
            try:
                if contact.partner_id:
                    lead = await self._get_or_create_lead(
                        env=env,
                        connector=connector,
                        adapter=adapter,
                        contact=contact,
                        external_chat=external_chat,
                    )
                    if lead is not None:
                        lead_id = lead.id
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[%s] Lead generation failed for message %s: %s",
                    self.strategy_type,
                    adapter.message_id,
                    exc,
                    exc_info=True,
                )

        # 3. Определяем автора сообщения.
        # contact — это контакт КЛИЕНТА-контрагента.
        author_user_id = None
        author_partner_id = None

        if adapter.is_from_external:
            if contact.user_id:
                # Оператор (контакт привязан к user)
                author_user_id = contact.user_id.id
            elif contact.partner_id:
                # Клиент
                author_partner_id = contact.partner_id.id
        else:
            # Наше сообщение (например, оператор написал клиенту прямо из
            # приложения Avito). Конкретного оператора webhook не передаёт,
            # поэтому автор — системный пользователь («магазин»).
            author_user_id = SYSTEM_USER_ID

        # 4. Создаём сообщение. Вид — обычный comment; канал несёт
        # connector_type (проставляется в post_message из connector.type).
        # Рендер письма (HTML) на фронте — по connector_type, без костыля
        # message_type='email'.
        # Тело для хранения: адаптер сам сериализует своё сообщение. Email
        # упаковывает {"subject","html"} (свой формат, как system хранит JSON);
        # прочие адаптеры отдают текст (дефолт ChatMessageAdapter.serialized_body).
        message = await env.models.chat_message.post_message(
            chat_id=chat_id,
            author_user_id=author_user_id,
            author_partner_id=author_partner_id,
            body=adapter.serialized_body,
            connector_id=connector.id,
            lead_id=lead_id,
        )

        # 5. Создаём связь с внешним сообщением
        await env.models.chat_external_message.create_link(
            external_id=adapter.message_id,
            connector_id=connector.id,
            message_id=message.id,
            external_chat_id=adapter.chat_id,
        )

        # 6. Обрабатываем изображения. Возвращённый список уже в формате
        # REST-эндпоинта — кладём его в WS-пейлоад ниже, чтобы вложения
        # входящего сообщения показывались вживую, без обновления страницы.
        attachments_payload = await self._process_attachments(
            connector, adapter, message
        )

        # 7. Лидогенерация выполнена ВЫШЕ (до post_message), чтобы message.lead_id
        # проставился синхронно. Здесь ничего не делаем.

        # 8. Отправляем уведомление через WebSocket.
        # partner_id/lead_id едут в пейлоаде — по ним фронт роутит событие в
        # «ленты» партнёра/лида (помимо кэша чата). partner_id тут известен
        # даром (contact.partner_id), поэтому кладём оба тега.
        author_data = {
            "id": author_user_id or author_partner_id,
            "name": counterparty_name or adapter.author_name,
            "type": "user" if author_user_id else "partner",
        }

        await env.apps.chat.chat_manager.send_to_chat(
            chat_id=chat_id,
            message={
                "type": "new_message",
                "chat_id": chat_id,
                "message": {
                    "id": message.id,
                    "body": message.body,
                    "author": author_data,
                    "author_user_id": author_user_id,
                    "author_partner_id": author_partner_id,
                    "partner_id": (
                        contact.partner_id.id if contact.partner_id else None
                    ),
                    "lead_id": lead_id,
                    "create_datetime": (
                        message.create_datetime.isoformat()
                        if message.create_datetime
                        else None
                    ),
                    "connector_type": connector.type,
                    # Вложения в формате REST /messages — чтобы бинарный
                    # контент показывался сразу по WS, а не только после F5.
                    "attachments": attachments_payload,
                },
                "external": True,
            },
        )

        logger.info(
            "[%s] Processed message %s -> internal %s",
            self.strategy_type,
            adapter.message_id,
            message.id,
        )

    async def _process_attachments(
        self,
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
        message,
    ) -> list[dict]:
        """Обработать вложения (изображения, файлы).

        Возвращает вложения в ТОМ ЖЕ формате, что и REST-эндпоинт
        /messages (messages.py: словарь id/name/mimetype/size/checksum/
        is_voice/show_preview), чтобы WS-пейлоад входящего сообщения и
        дозагрузка страницы рендерились фронтом одинаково. Нет вложений — [].
        """
        logger.info(
            "Process attachments: %s, %s, %s",
            adapter,
            adapter.images,
            adapter.files,
        )
        attachments_content = []
        if adapter.images:
            for image_url in adapter.images:
                try:
                    image_content, mimetype = await self.file_download(
                        connector, image_url
                    )
                    attachments_content.append((image_content, mimetype))
                    # TODO: Интеграция с модулем attachments
                    logger.debug(
                        "[%s] Downloaded image: %s bytes",
                        self.strategy_type,
                        len(image_content),
                    )
                except Exception as e:
                    logger.error(
                        "[%s] Error downloading image: %s",
                        self.strategy_type,
                        e,
                    )

        if adapter.files:
            for file_info in adapter.files:
                try:
                    file_content, mimetype = await self.file_download(
                        connector, file_info.get("url", "")
                    )
                    attachments_content.append((file_content, mimetype))
                    # TODO: Интеграция с модулем attachments
                    logger.debug(
                        "[%s] Downloaded file: %s (%s bytes)",
                        self.strategy_type,
                        file_info.get("name"),
                        len(file_content),
                    )
                except Exception as e:
                    logger.error(
                        "[%s] Error downloading file: %s",
                        self.strategy_type,
                        e,
                    )
        attachments: list["Attachment"] = []
        logger.info(
            "Process attachments_content end: %s",
            attachments_content,
        )
        for content, mimetype in attachments_content:
            # Получаем правильное расширение для файла (например, '.jpg' для 'image/jpeg')
            ext = mimetypes.guess_extension(mimetype) or ""
            attachment: "Attachment" = env.models.attachment(
                name=f"{self.strategy_type}_{message.id}{ext}",
                mimetype=mimetype,
                size=len(content),
                content=content,
                res_model="chat_message",
                res_id=message.id,
            )
            attachments.append(attachment)

        logger.info(
            "Process attachments end: %s",
            [attach.name for attach in attachments],
        )
        if not attachments:
            # Нет вложений — отдаём [], а не None: вызывающий код кладёт
            # его в WS-пейлоад как "attachments": [] (пустой, но валидный).
            return []

        await env.models.attachment.create_bulk(attachments)

        # Перечитываем из БД теми же полями, что и REST /messages. На
        # in-memory объектах незаданные поля (is_voice/show_preview)
        # читаются как None вместо дефолта БД — точного совпадения с REST
        # не дают. Чтение идёт в той же внешней транзакции (create_bulk —
        # вложенный SAVEPOINT на том же соединении), поэтому видит свои же
        # ещё не закоммиченные строки.
        rows = await env.models.attachment.search(
            filter=[
                ("res_model", "=", "chat_message"),
                ("res_id", "=", message.id),
            ],
            fields=[
                "id",
                "name",
                "mimetype",
                "size",
                "checksum",
                "is_voice",
                "show_preview",
            ],
        )
        # Формат словаря — зеркало REST-сериализации вложения в messages.py.
        return [
            {
                "id": att.id,
                "name": att.name,
                "mimetype": att.mimetype,
                "size": att.size,
                "checksum": att.checksum,
                "is_voice": att.is_voice or False,
                "show_preview": att.show_preview,
            }
            for att in rows
        ]

    # Лидогенерация
    async def _fetch_item_info(
        self,
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ) -> tuple[str, str]:
        """Получить (item_title, item_url) у стратегии.

        Не все коннекторы поддерживают объявления/контекст; такие
        вернут пустые строки. Avito-стратегия переопределяет
        `get_item_info` и возвращает реальные данные.
        """
        item_title = ""
        item_url = ""
        try:
            user_id = getattr(adapter, "user_id", None)
            item_id = getattr(adapter, "item_id", None)
            chat_id = getattr(adapter, "chat_id", None)
            # user_id может быть методом — это известно для Avito-адаптера
            # if callable(user_id):
            #     user_id = user_id()
            get_item_info = getattr(self, "get_item_info", None)
            if get_item_info is not None and chat_id:
                info = (
                    await get_item_info(
                        connector, user_id, item_id, chat_id=chat_id
                    )
                    or {}
                )
                item_title = info.get("title") or ""
                item_url = info.get("url") or ""
            else:
                # Fallback на отдельный get_item_url, если стратегия даёт только его.
                if item_id:
                    item_url = (
                        await self.get_item_url(connector, user_id, item_id)
                        or ""
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] Cannot fetch item info: %s",
                self.strategy_type,
                exc,
            )
        return item_title, item_url

    def _build_routing_payload(
        self,
        adapter: "ChatMessageAdapter",
        contact: "Contact",
        item_title: str,
        item_url: str,
        partner_name: str = "",
    ) -> dict:
        """Сформировать словарь для проверки правил маршрутизации.

        Структура (item_title, message_text, item_url,
        partner_name) — это позволяет администратору применять одни и
        те же правила между системами.
        """
        if not partner_name and contact and contact.partner_id:
            # Может быть stub — name не загружен; не страшно, fallback ниже.
            partner_name = getattr(contact.partner_id, "name", None) or ""
        if not partner_name:
            partner_name = getattr(adapter, "author_name", None) or ""
        return {
            "item_title": item_title or "",
            "message_text": adapter.text or "",
            "item_url": item_url or "",
            "partner_name": partner_name,
        }

    async def _get_or_create_lead(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
        contact: "Contact",
        external_chat,
    ):
        """Создать или найти существующий лид для входящего сообщения.

        Логика:
        - имя лида = item_title (заголовок объявления) или partner.name;
        - ищем существующий лид по (partner_id, connector_id);
        - если у найденного лида другой website (item_url) — создаём новый
          (клиент пишет по другому объявлению — это другой лид);
        - применяем правила chat_routing_rule_lead если включено
          `connector.lead_distribution`.
        """
        partner = contact.partner_id if contact else None
        if not partner:
            # Без партнёра-клиента создавать лид бессмысленно.
            return None

        # partner здесь может быть "stub" (только id, без полей) — дочерние
        # поля типа .name не подгружаются автоматически. Поэтому если name
        # пустое — догружаем явно из БД (один лёгкий запрос).
        partner_name = partner.name
        # partner_name = getattr(partner, "name", None)
        # if not partner_name:
        #     loaded_partners = await env.models.partner.search(
        #         filter=[("id", "=", partner.id)],
        #         fields=["id", "name"],
        #         limit=1,
        #     )
        #     if loaded_partners:
        #         partner_name = loaded_partners[0].name or ""
        #     else:
        #         partner_name = ""

        # item_title / item_url — из кеша chat_external_chat
        item_title = ""
        item_url = ""
        if external_chat:
            item_title = (external_chat.item_title or "").strip()
            item_url = (external_chat.item_url or "").strip()

        # Ищем существующий лид по (partner_id, connector_id) — берём свежий
        existing_leads = await env.models.lead.search(
            filter=[
                ("partner_id", "=", partner.id),
                ("connector_id", "=", connector.id),
            ],
            fields=["id", "website", "name"],
            sort="id",
            order="DESC",
            limit=1,
        )
        existing_lead = existing_leads[0] if existing_leads else None

        # Если у найденного лида другой website — этот клиент пишет по
        # другому объявлению, создаём новый лид.
        if (
            existing_lead
            and item_url
            and existing_lead.website
            and existing_lead.website != item_url
        ):
            existing_lead = None

        if existing_lead:
            # Обновим website если он появился позже
            if item_url and existing_lead.website != item_url:
                await existing_lead.update(env.models.lead(website=item_url))
            return existing_lead

        # Имя лида: заголовок объявления или имя партнёра.
        fallback_name = (
            partner_name
            or getattr(adapter, "author_name", None)
            or f"Lead {connector.name or connector.type}"
        )
        lead_name = item_title or fallback_name

        # Правила маршрутизации
        assigned_user = None
        assigned_team = None
        if connector.lead_distribution:
            try:
                rule_user, rule = (
                    await env.models.chat_routing_rule_lead.find_user_for(
                        connector.id,
                        self._build_routing_payload(
                            adapter,
                            contact,
                            item_title,
                            item_url,
                            partner_name=partner_name,
                        ),
                    )
                )
                if rule_user:
                    assigned_user = rule_user
                    if rule and rule.team_id:
                        assigned_team = rule.team_id
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[%s] Routing rule evaluation failed: %s",
                    self.strategy_type,
                    exc,
                )

        # Собираем payload для нового лида
        lead_payload = {
            "name": lead_name,
            "type": connector.lead_type or "opportunity",
            "partner_id": partner,
            "connector_id": env.models.chat_connector(id=connector.id),
            "website": item_url or None,
            "notes": (
                f"Создан из сообщения {adapter.message_id} ({connector.name})"
            ),
        }
        if assigned_user:
            lead_payload["user_id"] = assigned_user
        if assigned_team:
            lead_payload["team_id"] = assigned_team
        if connector.lead_stage_id:
            lead_payload["stage_id"] = connector.lead_stage_id

        new_lead = env.models.lead(**lead_payload)
        new_lead.id = await env.models.lead.create(payload=new_lead)
        logger.info(
            "[%s] Created lead %s (name=%r) for partner %s via connector %s",
            self.strategy_type,
            new_lead.id,
            lead_name,
            partner.id,
            connector.id,
        )
        return new_lead

    # ========================================================================
    # Дополнительные методы
    # ========================================================================

    async def get_webhook_info(self, connector: "ChatConnector") -> dict:
        """
        Получить информацию о текущем webhook.

        Args:
            connector: Экземпляр коннектора

        Returns:
            Словарь с информацией о webhook
        """
        return {}

    async def delete_webhook_by_url(
        self, connector: "ChatConnector", webhook_url: str
    ) -> Any:
        """
        Удалить webhook/подписку по произвольному URL.

        Актуально для провайдеров, где подписок может быть несколько
        (MAX: список /subscriptions) и надо почистить старые. Базовая
        реализация не поддерживает — переопределяют конкретные стратегии.
        """
        raise NotImplementedError(
            f"delete_webhook_by_url not supported for {self.strategy_type}"
        )

    async def get_self_account_id(self, connector: "ChatConnector") -> dict:
        """
        Получить информацию об аккаунте от внешнего сервиса.

        Конкретные стратегии (Avito) переопределяют — возвращают данные
        текущего аккаунта (id, name, email, phone, profile_url и т.п.),
        чтобы пользователь мог скопировать `external_account_id` при
        настройке коннектора.

        Returns:
            Словарь с данными аккаунта от провайдера.
        """
        raise NotImplementedError(
            f"get_self_account_id not supported for {self.strategy_type}"
        )

    async def test_connection(self, connector: "ChatConnector") -> dict:
        """
        Проверить соединение с внешним сервисом по текущим настройкам.

        Конкретные стратегии (например Email — SMTP/IMAP логин)
        переопределяют. Возвращает словарь вида:
            {"ok": bool, "message": str, "details": {...}}

        База не умеет проверять соединение универсально, поэтому по
        умолчанию сообщает, что проверка для типа не поддерживается.
        """
        return {
            "ok": False,
            "message": (
                f"Проверка соединения не поддерживается для "
                f"типа '{self.strategy_type}'"
            ),
            "details": {},
        }

    async def chat_send_message_binary(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        chat_id: str,
        attachment: Any,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить файл или изображение.

        Args:
            connector: Экземпляр коннектора
            user_from: Контакт отправителя
            chat_id: ID внешнего чата
            attachment: Вложение для отправки
            recipients_ids: Список получателей

        Returns:
            Tuple[external_message_id, external_chat_id]
        """
        raise NotImplementedError(
            f"Binary messages not supported for {self.strategy_type}"
        )

    async def file_download(
        self, connector: "ChatConnector", file_url: str
    ) -> tuple[bytes, str]:
        """
        Скачать файл по URL.

        Args:
            connector: Экземпляр коннектора
            file_url: URL файла

        Returns:
            Содержимое файла в байтах
        """
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(file_url)
            # Получаем MIME-тип и очищаем его от возможных параметров вроде charset=utf-8
            content_type = response.headers.get("content-type", "")
            mime_type = (
                content_type.split(";")[0].strip()
                if content_type
                else "unknown"
            )

            # Теперь у вас есть доступ и к mime_type, и к response.content
            return response.content, mime_type

    # async def get_partner_name(
    #     self, connector: "ChatConnector", user_id: str
    # ) -> str | None:
    #     """
    #     Получить имя пользователя по его ID во внешней системе.

    #     Args:
    #         connector: Экземпляр коннектора
    #         user_id: ID пользователя

    #     Returns:
    #         Имя пользователя или None
    #     """
    #     return None

    async def get_item_url(
        self, connector: "ChatConnector", user_id: str, item_id: str
    ) -> str | None:
        """
        Получить URL элемента (например, объявления в Avito).

        Args:
            connector: Экземпляр коннектора
            user_id: ID пользователя
            item_id: ID элемента

        Returns:
            URL элемента или None
        """
        return None

    async def send_outgoing_message(
        self,
        env: "Environment",
        chat_id: int,
        connector_id: "ChatConnector",
        user_id: int,
        body: str,
        message_id: int,
        attachments: list["Attachment"] | None = None,
        recipients_ids: list[dict] | None = None,
    ) -> bool:
        """
        Отправить сообщение во внешний коннектор (Telegram, WhatsApp и т.д.)

        Args:
            env: Environment
            chat_id: ID внутреннего чата
            connector_id: коннектор
            user_id: ID пользователя-отправителя
            body: Текст сообщения
            message_id: ID внутреннего сообщения
            attachments: Список вложений [{id, name, mimetype, size, content}]
            recipients_ids: Список контактов получателей [{"id": ..., "contact_value": ...}]

        Returns:
            True если успешно отправлено
        """
        try:
            # Находим external_chat для этого чата и коннектора
            external_chat = await env.models.chat_external_chat.search(
                filter=[
                    ("chat_id", "=", chat_id),
                    ("connector_id", "=", connector_id.id),
                ],
                fields=["id", "external_id"],
                limit=1,
            )

            external_chat_id = None
            # Флаг write-first: связи ещё нет, адресуем по контакту получателя.
            # Ниже, ПОСЛЕ отправки, персистим external_chat (иначе входящий
            # ответ не найдёт связь и создаст второй внутренний чат).
            is_write_first = False
            write_first_address = None

            if external_chat:
                # Есть существующий external_chat - используем его
                external_chat_id = external_chat[0].external_id
            elif recipients_ids:
                # Первое сообщение - используем контакты получателей
                # Пока поддерживаем отправку только одному получателю
                if len(recipients_ids) > 1:
                    logger.warning(
                        "Multiple recipients not fully supported yet, using first one"
                    )

                recipient = recipients_ids[0]
                external_chat_id = recipient["contact_value"]
                is_write_first = True
                write_first_address = external_chat_id
            else:
                logger.warning(
                    "No external_chat found for chat=%s, connector=%s and no recipients provided",
                    chat_id,
                    connector_id.id,
                )
                return False

            # Находим контакт оператора по contact_type_id коннектора
            # operator_ct_id = connector_id.contact_type_id
            # if operator_ct_id is None:
            #     raise ValueError("Contact type must be set")

            # operator_contact = await env.models.contact.search(
            #     filter=[
            #         ("contact_type_id", "=", operator_ct_id),
            #         ("user_id", "=", user_id),
            #         ("active", "=", True),
            #     ],
            #     fields_nested={"external_account_ids": ["id"]},
            #     limit=1,
            # )

            # if not operator_contact:
            #     logger.warning(
            #         "No operator contact found for connector %s, user %s",
            #         connector_id.id,
            #         user_id,
            #     )
            #     return False

            # Отправляем, если есть outbox-аккаунт ИЛИ стратегия его не требует
            # (email адресуется своими полями). Раньше здесь стоял голый
            # `if connector_id.outbox_account_id:` — у email он всегда None
            # (external_account_id не заполняется), поэтому весь блок отправки
            # пропускался, функция возвращала None, а сообщение оставалось
            # внутренним. Именно поэтому письмо «не уходило».
            outbox = connector_id.outbox_account_id
            if outbox or not self.requires_outbox_account:
                external_msg_id = None

                # Вложения внутри сообщения (email) или отдельными (мессенджеры)
                inline = bool(attachments) and self.attachments_inline

                # Пометка «это ответ на такое-то» для исходящего — только тем,
                # кто умеет её нести. Берём ПОСЛЕДНЕЕ сообщение чата: этого
                # хватает, чтобы почтовик получателя собрал переписку в ветку.
                # На маршрутизацию не влияет, см. supports_thread.
                thread_message_id = None
                if self.supports_thread:
                    thread_message_id = await env.models.chat_external_message.thread_outgoing_id(
                        chat_id=chat_id,
                        connector_id=connector_id.id,
                    )

                # Отправляем вложения ОТДЕЛЬНЫМИ сообщениями — только если
                # стратегия не умеет иначе. У email умеет: там они уедут внутри
                # письма ниже, одним отправлением.
                if attachments and not inline:
                    for att in attachments:
                        try:
                            # Получаем содержимое вложения из БД
                            # attachment = await env.models.attachment.get(att["id"])
                            # if not attachment:
                            #     continue
                            file_msg_id = await self.chat_send_message_binary(
                                connector_id,
                                outbox,
                                external_chat_id,
                                att,
                            )

                            if file_msg_id and not external_msg_id:
                                external_msg_id = file_msg_id

                        except Exception as e:
                            # att — объект Attachment (см. messages.py, там
                            # собираются payload'ы модели), а не dict. Раньше
                            # здесь стояло att.get("id") — обработчик ошибок сам
                            # падал на первом же сбое отправки вложения.
                            logger.error(
                                "Failed to send attachment %s: %s",
                                getattr(att, "id", None),
                                e,
                            )

                # Если нет вложений или есть текст без caption — отправляем текст.
                # При inline зовём ДАЖЕ С ПУСТЫМ текстом: иначе письмо с одними
                # файлами и без подписи не ушло бы вовсе — цикл выше пропущен, а
                # отправляет именно этот вызов.
                # Второй элемент — канонический ключ переписки, который вернула
                # стратегия (для write-first это нормализованный адрес/номер;
                # когда стратегия начнёт возвращать реальный chat_id из ответа —
                # это будет он).
                conversation_key = None
                if body.strip() or inline:
                    text_msg_id, conversation_key = (
                        await self.chat_send_message(
                            connector=connector_id,
                            user_from=outbox,
                            body=body,
                            chat_id=external_chat_id,
                            thread_message_id=thread_message_id,
                            attachments=attachments if inline else None,
                        )
                    )
                    if text_msg_id:
                        external_msg_id = text_msg_id

                # Сохраняем связь с внешним сообщением
                if external_msg_id:
                    await env.models.chat_external_message.create_link(
                        external_id=str(external_msg_id),
                        connector_id=connector_id.id,
                        message_id=message_id,
                        external_chat_id=external_chat_id,
                    )

                # Персистим связь чата при отправке-первым: без неё входящий
                # ответ не найдёт external_chat и создаст ВТОРОЙ внутренний чат.
                # external_id — ключ треда (пока = нормализованный адрес; когда
                # стратегия отдаст реальный chat_id — перезапишется на него).
                # external_address — сам адрес (номер), по нему входящий ответ
                # найдётся даже после перезаписи external_id (см.
                # ChatExternalChat.find_by_id_or_address). Идемпотентно: если
                # связь уже успел создать входящий — не дублируем.
                if is_write_first:
                    thread_key = str(conversation_key or write_first_address)
                    address_key = str(conversation_key or write_first_address)
                    # Идемпотентность — ПО АДРЕСУ, а не по chat_id.
                    already = await env.models.chat_external_chat.find_by_id_or_address(
                        key=address_key,
                        connector_id=connector_id.id,
                    )
                    if not already:
                        await env.models.chat_external_chat.create_link(
                            external_id=thread_key,
                            connector_id=connector_id.id,
                            chat_id=chat_id,
                            external_address=address_key,
                        )
                        logger.info(
                            "write-first external_chat linked: chat=%s "
                            "connector=%s address=%s",
                            chat_id,
                            connector_id.id,
                            address_key,
                        )
                    else:
                        # Связь на этот адрес уже есть и ведёт в другой чат —
                        # НЕ дублируем: диалог принадлежит тому чату, и входящий
                        # ответ уйдёт туда. Иначе получили бы два чата на адрес.
                        linked_chat = already.chat_id
                        if linked_chat != chat_id:
                            logger.warning(
                                "write-first: адрес %s уже привязан к чату %s "
                                "(коннектор %s), отправка идёт из чата %s — "
                                "ответ придёт в %s, связь не дублируем.",
                                address_key,
                                linked_chat,
                                connector_id.id,
                                chat_id,
                                linked_chat,
                            )

                logger.info(
                    "Sent message to %s: internal=%s, external=%s",
                    connector_id.type,
                    message_id,
                    external_msg_id,
                )
                return True

        except Exception as e:
            logger.error(
                "Failed to send to external connector: %s", e, exc_info=True
            )
            return False

    async def resolve_partner(
        self,
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ) -> tuple[str | None, str | None]:
        """Хук: вернуть (external_id, name) клиента-контрагента.

        По умолчанию контрагент = автор сообщения. Это верно для коннекторов,
        куда webhook приходит только на входящие сообщения от клиента
        (Telegram, WhatsApp, email и т.п.).

        Avito переопределяет: туда webhook приходит и на наши собственные
        исходящие, поэтому клиента (id и имя) нужно определять по участникам
        чата, а не по author_id.

        external_id=None означает «не удалось определить клиента» — обработка
        сообщения будет пропущена (см. _process_incoming_message), чтобы не
        создавать партнёра/лид на наш собственный аккаунт.
        """
        return adapter.author_id, adapter.author_name
