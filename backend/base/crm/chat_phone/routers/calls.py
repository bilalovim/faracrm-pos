# Copyright 2025 FARA CRM
# Chat Phone module - Calls analytics router (telephony)
#
# Звонок = независимая модель `call` (Архитектура 2). Сам реестр читается
# ОБЫЧНЫМ авто-CRUD (/auto/call/search) — экран «Звонки» это стандартный
# list/form, как у остальных моделей. Здесь остаётся только сводка
# («Всего / Отвечено / Пропущено / Входящие»).
#
# Сводка считается по ТОМУ ЖЕ фильтру, что и таблица, но БЕЗ пагинации:
# в таблице видна только страница, в плашках — все записи под фильтром.
# Поэтому и формат фильтра тот же, что у /auto/call/search (FilterExpression),
# а считаем через Model.search_count — с теми же проверками доступа.

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.status import HTTP_400_BAD_REQUEST

from backend.base.crm.auth_token.app import AuthTokenApp

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.system.dotorm.dotorm.components.filter_parser import (
        FilterExpression,
    )

router_private = APIRouter(
    tags=["Telephony Calls"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


class CallsStatsPayload(BaseModel):
    """Фильтр таблицы звонков (тот же FilterExpression, что у /search).

    Тип объявлен как list: FilterExpression рекурсивный, и pydantic на нём
    уходит в бесконечность при генерации схемы. Содержимое проверяет
    _fields_belong_to_call.
    """

    filter: list | None = None


def _fields_belong_to_call(expr: "FilterExpression", call_model) -> bool:
    """Все триплеты фильтра — по полям звонка (как проверка fields в /search)."""
    allowed = call_model.get_all_fields().keys()
    for item in expr:
        if isinstance(item, str):  # 'and' / 'or'
            continue
        if len(item) == 3 and isinstance(item[0], str):  # триплет
            if item[0] not in allowed:
                return False
        elif not _fields_belong_to_call(item, call_model):  # вложенная группа
            return False
    return True


@router_private.post("/telephony/calls/stats")
async def get_calls_stats(req: Request, payload: CallsStatsPayload):
    """Сводка по звонкам под текущим фильтром (без учёта пагинации).

    Фильтр приходит от фронта ровно тот же, что уходит в /auto/call/search
    (включая active=true самого вью), поэтому цифры плашек и содержимое
    таблицы всегда об одной выборке.
    """
    env: "Environment" = req.app.state.env
    call_model = env.models.call

    base = payload.filter or []
    if not _fields_belong_to_call(base, call_model):
        return JSONResponse(
            content={"error": "#FIELDS_NOT_FOUND"},
            status_code=HTTP_400_BAD_REQUEST,
        )

    # 1. Total (передаем None, если фильтр пустой)
    total = await call_model.search_count(filter=base or None)

    # 2. Answered
    answered_filter = [base] if base else []
    answered_filter.append(["disposition", "=", "answered"])
    answered = await call_model.search_count(filter=answered_filter)

    # 3. Incoming
    incoming_filter = [base] if base else []
    incoming_filter.append(["direction", "=", "incoming"])
    incoming = await call_model.search_count(filter=incoming_filter)

    # Пропущенный = любой неотвеченный (no_answer/busy/failed/cancelled),
    # исходящий = не входящий: считаем вычитанием, чтобы не гонять лишние
    # COUNT-запросы.
    return {
        "total": total,
        "answered": answered,
        "missed": total - answered,
        "incoming": incoming,
        "outgoing": total - incoming,
    }
