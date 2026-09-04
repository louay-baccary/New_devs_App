import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import logging
from ..config import settings

logger = logging.getLogger(__name__)

class DatabasePool:
    def __init__(self):
        self.engine = None
        self.session_factory = None

    async def initialize(self):
        """Initialize database connection pool"""
        try:
            # ============================================================
            # BUG #1 - wrong settings attributes (AttributeError)
            # ============================================================
            # OLD (BUGGY) CODE:
            #   database_url = f"postgresql+asyncpg://{settings.supabase_db_user}:{settings.supabase_db_password}@{settings.supabase_db_host}:{settings.supabase_db_port}/{settings.supabase_db_name}"
            #
            # ERROR PRODUCED (caught by the except below and logged):
            #   ERROR:app.core.database_pool:❌ Database pool initialization failed:
            #   'Settings' object has no attribute 'supabase_db_user'
            #
            # ROOT CAUSE: app/config.py's Settings class only defines
            # `database_url` (matching docker-compose's DATABASE_URL env var
            # for the local Postgres container) - there is no
            # supabase_db_user/password/host/port/name field anywhere on it.
            # Every call to initialize() threw AttributeError immediately,
            # was silently swallowed by the except block, and left
            # session_factory = None permanently. That forced every revenue
            # lookup down the except-block fallback in reservations.py, which
            # returns hardcoded mock data keyed ONLY by property_id (ignoring
            # tenant_id) - the real root cause of both clients seeing
            # identical revenue numbers.
            #
            # FIX: use settings.database_url directly, swapping the scheme
            # for the asyncpg driver.
            database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            print(f"DEBUG DB POOL: connecting with {database_url}")

            # ============================================================
            # BUG #2 - QueuePool incompatible with async engine
            # ============================================================
            # OLD (BUGGY) CODE:
            #   self.engine = create_async_engine(
            #       database_url,
            #       poolclass=QueuePool,   # <-- this line, plus `from sqlalchemy.pool import QueuePool` at the top
            #       pool_size=20,
            #       ...
            #   )
            #
            # ERROR PRODUCED (confirmed live, twice - once originally, once
            # again when poolclass=QueuePool was temporarily re-added to
            # double check this was really the cause):
            #   ERROR:app.core.database_pool:❌ Database pool initialization failed:
            #   Pool class QueuePool cannot be used with asyncio engine
            #   (Background on this error at: https://sqlalche.me/e/20/pcls)
            #
            # ROOT CAUSE: QueuePool is SQLAlchemy's SYNCHRONOUS pool
            # implementation. create_async_engine requires an async-compatible
            # pool class (or none, letting it pick its own default) - passing
            # the sync QueuePool explicitly makes it raise immediately. This
            # was bug #2 hiding behind bug #1: even after fixing the
            # connection string above, initialization still failed here,
            # still falling through to the same tenant-blind mock data.
            #
            # FIX: don't pass poolclass at all - create_async_engine selects
            # its own correct async-compatible default pool automatically.
            self.engine = create_async_engine(
                database_url,
                pool_size=20,  # Number of connections to maintain
                max_overflow=30,  # Additional connections when needed
                pool_pre_ping=True,  # Validate connections
                pool_recycle=3600,  # Recycle connections every hour
                echo=False  # Set to True for SQL debugging
            )

            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            logger.info("✅ Database connection pool initialized")

        except Exception as e:
            logger.error(f"❌ Database pool initialization failed: {e}")
            self.engine = None
            self.session_factory = None

    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()

    # ============================================================
    # BUG #3 - async def wrapping an async context manager in a coroutine
    # ============================================================
    # OLD (BUGGY) CODE:
    #   async def get_session(self) -> AsyncSession:
    #       """Get database session from pool"""
    #       if not self.session_factory:
    #           raise Exception("Database pool not initialized")
    #       return self.session_factory()
    #
    # ERROR PRODUCED (surfaced in reservations.py's except block once bugs
    # #1 and #2 above were fixed and the DB path was finally reached):
    #   Database error for prop-001 (tenant: tenant-a):
    #   'coroutine' object does not support the asynchronous context manager protocol
    #
    # ROOT CAUSE: this method did no awaited work internally -
    # self.session_factory() directly returns an AsyncSession, which already
    # implements __aenter__/__aexit__ and is meant to be used as
    # `async with db_pool.get_session() as session:`. Because the method
    # itself was declared `async def`, CALLING it produced a coroutine
    # WRAPPING that session object, and `async with <coroutine>` fails,
    # since a coroutine doesn't implement __aenter__/__aexit__ - only the
    # AsyncSession inside it does. This was the third bug in the chain,
    # only visible after bugs #1 and #2 were both fixed.
    #
    # FIX: remove `async` - calling get_session() now returns the
    # AsyncSession object itself, which `async with` can use directly.
    def get_session(self) -> AsyncSession:
        """Get database session from pool"""
        if not self.session_factory:
            raise Exception("Database pool not initialized")
        return self.session_factory()

# Global database pool instance
db_pool = DatabasePool()

async def get_db_session() -> AsyncSession:
    """Dependency to get database session"""
    async with db_pool.get_session() as session:
        yield session
