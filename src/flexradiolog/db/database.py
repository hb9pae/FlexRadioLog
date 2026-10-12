"""Database engine and session management."""

import logging
from typing import AsyncGenerator, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from flexradiolog.config import AppConfig, DatabaseConfig, IpAllocationItem
from flexradiolog.db.models import (
    Base,
    IpAllocation,
    Session,
    SystemEvent,
    calculate_duration_seconds,
    utc_now,
)

logger = logging.getLogger(__name__)


class Database:
    """Manages SQLite async engine and sessions."""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        if config is None:
            config = DatabaseConfig()
        self.config = config
        self.engine: AsyncEngine = create_async_engine(
            self.config.url,
            echo=self.config.echo,
            future=True,
        )
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_models(self) -> None:
        """Create database tables if they do not exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created successfully.")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Dependency generator yielding an async database session."""
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def seed_initial_allocations(self, allocations: List[IpAllocationItem]) -> None:
        """Seed initial IP allocations into database if not present."""
        if not allocations:
            return

        async with self.session_factory() as session:
            for item in allocations:
                stmt = select(IpAllocation).where(IpAllocation.ip_address == item.ip_address)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if not existing:
                    new_alloc = IpAllocation(
                        ip_address=item.ip_address,
                        callsign=item.callsign,
                        operator_name=item.operator_name or "",
                        notes=item.notes or "",
                    )
                    session.add(new_alloc)
                    logger.info("Seeded IP allocation: %s -> %s", item.ip_address, item.callsign)
            await session.commit()

    async def close_abandoned_sessions(self) -> int:
        """Close any sessions that were active before server start/restart."""
        async with self.session_factory() as session:
            stmt = select(Session).where(Session.is_active == True)  # noqa: E712
            result = await session.execute(stmt)
            open_sessions = result.scalars().all()
            count = len(open_sessions)

            now = utc_now()
            for s in open_sessions:
                s.is_active = False
                s.end_time = now
                s.disconnect_reason = "SERVER_RESTARTED"
                if s.start_time:
                    s.duration_seconds = calculate_duration_seconds(s.start_time, now)

            if count > 0:
                await session.commit()
                logger.info("Closed %d abandoned active sessions from previous run.", count)
            return count

    async def close(self) -> None:
        """Dispose of the database engine."""
        await self.engine.dispose()
        logger.info("Database engine disposed.")
