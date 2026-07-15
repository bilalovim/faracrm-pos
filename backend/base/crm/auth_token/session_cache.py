# Copyright 2025 FARA CRM
# Auth - in-memory session cache with pg_notify-based invalidation

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


# Ключ в system_settings. Значение: bool/str "true"/"false"/"1"/"0".
SETTING_KEY = "auth.session_cache_enabled"


@dataclass
class CachedSession:
    """Слепок данных сессии + присоединённых полей user/language.
    Позволяет собрать Session-объект без хождения в БД.
    """

    session_id: int
    user_id: int
    is_admin: bool
    user_name: str
    lang_id: int | None
    lang_code: str | None
    cookie_token: str | None
    token: str | None
    expired_datetime: datetime
    ttl: int
    create_datetime: datetime
    revoked: bool = False
    # Развёрнутые коды ролей (с учётом based_role_ids) — кладутся при
    # сборке сессии, чтобы field-level проверка не ходила в БД на каждый
    # write. Сбрасываются через invalidate_user при смене ролей.
    role_codes: tuple[str, ...] = ()
    # ID команд пользователя (team_crm.user_ids) — кладутся при сборке сессии,
    # чтобы доступ по командам ({{team_ids}}) не ходил в БД на каждую проверку.
    # Инвалидация — тем же invalidate_user (publish_roles_changed при смене
    # состава команды: команды = authz-атрибут).
    team_ids: tuple[int, ...] = ()


class SessionCache:
    """
    In-memory кэш сессий для избежания походов в БД на каждый verify.

    Инвалидация через pg_notify: при logout / revoke публикуется событие
    session_revoked, воркеры помечают запись как revoked.

    Два индекса доступа: token и cookie_token — обе функции проверки
    (Bearer+cookie и только cookie) ходят через один и тот же кэш.
    """

    def __init__(self):
        self._by_token: dict[str, CachedSession] = {}
        self._by_cookie: dict[str, CachedSession] = {}
        self._by_session_id: dict[int, CachedSession] = {}
        # user_id → set(session_id): чтобы по смене ролей сбросить ВСЕ
        # сессии пользователя (у юзера их может быть несколько).
        self._by_user_id: dict[int, set[int]] = {}
        self._lock = asyncio.Lock()

    def _index_user(self, cached: CachedSession) -> None:
        if cached.user_id not in self._by_user_id:
            self._by_user_id[cached.user_id] = set()
        self._by_user_id[cached.user_id].add(cached.session_id)

    def _unindex_user(self, cached: CachedSession) -> None:
        sids = self._by_user_id.get(cached.user_id)
        if sids is not None:
            sids.discard(cached.session_id)
            if not sids:
                self._by_user_id.pop(cached.user_id, None)

    async def get_by_token(self, token: str) -> CachedSession | None:
        async with self._lock:
            return self._by_token.get(token)

    async def get_by_cookie(self, cookie_token: str) -> CachedSession | None:
        async with self._lock:
            return self._by_cookie.get(cookie_token)

    async def put(self, cached: CachedSession) -> None:
        async with self._lock:
            # Если по session_id уже была запись — вычищаем её старые индексы,
            # чтобы при ротации tokens не оставалось мусора.
            prev = self._by_session_id.get(cached.session_id)
            if prev is not None:
                if prev.token and prev.token != cached.token:
                    self._by_token.pop(prev.token, None)
                if (
                    prev.cookie_token
                    and prev.cookie_token != cached.cookie_token
                ):
                    self._by_cookie.pop(prev.cookie_token, None)

            if cached.token:
                self._by_token[cached.token] = cached
            if cached.cookie_token:
                self._by_cookie[cached.cookie_token] = cached
            self._by_session_id[cached.session_id] = cached
            self._index_user(cached)

    async def revoke(self, session_id: int) -> str | None:
        """
        Пометить запись revoked и вернуть token для принудительного закрытия
        WS (если есть). Вызывается из pg_notify handler.
        """
        async with self._lock:
            cached = self._by_session_id.pop(session_id, None)
            if cached is None:
                return None
            cached.revoked = True
            if cached.token:
                self._by_token.pop(cached.token, None)
            if cached.cookie_token:
                self._by_cookie.pop(cached.cookie_token, None)
            self._unindex_user(cached)
            logger.debug("SessionCache: session %s revoked", session_id)
            return cached.token

    async def drop_by_token(self, token: str) -> None:
        async with self._lock:
            cached = self._by_token.pop(token, None)
            if cached is not None:
                self._by_session_id.pop(cached.session_id, None)
                if cached.cookie_token:
                    self._by_cookie.pop(cached.cookie_token, None)
                self._unindex_user(cached)

    async def invalidate_user(self, user_id: int) -> list[str]:
        """
        Сбросить кэш ВСЕХ сессий пользователя (НЕ revoke).

        В отличие от revoke (logout) — просто удаляет записи из кэша, не
        помечая revoked. Следующий запрос промахнётся мимо кэша и
        пересоберёт сессию из БД уже со свежими ролями. Вызывается из
        pg_notify-обработчика при смене role_ids/is_admin/иерархии.

        Returns: список token'ов сброшенных сессий (для опц. WS-нужд).
        """
        async with self._lock:
            sids = self._by_user_id.pop(user_id, set())
            tokens: list[str] = []
            for sid in list(sids):
                cached = self._by_session_id.pop(sid, None)
                if cached is None:
                    continue
                if cached.token:
                    self._by_token.pop(cached.token, None)
                    tokens.append(cached.token)
                if cached.cookie_token:
                    self._by_cookie.pop(cached.cookie_token, None)
            if sids:
                logger.debug(
                    "SessionCache: invalidated %s sessions of user %s",
                    len(sids),
                    user_id,
                )
            return tokens

    async def clear(self) -> None:
        async with self._lock:
            self._by_token.clear()
            self._by_cookie.clear()
            self._by_session_id.clear()
            self._by_user_id.clear()

    def size(self) -> int:
        return len(self._by_session_id)
