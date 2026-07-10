# Copyright 2025 FARA CRM
# Chat module - MAX "business" strategy.
#
# ВАЖНО (2026-07): у MAX НЕТ официального «бизнес»-канала с отправкой первым по
# номеру телефона. platform-api.max.ru — это тот же MAX Bot API, что и
# botapi.max.ru (коннектор max_bot): получатель адресуется по chat_id, который
# приходит в вебхуке (событие bot_started / сообщение пользователя), отправка —
# POST /messages?chat_id=…, приём и вложения — как в Bot API (см. dev.max.ru).
# Прежняя реализация слала POST /messages?phone=<E.164> и получала
# HTTP 400 «Unknown recipient» — такой адресации в API не существует.
#
# Поэтому max_business ТЕПЕРЬ НАСЛЕДУЕТ поведение max_bot целиком: отправка,
# приём, вложения, вебхуки — одинаковые. Для клиента неважно, что он выбрал —
# «бот» или «бизнес»: оба работают через один Bot API. Отличается только
# strategy_type и (пока) домен по умолчанию. Старый phone-код закомментирован
# внизу файла (полностью — в истории git).

from backend.base.crm.chat_max_bot.strategies.strategy import MaxBotStrategy


class MaxBusinessStrategy(MaxBotStrategy):
    """
    «MAX для бизнеса» — по факту тот же MAX Bot API, что и max_bot.

    Наследует всё поведение MaxBotStrategy (chat_id из вебхука, POST /messages,
    /subscriptions, /uploads, скачивание вложений). Отличается только типом
    коннектора и доменом по умолчанию, чтобы «бот» и «бизнес» вели себя
    одинаково.

    Write-first по номеру телефона MAX-API не поддерживает (получатель —
    только chat_id из вебхука). Если нужна отправка первым по номеру — это
    сторонний агрегатор (коннектор max_wamm), а не официальное API.
    """

    strategy_type = "max_business"
    # Пока оставляем старый домен. Миграция на platform-api2.max.ru
    # (+ сертификат Минцифры) — до 19.07.2026. Переопределяется полем
    # connector_url коннектора.
    BASE_API_URL = "https://platform-api.max.ru"


# =============================================================================
# СТАРЫЙ КОД (write-first по номеру телефона) — ЗАКОММЕНТИРОВАН.
#
# Отключён, т.к. официального бизнес-API MAX с отправкой первым по номеру не
# существует: platform-api.max.ru — Bot API, получатель = chat_id из вебхука,
# а POST /messages?phone=<E.164> возвращал HTTP 400 «Unknown recipient».
# Всё поведение теперь наследуется от MaxBotStrategy (см. выше). Ниже —
# ключевые куски прежней phone-реализации (полностью — в git history):
#
# import asyncio, logging, re
# import httpx
# from backend.base.crm.chat.strategies.strategy import ChatStrategyBase
# from .adapter import MaxBusinessMessageAdapter
# logger = logging.getLogger(__name__)
#
# class MaxBusinessStrategy(ChatStrategyBase):
#     strategy_type = "max_business"
#     BASE_API_URL = "https://platform-api.max.ru"
#     TIMEOUT = 30.0
#     # Слал по токену бизнес-аккаунта + номеру, outbox-аккаунт не использовал.
#     requires_outbox_account = False
#
#     @staticmethod
#     def _headers(connector):
#         return {"Authorization": connector.access_token or ""}
#
#     @staticmethod
#     def _recipient_digits(value):
#         # Цифры номера; на провод уходил E.164 (+digits), ключ — digits.
#         return re.sub(r"\D", "", str(value or ""))
#
#     async def chat_send_message(self, connector, user_from, body,
#                                 chat_id=None, recipients_ids=None):
#         # POST /messages?phone=+<digits> — MAX отвечал 400 Unknown recipient.
#         digits = self._recipient_digits(chat_id)
#         params = {"phone": "+" + digits}
#         async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
#             response = await client.post(
#                 self._api_url(connector, "messages"),
#                 headers=self._headers(connector),
#                 params=params,
#                 json={"text": re.sub(r"<[^>]+>", "", body or "")},
#             )
#             result = self._parse(response, "sendMessage")
#         return self._extract_mid(result), digits
#
#     # chat_send_message_binary — то же, но с POST /uploads и attachments.
#     # set_webhook/unset_webhook/get_webhook_info — POST/DELETE/GET
#     #   /subscriptions (идентичны max_bot, теперь наследуются).
#     # get_self_account_id — GET /me (идентично max_bot).
#     # _upload_attachment — POST /uploads (идентично max_bot).
#
#     def create_message_adapter(self, connector, raw_message):
#         # Прежний адаптер ключевал входящее по номеру (sender_phone).
#         # Теперь наследуется max_bot-адаптер (chat_id).
#         return MaxBusinessMessageAdapter(connector, raw_message)
# =============================================================================
