"""Async TCP client for FlexRadio SmartSDR connection and message processing."""

import asyncio
from datetime import datetime
import logging
from typing import Optional
from flexradiolog.config import RadioConfig
from flexradiolog.db.models import utc_now
from flexradiolog.radio.parser import ProtocolParser
from flexradiolog.radio.tracker import RadioStateTracker

logger = logging.getLogger(__name__)


class RadioClient:
    """Manages persistent asynchronous TCP connection to FlexRadio 6400."""

    def __init__(self, config: RadioConfig, tracker: RadioStateTracker):
        self.config = config
        self.tracker = tracker
        self.is_connected: bool = False
        self.connected_at: Optional[datetime] = None
        self.last_message_at: Optional[datetime] = None
        self.reconnect_count: int = 0
        self.radio_version: Optional[str] = None
        self.radio_handle: Optional[str] = None

        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    @property
    def status_summary(self) -> dict:
        """Return dict summary of current radio connection status."""
        return {
            "host": self.config.host,
            "port": self.config.port,
            "is_connected": self.is_connected,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "reconnect_count": self.reconnect_count,
            "radio_version": self.radio_version,
            "radio_handle": self.radio_handle,
            "active_clients": len(self.tracker.active_sessions_by_uuid),
            "is_transmitting": self.tracker.current_ptt is not None,
        }

    async def start(self) -> None:
        """Start the background connection worker."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="flexradio-client-loop")
        logger.info("Radio client background service started.")

    async def stop(self) -> None:
        """Gracefully stop background connection worker."""
        self._running = False
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        self.is_connected = False
        await self.tracker.on_radio_disconnected("SERVICE_STOPPED")
        logger.info("Radio client background service stopped.")

    async def _run_loop(self) -> None:
        """Continuous reconnection and monitoring loop."""
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(
                    "Connection error to FlexRadio (%s:%d): %s",
                    self.config.host, self.config.port, e
                )
                self.is_connected = False
                await self.tracker.on_radio_disconnected("SOCKET_ERROR")

            if not self._running:
                break

            # Exponential backoff calculation
            self.reconnect_count += 1
            backoff = min(
                self.config.reconnect_interval_sec * (1.5 ** min(self.reconnect_count - 1, 6)),
                self.config.reconnect_max_backoff_sec,
            )
            logger.info("Reconnecting to FlexRadio in %.1f seconds (attempt %d)...", backoff, self.reconnect_count)
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                break

    async def _connect_and_listen(self) -> None:
        """Establish connection, subscribe to status updates, and read stream."""
        logger.info("Connecting to FlexRadio at %s:%d ...", self.config.host, self.config.port)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.config.host, self.config.port),
            timeout=self.config.timeout_sec,
        )
        self._writer = writer
        self.is_connected = True
        self.connected_at = utc_now()
        self.reconnect_count = 0
        logger.info("Connected successfully to FlexRadio at %s:%d.", self.config.host, self.config.port)

        # Refresh IP allocation cache on new connection
        await self.tracker.reload_ip_cache()

        # Send subscriptions
        commands = [
            b"C1|sub client all\n",
            b"C2|sub interlock all\n",
            b"C3|sub slice all\n",
        ]
        for cmd in commands:
            writer.write(cmd)
        await writer.drain()

        # Listen for messages
        while self._running:
            line_bytes = await reader.readline()
            if not line_bytes:
                logger.warning("Connection closed by FlexRadio (EOF).")
                break

            self.last_message_at = utc_now()
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            parsed = ProtocolParser.parse_line(line)
            if not parsed:
                continue

            if parsed.msg_type == "V":
                self.radio_version = parsed.attributes.get("version")
            elif parsed.msg_type == "H":
                self.radio_handle = parsed.handle

            await self.tracker.process_message(parsed)

        self.is_connected = False
        await self.tracker.on_radio_disconnected("CONNECTION_CLOSED")
