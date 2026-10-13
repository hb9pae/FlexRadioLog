"""Async TCP client for FlexRadio SmartSDR connection and message processing."""

import asyncio
from datetime import datetime
import logging
import re
import socket
from typing import Optional
from flexradiolog.config import RadioConfig
from flexradiolog.db.models import utc_now
from flexradiolog.radio.parser import ProtocolParser
from flexradiolog.radio.tracker import RadioStateTracker

logger = logging.getLogger(__name__)


class DiscoveryProtocol(asyncio.DatagramProtocol):
    """Protocol for receiving UDP discovery broadcasts from FlexRadio."""

    def __init__(self, on_datagram):
        self.on_datagram = on_datagram

    def datagram_received(self, data: bytes, addr: tuple):
        self.on_datagram(data, addr)

    def error_received(self, exc):
        logger.debug("Discovery UDP error: %s", exc)


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
        self._udp_transport: Optional[asyncio.DatagramTransport] = None
        self._udp_task: Optional[asyncio.Task] = None

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
        """Start the background connection worker and UDP discovery listener."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="flexradio-client-loop")
        self._udp_task = asyncio.create_task(self._run_udp_discovery(), name="flexradio-udp-discovery")
        logger.info("Radio client background service started.")

    async def stop(self) -> None:
        """Gracefully stop background connection worker and UDP discovery."""
        self._running = False
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None

        if self._udp_transport:
            try:
                self._udp_transport.close()
            except Exception:
                pass
            self._udp_transport = None

        if self._udp_task:
            self._udp_task.cancel()
            try:
                await self._udp_task
            except asyncio.CancelledError:
                pass
            self._udp_task = None

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

    async def _run_udp_discovery(self) -> None:
        """Listen for UDP discovery broadcasts on port 4992 to discover client IP addresses."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass
            sock.bind(("", 4992))
            sock.setblocking(False)

            loop = asyncio.get_running_loop()
            transport, _ = await loop.create_datagram_endpoint(
                lambda: DiscoveryProtocol(self._on_udp_packet),
                sock=sock,
            )
            self._udp_transport = transport
            logger.info("UDP discovery listener active on port 4992.")
        except Exception as e:
            logger.info("UDP discovery listener unavailable on port 4992 (%s). Relying on TCP stream.", e)
            return

        try:
            while self._running:
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        finally:
            if self._udp_transport:
                self._udp_transport.close()
                self._udp_transport = None

    def _on_udp_packet(self, data: bytes, addr: tuple) -> None:
        """Process incoming UDP discovery packet from FlexRadio."""
        # Check if packet originates from configured radio host
        if addr[0] != self.config.host:
            return

        idx = data.find(b"discovery_protocol_version")
        if idx < 0:
            return

        text = data[idx:].decode("utf-8", errors="replace")
        pattern = re.compile(r"([A-Za-z0-9_]+)=([^\s]+)")
        kv = dict(pattern.findall(text))

        handles_raw = kv.get("gui_client_handles", "")
        ips_raw = kv.get("gui_client_ips", "")
        progs_raw = kv.get("gui_client_programs", "")
        stations_raw = kv.get("gui_client_stations", "")
        inuse_ip = kv.get("inuse_ip") or None
        status = kv.get("status")

        handles = [h.strip() for h in handles_raw.split(",") if h.strip()]
        ips = [ip.strip() for ip in ips_raw.split(",") if ip.strip()]
        programs = [p.strip() for p in progs_raw.split(",") if p.strip()]
        stations = [s.strip() for s in stations_raw.split(",") if s.strip()]

        asyncio.create_task(
            self.tracker.update_discovered_clients(
                handles=handles,
                ips=ips,
                programs=programs,
                stations=stations,
                inuse_ip=inuse_ip,
                status=status,
            )
        )

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
            b"C2|sub radio all\n",
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
