# Copyright 2025 FARA CRM
# Chat Phone module - дефолты телефонного коннектора

import secrets

from backend.base.system.core.enviroment import env


async def phone_connector_defaults() -> dict:
    """
    Значения, которые проставляются при выборе ЛЮБОГО телефонного типа
    коннектора: свой webhook-секрет, категория и тип контакта «телефон».

    Про тип контакта. Базовый ChatConnector.onchange_type ищет тип контакта по
    ИМЕНИ типа коннектора ('phone_asterisk', 'phone_sipuni', …) — таких типов
    нет и не будет, и при промахе он ЯВНО ставит contact_type_id=None, то есть
    очищает поле. А по нему звонок находит клиента: без типа контакта
    find_or_create_for_webhook бросает ValueError внутри транзакции записи
    звонка, стратегия его глушит и отдаёт провайдеру 200 — снаружи это выглядит
    как «звонки молча не пишутся». Наши обработчики выполняются ПОСЛЕ базового
    (dir() отдаёт имена по алфавиту, а onchange_type короче onchange_type_phone_*),
    поэтому значение отсюда перекрывает базовый None.
    """
    contact_type = await env.models.contact_type.get_by_name("phone")
    return {
        "webhook_hash": secrets.token_hex(32),
        "category": "phone",
        "contact_type_id": contact_type,
    }
