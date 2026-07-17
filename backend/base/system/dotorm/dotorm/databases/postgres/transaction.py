"""PostgreSQL transaction management."""

from contextvars import ContextVar

try:
    import asyncpg
    from asyncpg.transaction import Transaction
except ImportError:
    asyncpg = None  # type: ignore
    Transaction = None  # type: ignore

from .session import TransactionSession

# Context variable для хранения текущей сессии транзакции
_current_session: ContextVar["TransactionSession | None"] = ContextVar(
    "current_session", default=None
)


def get_current_session() -> "TransactionSession | None":
    """Получить текущую сессию из контекста (если есть активная транзакция)."""
    return _current_session.get()


class ContainerTransaction:
    """
    Transaction context manager for PostgreSQL.

    Acquires connection, starts transaction, executes queries,
    commits on success, rollbacks on exception.

    Автоматически устанавливает текущую сессию в contextvars,
    так что методы ORM могут использовать её без явной передачи.

    ВЛОЖЕННОСТЬ (transaction propagation = REQUIRED).
    Если транзакция уже открыта в этом контексте, НЕ берём второе соединение из
    пула, а вкладываемся в существующее: asyncpg на вложенный
    connection.transaction() выпускает SAVEPOINT.

    Раньше __aenter__ безусловно делал pool.acquire() + transaction.start(), и
    вложенный `async with get_transaction()` открывал ВТОРУЮ ПАРАЛЛЕЛЬНУЮ
    транзакцию на ДРУГОМ соединении. Она не видела незакоммиченных данных
    внешней, поэтому любой код вида

        async with get_transaction():          # внешняя, conn A
            partner = await create_partner()   # INSERT в A, не закоммичен
            await get_or_create_partner_chat() # внутри — своя TX на conn B
                                               # -> INSERT chat_member(partner)
                                               # -> ForeignKeyViolationError:
                                               #    "Ключ (partner_id)=(1)
                                               #     отсутствует в partners"

    падал на ровном месте. Воспроизведено на живой БД: conn B действительно не
    видит партнёра, созданного в незакоммиченной TX conn A. Так ломался приём
    первого письма от неизвестного адреса (создание партнёра и чата — в одной
    внешней транзакции крона).

    Побочно чинится и риск дедлока: вложенный acquire брал второе соединение,
    удерживая первое, и при исчерпанном пуле вставал намертво.

    Семантика после фикса:
      - внутренний commit   -> RELEASE SAVEPOINT (внешняя жива, решает она);
      - внутренний rollback -> ROLLBACK TO SAVEPOINT (внешняя цела);
      - откат внешней       -> откатывает и вложенные (как и должно быть).

    Example:
        async with ContainerTransaction(pool) as session:
            await session.execute("INSERT INTO users ...")
            # Или без явной передачи session:
            await User.create(payload=user)  # session подставится из контекста
            # Commits on exit
    """

    default_pool: "asyncpg.Pool | None" = None

    def __init__(self, pool: "asyncpg.Pool | None" = None):
        self.session_factory = TransactionSession
        if pool is None:
            assert self.default_pool is not None
            self.pool = self.default_pool
        else:
            self.pool = pool
        self._token = None
        # Взяли ли соединение из пула сами (значит, нам его и возвращать).
        self._own_connection = True

    async def __aenter__(self):
        parent = _current_session.get()

        if parent is not None:
            # Уже внутри транзакции — переиспользуем ЕЁ соединение, иначе не
            # увидим её незакоммиченных данных (см. докстринг класса).
            connection: "asyncpg.Connection" = parent.connection
            self._own_connection = False
        else:
            connection = await self.pool.acquire()
            self._own_connection = True

        # На вложенном вызове asyncpg сам выпустит SAVEPOINT вместо BEGIN.
        transaction = connection.transaction()

        assert isinstance(transaction, Transaction)
        assert isinstance(connection, asyncpg.Connection)

        await transaction.start()
        self.session = self.session_factory(connection, transaction)

        # Устанавливаем текущую сессию в контекст
        self._token = _current_session.set(self.session)

        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Сбрасываем контекст
        if self._token is not None:
            _current_session.reset(self._token)

        if exc_type is not None:
            # Выпало исключение вызвать ролбек
            # (вложенный -> ROLLBACK TO SAVEPOINT, внешняя транзакция цела)
            await self.session.transaction.rollback()
        else:
            # Не выпало исключение вызвать комит
            # (вложенный -> RELEASE SAVEPOINT; реальный COMMIT сделает внешняя)
            await self.session.transaction.commit()

        # Соединение возвращает в пул только тот, кто его брал: вложенный блок
        # им не владеет, и release здесь оборвал бы внешнюю транзакцию.
        if self._own_connection:
            await self.pool.release(self.session.connection)
