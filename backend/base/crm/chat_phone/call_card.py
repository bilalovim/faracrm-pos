# Copyright 2025 FARA CRM
# Chat Phone module - живая карточка разговора (WS-попап сотруднику)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment


class CallCard:
    """
    Транспорт живой карточки разговора: показать (show) и убрать (hide).

    НИЧЕГО не резолвит и в БД не ходит — данные готовит IncomingCallPipeline,
    единственный источник истины про ноги звонка и клиента. Зеркало
    IncomingMessagePipeline._notify: собрать конверт и отправить.

    Карточка эфемерная: в БД не пишется, звонок попадёт в реестр отдельно —
    по завершению.
    """

    @classmethod
    async def show(cls, env: "Environment", user_id: int, call: dict) -> None:
        await env.apps.chat.chat_manager.send_to_user(
            user_id, {"type": "call.incoming", "call": call}
        )

    @classmethod
    async def hide(cls, env: "Environment", user_id: int, number: str) -> None:
        await env.apps.chat.chat_manager.send_to_user(
            user_id, {"type": "call.ended", "call": {"number": number}}
        )
