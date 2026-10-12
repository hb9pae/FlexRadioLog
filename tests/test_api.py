"""Tests for FastAPI REST API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from flexradiolog.api.app import create_app
from flexradiolog.config import AppConfig, DatabaseConfig, IpAllocationItem, RadioConfig
from flexradiolog.db.models import PttEvent, Session, utc_now


@pytest.fixture
async def app_and_client():
    config = AppConfig(
        radio=RadioConfig(host="127.0.0.1", port=4992),
        database=DatabaseConfig(url="sqlite+aiosqlite:///:memory:"),
        initial_allocations=[
            IpAllocationItem(ip_address="192.168.84.10", callsign="HB9ALPHA", operator_name="Alice"),
        ],
    )
    # Do not start radio connection task in unit test
    app = create_app(config, start_radio_client=False)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield app, client


@pytest.mark.asyncio
async def test_api_status(app_and_client):
    app, client = app_and_client
    resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["host"] == "127.0.0.1"
    assert data["port"] == 4992
    assert data["is_connected"] is False
    assert data["is_transmitting"] is False


@pytest.mark.asyncio
async def test_api_allocations_crud(app_and_client):
    app, client = app_and_client

    # List initial allocations
    resp = await client.get("/api/allocations")
    assert resp.status_code == 200
    allocs = resp.json()
    assert len(allocs) == 1
    assert allocs[0]["callsign"] == "HB9ALPHA"

    # Create new allocation
    create_payload = {
        "ip_address": "192.168.84.20",
        "callsign": "HB9BETA",
        "operator_name": "Bob",
        "notes": "Remote station",
    }
    resp = await client.post("/api/allocations", json=create_payload)
    assert resp.status_code == 200
    created = resp.json()
    assert created["callsign"] == "HB9BETA"
    alloc_id = created["id"]

    # Verify updated list
    resp = await client.get("/api/allocations")
    assert len(resp.json()) == 2

    # Delete allocation
    resp = await client.delete(f"/api/allocations/{alloc_id}")
    assert resp.status_code == 200

    resp = await client.get("/api/allocations")
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_api_sessions_and_ptt_query(app_and_client):
    app, client = app_and_client
    db = app.state.db

    # Insert test session and PTT records
    now = utc_now()
    async for db_session in db.get_session():
        s = Session(
            client_uuid="sess-uuid-1",
            client_ip="192.168.84.10",
            callsign="HB9ALPHA",
            client_name="SmartSDR-Win",
            station="Main",
            start_time=now,
            end_time=now,
            duration_seconds=300,
            is_active=False,
            disconnect_reason="LOGOUT",
        )
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        p1 = PttEvent(
            session_id=s.id,
            start_time=now,
            end_time=now,
            duration_seconds=12.5,
            frequency_hz=14_074_000,
            band="20m",
            mode="USB",
        )
        p2 = PttEvent(
            session_id=s.id,
            start_time=now,
            end_time=now,
            duration_seconds=5.0,
            frequency_hz=7_074_000,
            band="40m",
            mode="USB",
        )
        db_session.add_all([p1, p2])
        await db_session.commit()

        session_id = s.id

    # 1. Query sessions
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 1
    assert sessions[0]["callsign"] == "HB9ALPHA"
    assert sessions[0]["ptt_count"] == 2
    assert sessions[0]["total_ptt_duration_seconds"] == 17.5

    # 2. Query session detail
    resp = await client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == session_id
    assert len(detail["ptt_events"]) == 2

    # 3. Query session PTT list
    resp = await client.get(f"/api/sessions/{session_id}/ptt")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # 4. Query global PTT list with filter
    resp = await client.get("/api/ptt?band=20m")
    assert resp.status_code == 200
    ptts_20m = resp.json()
    assert len(ptts_20m) == 1
    assert ptts_20m[0]["band"] == "20m"

    # 5. Query stats summary
    resp = await client.get("/api/stats/summary")
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_sessions"] == 1
    assert stats["total_ptt_count"] == 2
    assert stats["total_ptt_duration_seconds"] == 17.5
    assert len(stats["per_operator"]) == 1
    assert stats["per_operator"][0]["callsign"] == "HB9ALPHA"
    assert len(stats["per_band"]) == 2
