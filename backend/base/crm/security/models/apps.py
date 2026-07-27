from backend.base.system.dotorm.dotorm.fields import Boolean, Char, Integer
from backend.base.system.dotorm.dotorm.model import DotModel


class App(DotModel):
    """
    Приложение/модуль системы.

    Используется для:
    - Группировки ролей по приложениям в UI
    - Отслеживания установленных модулей
    """

    __table__ = "apps"

    id: int = Integer(primary_key=True)
    code: str = Char(max_length=64, unique=True)
    name: str = Char(max_length=128)
    active: bool = Boolean(default=True)
    sequence: int = Integer(default=10, description="Порядок в очереди")

    # Признак «UI-приложение»: модуль даёт плитку главного меню (лаунчера).
    # Объявляется в info САМОГО МОДУЛЯ ("ui_menu": True, "ui_menu_name": "…");
    # _init_apps переносит их на строку App. Список UI-приложений — запрос
    # App где ui_menu=true (не хардкод-список).
    ui_menu: bool = Boolean(
        default=False, description="Модуль даёт плитку главного меню"
    )
    # Ключ группы меню на фронте (communication, crm, settings, telephony, …).
    # Именно он — контракт с фронтом; App.code остаётся кодом МОДУЛЯ (chat,
    # leads, security, chat_phone). «Рабочее место» ссылается на App через
    # app_ids (m2m), фронту отдаётся набор ui_menu_name.
    ui_menu_name: str | None = Char(
        max_length=64,
        required=False,
        description="Ключ группы меню на фронте (контракт)",
    )
