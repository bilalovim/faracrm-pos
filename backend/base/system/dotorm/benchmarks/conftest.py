"""Benchmark fixtures and configuration.

Benchmarks are driven SYNCHRONOUSLY: pytest-benchmark repeatedly calls a plain
sync callable, so tests are `def` (not `async def`) and drive their coroutines
via run_async(), which reuses ONE persistent event loop for the whole session.

Why one shared loop: the asyncpg pool (and the SQLAlchemy/Tortoise connections)
are created on that loop, and every benchmark round runs its queries on the same
loop — so connections are never torn down mid-operation. Mixing `async def`
tests (pytest-asyncio drives its own loop) with benchmark's own
run_until_complete puts the pool on one loop and the query on another, which
surfaces as `asyncpg ConnectionDoesNotExistError: connection was closed in the
middle of operation`.

Do NOT make these tests `async def`, and do NOT redefine pytest-asyncio's
`event_loop` fixture (removed in pytest-asyncio >= 1.0).
"""

import asyncio
import pytest

# Try to import database drivers
try:
    import asyncpg
except ImportError:
    asyncpg = None

try:
    from sqlalchemy.ext.asyncio import create_async_engine
except ImportError:
    create_async_engine = None

try:
    from tortoise import Tortoise
except ImportError:
    Tortoise = None


# memory_test.py is a memory-PROFILING script (run via
# `python -m memory_profiler benchmarks/memory_test.py`), not a pytest suite:
# its test_* functions take params, return values and drive their own event
# loop via asyncio.get_event_loop().run_until_complete — which hangs under
# pytest-asyncio. Keep it out of the pytest benchmark run.
collect_ignore = ["memory_test.py"]


# Database configuration
DATABASE_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "openpg",
    "password": "openpgpwd",
    "database": "benchmark_test",
}

DATABASE_URL = (
    f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}"
    f"@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
)


# ═══════════════════════════════════════════════════════════════════════════
# Always-running event loop (background thread) for all benchmarks
# ═══════════════════════════════════════════════════════════════════════════
#
# The loop runs FOREVER in a dedicated thread; run_async() submits coroutines
# to it via run_coroutine_threadsafe and blocks for the result. This is the key
# to keeping a persistent asyncpg pool healthy across many benchmark rounds:
# with repeated loop.run_until_complete() the loop sits IDLE between calls, so
# pooled connections' protocol machinery (keepalive/timeouts) stops running and
# a later round reuses a dead connection → "connection was closed in the middle
# of operation". A continuously-running loop never lets connections rot.

import threading  # noqa: E402

_bench_loop: "asyncio.AbstractEventLoop | None" = None
_bench_thread: "threading.Thread | None" = None


def _ensure_bench_loop() -> "asyncio.AbstractEventLoop":
    """Return the shared loop, starting its background thread on first use."""
    global _bench_loop, _bench_thread
    if _bench_loop is not None and not _bench_loop.is_closed():
        return _bench_loop

    _bench_loop = asyncio.new_event_loop()

    def _run_forever(loop: "asyncio.AbstractEventLoop") -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    _bench_thread = threading.Thread(
        target=_run_forever,
        args=(_bench_loop,),
        name="bench-loop",
        daemon=True,
    )
    _bench_thread.start()
    return _bench_loop


_set_access_session = None


async def _with_access(coro):
    """Set a DotORM access session in THIS task's context, then run `coro`.

    DotORM default-denies CRUD when no session is in context. Benchmarks use the
    permissive default AccessChecker, so any non-None session unlocks access.
    It must be set inside the task (on the bench loop), not from a main-thread
    fixture: the loop runs in another thread and the ContextVar wouldn't carry
    across. Set at task start → all awaited DotORM ops inherit it.
    """
    global _set_access_session
    if _set_access_session is None:
        try:
            from dotorm.access import set_access_session as _s

            _set_access_session = _s
        except Exception:  # dotorm not importable (e.g. non-DotORM benchmarks)
            _set_access_session = False
    if _set_access_session:
        _set_access_session(object())
    return await coro


def run_async(coro):
    """Submit a coroutine to the always-running benchmark loop and block.

    Used by fixtures (setup/teardown) and benchmarked callables alike, so the
    pool and every query run on one continuously-running event loop.
    """
    loop = _ensure_bench_loop()
    return asyncio.run_coroutine_threadsafe(_with_access(coro), loop).result()


@pytest.fixture(scope="session")
def bench_loop():
    """Own the shared loop for the session and stop it at the end.

    Resource fixtures (dotorm_pool, sqlalchemy_engine, tortoise_connection)
    depend on this so the loop outlives their teardown.
    """
    loop = _ensure_bench_loop()
    yield loop
    global _bench_loop, _bench_thread
    loop.call_soon_threadsafe(loop.stop)
    if _bench_thread is not None:
        _bench_thread.join(timeout=5)
    if not loop.is_closed():
        loop.close()
    _bench_loop = None
    _bench_thread = None


# ═══════════════════════════════════════════════════════════════════════════
# Resource fixtures (sync — driven via run_async on the shared loop)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def dotorm_pool(bench_loop):
    """Create DotORM connection pool."""
    if asyncpg is None:
        pytest.skip("asyncpg not installed")

    from dotorm.databases.postgres import ContainerPostgres
    from dotorm.databases.abstract import (
        PostgresPoolSettings,
        ContainerSettings,
    )

    pool_settings = PostgresPoolSettings(**DATABASE_CONFIG)
    container_settings = ContainerSettings(
        driver="asyncpg", reconnect_timeout=10
    )

    container = ContainerPostgres(pool_settings, container_settings)
    pool = run_async(container.create_pool())

    yield pool

    run_async(container.close_pool())


@pytest.fixture(scope="session")
def sqlalchemy_engine(bench_loop):
    """Create SQLAlchemy async engine."""
    if create_async_engine is None:
        pytest.skip("SQLAlchemy not installed")

    engine = create_async_engine(
        f"postgresql+asyncpg://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}"
        f"@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}",
        echo=False,
    )

    yield engine

    run_async(engine.dispose())


@pytest.fixture(scope="session")
def tortoise_connection(bench_loop):
    """Initialize Tortoise ORM."""
    if Tortoise is None:
        pytest.skip("Tortoise ORM not installed")

    run_async(
        Tortoise.init(
            db_url=f"postgres://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}"
            f"@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}",
            modules={"models": ["benchmarks.tortoise_models"]},
        )
    )

    yield

    run_async(Tortoise.close_connections())


@pytest.fixture
def clean_tables(dotorm_pool):
    """Clean test tables before each test."""

    async def _clean():
        async with dotorm_pool.acquire() as conn:
            await conn.execute(
                "TRUNCATE TABLE benchmark_users RESTART IDENTITY CASCADE"
            )
            await conn.execute(
                "TRUNCATE TABLE benchmark_roles RESTART IDENTITY CASCADE"
            )

    run_async(_clean())
    yield


# ═══════════════════════════════════════════════════════════════════════════
# Test data generators
# ═══════════════════════════════════════════════════════════════════════════


def generate_user_data(count: int) -> list[dict]:
    """Generate test user data."""
    return [
        {
            "name": f"User {i}",
            "email": f"user{i}@benchmark.test",
            "active": i % 2 == 0,
        }
        for i in range(count)
    ]


def generate_role_data(count: int) -> list[dict]:
    """Generate test role data."""
    return [
        {
            "name": f"Role {i}",
            "description": f"Description for role {i}",
        }
        for i in range(count)
    ]
