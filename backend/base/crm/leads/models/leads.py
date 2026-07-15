from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.crm.company.models.company import Company
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.partners import Partner
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from .team_crm import TeamCrm
    from .lead_stage import LeadStage

import logging

from ...partners.models.contact import Contact
from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
    Many2one,
    One2many,
    Selection,
    Text,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.crm.users.audit_mixin import AuditMixin
from backend.base.system.core.enviroment import env
from backend.base.crm.security.polymorphic_parent import (
    PolymorphicParentMixin,
)

logger = logging.getLogger(__name__)


class Lead(AuditMixin, PolymorphicParentMixin):
    __table__ = "leads"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Lead Name")
    active: bool = Boolean(default=True)
    stage_id: "LeadStage" = Many2one(
        lambda: env.models.lead_stage,
        string="Stage",
        index=True,
        ondelete="restrict",
    )
    user_id: "User | None" = Many2one(
        lambda: env.models.user,
        string="Salesperson",
        # index=True,
        ondelete="restrict",
    )
    partner_id: "Partner | None" = Many2one(
        lambda: env.models.partner,
        string="Partner",
        index=True,
        ondelete="restrict",
    )
    company_id: "Company | None" = Many2one(
        lambda: env.models.company, string="Company"
    )
    notes: str | None = Text(string="Notes")
    type: str = Selection(
        options=[
            ("lead", "Lead"),
            ("opportunity", "Opportunity"),
        ],
        default="lead",
        string="Type",
    )

    connector_id: "ChatConnector | None" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        string="Connector",
        ondelete="set null",
        description="Коннектор, через который создан лид",
    )

    # Команда лида. Раньше strategy._get_or_create_lead писал team_id из
    # правила маршрутизации, но поля не было → значение молча терялось.
    # Добавлено как реальное поле (правило маршрутизации теперь работает).
    team_id: "TeamCrm | None" = Many2one(
        relation_table=lambda: env.models.team_crm,
        string="Team",
        ondelete="set null",
        index=True,
        description="Команда, ответственная за лид",
    )

    website: str | None = Char(
        max_length=500,
        string="Website URL",
        description="URL объявления / контекста лида",
    )

    # Контакты (телефоны, email, telegram и т.д.)
    # Внешние аккаунты доступны через contact_ids.external_account_ids
    contact_ids: list["Contact"] = One2many(
        store=False,
        relation_table=lambda: env.models.contact,
        relation_table_field="partner_id",
        description="Контакты",
    )

    @hybridmethod
    async def update(
        self, payload, fields=None, session=None, depends_jobs=None
    ):
        """Pull-модель: когда лид «берут» (появляется user_id), ответственный
        автоматически подписывается на внешний чат клиента по этому коннектору.

        Лид создаётся без user_id и лежит в общем пуле; первый, кто поставит
        себя в Salesperson, становится участником чата и может писать клиенту.
        Старых участников не трогаем — история переписки видна всем, кто был
        в чате.
        """
        result = await super().update(payload, fields, session, depends_jobs)

        # Только когда проставляют ответственного.
        if fields is not None and "user_id" not in fields:
            return result
        if not payload.user_id or not self.partner_id or not self.connector_id:
            return result

        # Чаты клиента по этому коннектору: партнёр — активный участник, и
        # чат привязан к внешнему чату коннектора. Подписываем ответственного
        # (_ensure_membership добавит, только если ещё не участник).
        try:
            partner_members = await env.models.chat_member.search(
                filter=[
                    ("partner_id", "=", self.partner_id.id),
                    ("is_active", "=", True),
                ],
                fields=["chat_id"],
            )
            chat_ids = [m.chat_id.id for m in partner_members if m.chat_id]
            if chat_ids:
                ext_chats = await env.models.chat_external_chat.search(
                    filter=[
                        ("connector_id", "=", self.connector_id.id),
                        ("chat_id", "in", chat_ids),
                    ],
                    fields=["chat_id"],
                )
                for ec in ext_chats:
                    await env.models.chat._ensure_membership(
                        ec.chat_id.id, payload.user_id.id
                    )
                    # _ensure_membership добавляет DB-участника, но НЕ
                    # подписывает live WS-сессию ответственного и не шлёт ему
                    # chat_created → без этого диалог всплывает у него только
                    # после рефреша. notify_new_chat (cross-worker через
                    # pubsub) подписывает его WS на любом воркере и уведомляет
                    # фронт. Best-effort: сбой не должен ломать обновление лида.
                    try:
                        await env.apps.chat.chat_manager.notify_new_chat(
                            payload.user_id.id, ec.chat_id.id
                        )
                    except Exception as notify_exc:  # noqa: BLE001
                        logger.warning(
                            "Lead %s: notify_new_chat failed for chat %s: %s",
                            self.id,
                            ec.chat_id.id,
                            notify_exc,
                        )
        except Exception as exc:  # noqa: BLE001
            # Подписка не должна ломать обновление лида.
            logger.warning(
                "Lead %s: failed to subscribe user to chat: %s", self.id, exc
            )
        return result
