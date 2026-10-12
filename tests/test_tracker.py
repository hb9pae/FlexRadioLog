"""Tests for RadioStateTracker session and PTT logic."""

import pytest
from sqlalchemy import select
from flexradiolog.config import DatabaseConfig, IpAllocationItem
from flexradiolog.db.database import Database
from flexradiolog.db.models import PttEvent, Session
from flexradiolog.radio.parser import ProtocolParser
from flexradiolog.radio.tracker import RadioStateTracker


@pytest.mark.asyncio
async def test_tracker_client_lifecycle():
    db = Database(DatabaseConfig(url="sqlite+aiosqlite:///:memory:"))
    await db.init_models()
    await db.seed_initial_allocations([
        IpAllocationItem(ip_address="192.168.84.100", callsign="HB9ABC", operator_name="Alice"),
    ])

    tracker = RadioStateTracker(db)
    await tracker.reload_ip_cache()

    # 1. Client connects
    conn_line = "S0|client 1111-2222-3333 connected=1 ip=192.168.84.100 name=SmartSDR-Win station=MyStation handle=0x1234 gui=1"
    msg_conn = ProtocolParser.parse_line(conn_line)
    await tracker.process_message(msg_conn)

    assert "1111-2222-3333" in tracker.active_sessions_by_uuid
    active_s = tracker.active_sessions_by_uuid["1111-2222-3333"]
    assert active_s.callsign == "HB9ABC"
    assert active_s.client_ip == "192.168.84.100"

    # Verify session in DB
    async for session in db.get_session():
        stmt = select(Session).where(Session.client_uuid == "1111-2222-3333")
        res = await session.execute(stmt)
        db_s = res.scalar_one()
        assert db_s.is_active is True
        assert db_s.callsign == "HB9ABC"

    # 2. Client disconnects
    disconn_line = "S0|client 1111-2222-3333 connected=0"
    msg_disconn = ProtocolParser.parse_line(disconn_line)
    await tracker.process_message(msg_disconn)

    assert "1111-2222-3333" not in tracker.active_sessions_by_uuid

    # Verify session marked closed in DB
    async for session in db.get_session():
        stmt = select(Session).where(Session.client_uuid == "1111-2222-3333")
        res = await session.execute(stmt)
        db_s = res.scalar_one()
        assert db_s.is_active is False
        assert db_s.disconnect_reason == "LOGOUT"
        assert db_s.end_time is not None

    await db.close()


@pytest.mark.asyncio
async def test_tracker_ptt_and_slice():
    db = Database(DatabaseConfig(url="sqlite+aiosqlite:///:memory:"))
    await db.init_models()

    tracker = RadioStateTracker(db)

    # 1. Client connects (fallback to station name if not in IP allocation)
    conn_line = "S0|client 4444-5555 connected=1 ip=192.168.84.50 station=HB9XYZ handle=0xABCD"
    await tracker.process_message(ProtocolParser.parse_line(conn_line))

    # 2. Slice update
    slice_line = "S0|slice 0 RF_frequency=14.074000 mode=USB tx=1 client_handle=0xABCD"
    await tracker.process_message(ProtocolParser.parse_line(slice_line))

    assert 0 in tracker.slices
    assert tracker.slices[0].frequency_hz == 14_074_000
    assert tracker.slices[0].mode == "USB"
    assert tracker.slices[0].is_tx is True

    # 3. Interlock TX start
    tx_start_line = "S0|interlock state=TRANSMITTING source=SW tx_client_handle=0xABCD"
    await tracker.process_message(ProtocolParser.parse_line(tx_start_line))

    assert tracker.current_ptt is not None
    assert tracker.current_ptt.frequency_hz == 14_074_000
    assert tracker.current_ptt.band == "20m"

    # 4. Interlock TX end
    tx_end_line = "S0|interlock state=READY source= tx_client_handle=0x0"
    await tracker.process_message(ProtocolParser.parse_line(tx_end_line))

    assert tracker.current_ptt is None

    # Verify PttEvent in DB
    async for session in db.get_session():
        stmt = select(PttEvent)
        res = await session.execute(stmt)
        events = res.scalars().all()
        assert len(events) == 1
        ev = events[0]
        assert ev.frequency_hz == 14_074_000
        assert ev.band == "20m"
        assert ev.mode == "USB"
        assert ev.session_id is not None

    await db.close()


@pytest.mark.asyncio
async def test_tracker_radio_disconnect():
    db = Database(DatabaseConfig(url="sqlite+aiosqlite:///:memory:"))
    await db.init_models()

    tracker = RadioStateTracker(db)
    # Connect client and start PTT
    await tracker.process_message(ProtocolParser.parse_line("S0|client uuid-a connected=1 ip=192.168.84.22 station=HB9DC"))
    await tracker.process_message(ProtocolParser.parse_line("S0|interlock state=TRANSMITTING"))

    assert len(tracker.active_sessions_by_uuid) == 1
    assert tracker.current_ptt is not None

    # Disconnect radio
    await tracker.on_radio_disconnected("RADIO_OFFLINE")

    assert len(tracker.active_sessions_by_uuid) == 0
    assert tracker.current_ptt is None

    async for session in db.get_session():
        # Session closed
        s_stmt = select(Session)
        s_res = await session.execute(s_stmt)
        s_record = s_res.scalar_one()
        assert s_record.is_active is False
        assert s_record.disconnect_reason == "RADIO_OFFLINE"

        # PTT saved
        p_stmt = select(PttEvent)
        p_res = await session.execute(p_stmt)
        p_events = p_res.scalars().all()
        assert len(p_events) == 1

    await db.close()
