"""Integration test using a Mock FlexRadio TCP server."""

import asyncio
import pytest
from sqlalchemy import select
from flexradiolog.config import DatabaseConfig, RadioConfig
from flexradiolog.db.database import Database
from flexradiolog.db.models import PttEvent, Session
from flexradiolog.radio.client import RadioClient
from flexradiolog.radio.tracker import RadioStateTracker


class MockFlexRadioServer:
    """Mock TCP server imitating FlexRadio SmartSDR TCP port."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self.server: asyncio.Server | None = None
        self.client_writer: asyncio.StreamWriter | None = None

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.client_writer = writer
        # Send initial version and handle
        writer.write(b"V3.4.24.112\n")
        writer.write(b"H01234567\n")
        await writer.drain()

        # Read subscription commands
        while True:
            line = await reader.readline()
            if not line:
                break
            text = line.decode("utf-8").strip()
            if text.startswith("C1|"):
                writer.write(b"R1|0|\n")
            elif text.startswith("C2|"):
                writer.write(b"R2|0|\n")
            elif text.startswith("C3|"):
                writer.write(b"R3|0|\n")
            await writer.drain()

    async def send_message(self, msg: str):
        if self.client_writer:
            self.client_writer.write(msg.encode("utf-8") + b"\n")
            await self.client_writer.drain()

    async def stop(self):
        if self.client_writer:
            self.client_writer.close()
            try:
                await self.client_writer.wait_closed()
            except Exception:
                pass
        if self.server:
            self.server.close()
            await self.server.wait_closed()


@pytest.mark.asyncio
async def test_radio_client_full_cycle():
    mock_server = MockFlexRadioServer()
    server_port = await mock_server.start()

    db = Database(DatabaseConfig(url="sqlite+aiosqlite:///:memory:"))
    await db.init_models()
    tracker = RadioStateTracker(db)

    radio_config = RadioConfig(
        host="127.0.0.1",
        port=server_port,
        reconnect_interval_sec=0.2,
        reconnect_max_backoff_sec=1.0,
        timeout_sec=2.0,
    )
    client = RadioClient(radio_config, tracker)

    try:
        await client.start()

        # Wait for connection
        for _ in range(20):
            if client.is_connected:
                break
            await asyncio.sleep(0.05)

        assert client.is_connected is True
        assert client.radio_version == "3.4.24.112"
        assert client.radio_handle == "01234567"

        # Mock radio events:
        # 1. Client connects
        await mock_server.send_message("S0|client 9999-8888 connected=1 ip=127.0.0.1 name=SmartSDR-Win station=HB9MOCK gui=1")
        await asyncio.sleep(0.05)
        assert len(tracker.active_sessions_by_uuid) == 1

        # 2. Slice configured to 40m
        await mock_server.send_message("S0|slice 0 RF_frequency=7.074000 mode=USB tx=1")
        await asyncio.sleep(0.05)

        # 3. PTT pressed
        await mock_server.send_message("S0|interlock state=TRANSMITTING source=SW")
        await asyncio.sleep(0.1)
        assert client.status_summary["is_transmitting"] is True

        # 4. PTT released
        await mock_server.send_message("S0|interlock state=READY source=")
        await asyncio.sleep(0.05)
        assert client.status_summary["is_transmitting"] is False

        # 5. Client disconnects
        await mock_server.send_message("S0|client 9999-8888 connected=0")
        await asyncio.sleep(0.05)
        assert len(tracker.active_sessions_by_uuid) == 0

        # Verify DB contents
        async for session in db.get_session():
            s_stmt = select(Session)
            s_res = await session.execute(s_stmt)
            sessions = s_res.scalars().all()
            assert len(sessions) == 1
            assert sessions[0].station == "HB9MOCK"
            assert sessions[0].is_active is False

            p_stmt = select(PttEvent)
            p_res = await session.execute(p_stmt)
            ptts = p_res.scalars().all()
            assert len(ptts) == 1
            assert ptts[0].frequency_hz == 7_074_000
            assert ptts[0].band == "40m"
            assert ptts[0].mode == "USB"
            assert ptts[0].duration_seconds > 0.05

    finally:
        await client.stop()
        await mock_server.stop()
        await db.close()
