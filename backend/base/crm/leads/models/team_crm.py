from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Many2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.system.schemas.base_schema import Id

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User


class TeamCrm(DotModel):
    __table__ = "team_crm"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Team Name")

    # Пользователи-участники команды. Источник {{team_ids}} в правилах:
    # резолвер в access_control читает team_crm_user_many2many по user_id.
    # column1 -> users.id, column2 -> team_crm.id (сверено с m2m-builder).
    # Join-таблица + FK + индекс создаются auto-DDL из этого поля.
    user_ids: list["User"] = Many2many(
        store=False,
        relation_table=lambda: env.models.user,
        many2many_table="team_crm_user_many2many",
        column1="user_id",
        column2="team_id",
        ondelete="cascade",
        default=[],
        description="Пользователи-участники команды",
    )

    async def update(
        self, payload, fields=None, session=None, depends_jobs=None
    ):
        await super().update(payload, fields, session, depends_jobs)

        # Смена состава команды меняет {{team_ids}} у её участников → сессии
        # закэшированы с командами (см. _set_team_ids), поэтому точечно
        # инвалидируем сессии текущих участников (тем же каналом, что роли:
        # команды — authz-атрибут). Удалённый участник ловится по истечении
        # сессии (в текущих участниках его уже нет) — приемлемо для доступа
        # на чтение. Правки состава со стороны user.team_ids — через User.
        changed = fields or payload.assigned_fields()
        if "user_ids" in changed:
            affected = await self._member_user_ids()
            if affected:
                await env.models.session.publish_roles_changed(affected)

    async def _member_user_ids(self) -> list[int]:
        """ID текущих участников команды (для инвалидации их сессий)."""
        db = self._get_db_session()
        rows = await db.execute(
            "SELECT user_id FROM team_crm_user_many2many WHERE team_id = $1",
            [self.id],
            cursor="fetch",
        )
        return [r["user_id"] for r in rows]
