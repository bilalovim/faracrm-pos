# Copyright 2025 FARA CRM
# Chat Phone module - фоновые задачи телефонии (точки входа cron-задач)

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)


async def _connectors(env: "Environment", strategy_type: str) -> list:
    """Активные коннекторы типа — как их грузит webhook-роутер (contact_type_id
    нужен резолву клиента, иначе импорт не заведёт партнёра)."""
    return await env.models.chat_connector.search(
        filter=[("type", "=", strategy_type), ("active", "=", True)],
        fields_nested={"contact_type_id": ["id", "name", "is_phone_format"]},
    )


async def fetch_call_history(env: "Environment", strategy_type: str) -> dict:
    """
    Бэкофилл истории звонков за последнее окно: тихо (без карточек и лидов) —
    живой звонок ведёт webhook-поток, дубли гасит upsert по uniqueid.
    """
    total = 0
    connectors = await _connectors(env, strategy_type)
    for connector in connectors:
        strategy = connector.strategy
        end = datetime.now() - timedelta(minutes=strategy.HISTORY_WAIT_MINUTES)
        start = end - timedelta(minutes=strategy.HISTORY_WINDOW_MINUTES)
        try:
            result = await strategy.import_history(
                connector, start.astimezone(), end.astimezone(), env
            )
            total += result.get("imported", 0)
        except Exception as e:  # noqa: BLE001
            logger.error("[%s] cron history failed: %s", strategy_type, e)

    logger.info(
        "[%s] cron imported %s calls from %s connectors",
        strategy_type,
        total,
        len(connectors),
    )
    return {"connectors": len(connectors), "calls": total}


async def sync_numbers(env: "Environment", strategy_type: str) -> dict:
    """Периодическая синхронизация номеров (то же, что кнопка в форме)."""
    total = 0
    connectors = await _connectors(env, strategy_type)
    for connector in connectors:
        try:
            result = await connector.strategy.sync_numbers(connector, env)
            total += (result.get("details") or {}).get("synced", 0)
        except Exception as e:  # noqa: BLE001
            logger.error("[%s] cron sync_numbers failed: %s", strategy_type, e)

    logger.info(
        "[%s] cron synced numbers for %s connectors (%s lines)",
        strategy_type,
        len(connectors),
        total,
    )
    return {"connectors": len(connectors), "lines": total}
