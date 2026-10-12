"""Tests for database engine, models, and operations."""

import pytest
from sqlalchemy import select
from flexradiolog.config import DatabaseConfig, IpAllocationItem
from flexradiolog.db.database import Database
from flexradiolog.db.models import IpAllocation, PttEvent, Session, utc_now


@pytest.mark.asyncio
async def test_database_init_and_seed():
    db = Database(DatabaseConfig(url="sqlite+aiosqlite:///:memory:"))
    try:
        await db.init_models()

        # Seed initial allocations
        allocs = [
            IpAllocationItem(ip_address="192.168.1.10", callsign="HB9AAA", operator_name="Alice"),
            IpAllocationItem(ip_address="192.168.1.20", callsign="HB9BBB", operator_name="Bob"),
        ]
        await db.seed_initial_allocations(allocs)

        # Verify seeded data
        async for session in db.get_session():
            stmt = select(IpAllocation).order_by(IpAllocation.callsign)
            result = await session.execute(stmt)
            items = result.scalars().all()
            assert len(items) == 2
            assert items[0].callsign == "HB9AAA"
            assert items[1].callsign == "HB9BBB"

        # Verify duplicate seeding does not fail or duplicate
        await db.seed_initial_allocations(allocs)
        async for session in db.get_session():
            stmt = select(IpAllocation)
            result = await session.execute(stmt)
            assert len(result.scalars().all()) == 2
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_session_and_ptt_relations():
    db = Database(DatabaseConfig(url="sqlite+aiosqlite:///:memory:"))
    try:
        await db.init_models()

        start = utc_now()
        async for session in db.get_session():
            radio_session = Session(
                client_uuid="550e8400-e29b-41d4-a716-446655440000",
                client_handle="0x12345678",
                client_ip="192.168.84.10",
                callsign="HB9TEST",
                client_name="SmartSDR-Win",
                station="MainShack",
                start_time=start,
                is_active=True,
            )
            session.add(radio_session)
            await session.commit()
            await session.refresh(radio_session)

            ptt = PttEvent(
                session_id=radio_session.id,
                client_handle="0x12345678",
                start_time=start,
                end_time=start,
                duration_seconds=3.5,
                frequency_hz=14_074_000,
                band="20m",
                mode="USB",
                tx_slice_id=0,
            )
            session.add(ptt)
            await session.commit()

        # Verify relations
        async for session in db.get_session():
            stmt = select(Session).where(Session.callsign == "HB9TEST")
            result = await session.execute(stmt)
            loaded = result.scalar_one()
            assert loaded.is_active is True

            stmt_ptt = select(PttEvent).where(PttEvent.session_id == loaded.id)
            ptt_result = await session.execute(stmt_ptt)
            ptts = ptt_result.scalars().all()
            assert len(ptts) == 1
            assert ptts[0].frequency_hz == 14_074_000
            assert ptts[0].band == "20m"
            assert ptts[0].duration_seconds == 3.5
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_close_abandoned_sessions():
    db = Database(DatabaseConfig(url="sqlite+aiosqlite:///:memory:"))
    try:
        await db.init_models()

        async for session in db.get_session():
            s1 = Session(
                client_uuid="uuid-1",
                client_ip="192.168.84.10",
                callsign="HB9ONE",
                start_time=utc_now(),
                is_active=True,
            )
            s2 = Session(
                client_uuid="uuid-2",
                client_ip="192.168.84.20",
                callsign="HB9TWO",
                start_time=utc_now(),
                is_active=False,
            )
            session.add_all([s1, s2])
            await session.commit()

        closed = await db.close_abandoned_sessions()
        assert closed == 1

        async for session in db.get_session():
            stmt = select(Session).where(Session.is_active == True)  # noqa: E712
            result = await session.execute(stmt)
            assert len(result.scalars().all()) == 0
    finally:
        await db.close()
