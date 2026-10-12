"""Radio state and session tracking."""

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Dict, Optional
from sqlalchemy import select
from flexradiolog.db.database import Database
from flexradiolog.db.models import (
    IpAllocation,
    PttEvent,
    Session,
    calculate_duration_float,
    calculate_duration_seconds,
    utc_now,
)
from flexradiolog.radio.bands import frequency_to_band
from flexradiolog.radio.parser import ParsedMessage, parse_frequency_hz

logger = logging.getLogger(__name__)


@dataclass
class ActiveSessionInfo:
    """In-memory representation of an active client session."""
    db_id: int
    client_uuid: str
    client_handle: Optional[str]
    client_ip: str
    callsign: str
    client_name: str
    station: str
    start_time: datetime
    gui: bool = True


@dataclass
class SliceInfo:
    """In-memory representation of a radio slice receiver."""
    slice_id: int
    frequency_hz: int = 14_074_000
    mode: str = "USB"
    is_tx: bool = False
    client_handle: Optional[str] = None


@dataclass
class ActivePttInfo:
    """In-memory tracking of an ongoing PTT transmission."""
    start_time: datetime
    tx_client_handle: Optional[str]
    frequency_hz: int
    band: str
    mode: str
    tx_slice_id: Optional[int]
    session_id: Optional[int]


class RadioStateTracker:
    """Tracks sessions, slices, and PTT events from parsed radio messages."""

    def __init__(self, db: Database):
        self.db = db
        # Active sessions keyed by client_uuid
        self.active_sessions_by_uuid: Dict[str, ActiveSessionInfo] = {}
        # Slices keyed by slice_id
        self.slices: Dict[int, SliceInfo] = {}
        # Active PTT state
        self.current_ptt: Optional[ActivePttInfo] = None
        # IP to callsign cache
        self.ip_cache: Dict[str, str] = {}

    async def reload_ip_cache(self) -> None:
        """Load or refresh the IP-to-callsign allocation cache from database."""
        async for session in self.db.get_session():
            stmt = select(IpAllocation)
            result = await session.execute(stmt)
            allocs = result.scalars().all()
            self.ip_cache = {a.ip_address: a.callsign for a in allocs}
            logger.debug("IP allocation cache loaded with %d entries.", len(self.ip_cache))

    async def resolve_callsign(self, ip_address: str, fallback_station: str) -> str:
        """Resolve callsign from IP cache, with fallback to station name or IP."""
        if not self.ip_cache:
            await self.reload_ip_cache()

        if ip_address in self.ip_cache:
            return self.ip_cache[ip_address]

        if fallback_station and fallback_station.strip():
            return fallback_station.strip()

        return ip_address or "UNKNOWN"

    def get_session_by_handle(self, handle: Optional[str]) -> Optional[ActiveSessionInfo]:
        """Find active session by client handle."""
        if not handle:
            return None
        norm_handle = handle.lower()
        for s in self.active_sessions_by_uuid.values():
            if s.client_handle and s.client_handle.lower() == norm_handle:
                return s
        return None

    def get_tx_slice(self) -> Optional[SliceInfo]:
        """Find current TX slice, or return slice 0 as default if present."""
        for s in self.slices.values():
            if s.is_tx:
                return s
        if 0 in self.slices:
            return self.slices[0]
        if self.slices:
            return next(iter(self.slices.values()))
        return None

    async def handle_client_message(self, msg: ParsedMessage) -> None:
        """Process 'client' status updates (connected=1 / connected=0)."""
        uuid = msg.object_id
        if not uuid:
            return

        connected = msg.attributes.get("connected")
        if connected == "1":
            ip = msg.attributes.get("ip", "")
            station = msg.attributes.get("station", "")
            name = msg.attributes.get("name", "")
            gui = msg.attributes.get("gui", "1") == "1"
            handle = msg.attributes.get("handle") or msg.handle

            callsign = await self.resolve_callsign(ip, station)
            now = utc_now()

            # Create session in DB
            async for db_session in self.db.get_session():
                new_session = Session(
                    client_uuid=uuid,
                    client_handle=handle,
                    client_ip=ip,
                    callsign=callsign,
                    client_name=name,
                    station=station,
                    start_time=now,
                    is_active=True,
                )
                db_session.add(new_session)
                await db_session.commit()
                await db_session.refresh(new_session)

                self.active_sessions_by_uuid[uuid] = ActiveSessionInfo(
                    db_id=new_session.id,
                    client_uuid=uuid,
                    client_handle=handle,
                    client_ip=ip,
                    callsign=callsign,
                    client_name=name,
                    station=station,
                    start_time=now,
                    gui=gui,
                )
                logger.info(
                    "User connected: %s (IP: %s, App: %s, UUID: %s, DB-ID: %d)",
                    callsign, ip, name, uuid, new_session.id
                )

        elif connected == "0":
            if uuid in self.active_sessions_by_uuid:
                info = self.active_sessions_by_uuid.pop(uuid)
                now = utc_now()
                duration = calculate_duration_seconds(info.start_time, now)

                async for db_session in self.db.get_session():
                    stmt = select(Session).where(Session.id == info.db_id)
                    res = await db_session.execute(stmt)
                    record = res.scalar_one_or_none()
                    if record:
                        record.is_active = False
                        record.end_time = now
                        record.duration_seconds = duration
                        record.disconnect_reason = "LOGOUT"
                        await db_session.commit()

                logger.info(
                    "User disconnected: %s (Duration: %d s, UUID: %s)",
                    info.callsign, duration, uuid
                )

    async def handle_slice_message(self, msg: ParsedMessage) -> None:
        """Process 'slice' status updates (frequency, mode, tx flag)."""
        try:
            slice_id = int(msg.object_id) if msg.object_id is not None else 0
        except ValueError:
            return

        if slice_id not in self.slices:
            self.slices[slice_id] = SliceInfo(slice_id=slice_id)

        sl = self.slices[slice_id]
        if "rf_frequency" in msg.attributes:
            sl.frequency_hz = parse_frequency_hz(msg.attributes["rf_frequency"])
        if "mode" in msg.attributes:
            sl.mode = msg.attributes["mode"].upper()
        if "tx" in msg.attributes:
            sl.is_tx = (msg.attributes["tx"] == "1")
        if "client_handle" in msg.attributes:
            sl.client_handle = msg.attributes["client_handle"]

    async def handle_interlock_message(self, msg: ParsedMessage) -> None:
        """Process 'interlock' status updates (PTT state)."""
        state = msg.attributes.get("state", "").upper()
        tx_handle = msg.attributes.get("tx_client_handle")

        is_transmitting = (state in ("TRANSMITTING", "PTT_REQUESTED"))

        # Transition to TRANSMITTING
        if is_transmitting and self.current_ptt is None:
            now = utc_now()
            tx_slice = self.get_tx_slice()

            freq = tx_slice.frequency_hz if tx_slice else 14_074_000
            mode = tx_slice.mode if tx_slice else "USB"
            slice_id = tx_slice.slice_id if tx_slice else 0
            band = frequency_to_band(freq)

            # Match session
            session_info = self.get_session_by_handle(tx_handle)
            if not session_info and self.active_sessions_by_uuid:
                # Fallback to the first active GUI session
                for s in self.active_sessions_by_uuid.values():
                    if s.gui:
                        session_info = s
                        break
                if not session_info:
                    session_info = next(iter(self.active_sessions_by_uuid.values()))

            session_id = session_info.db_id if session_info else None
            self.current_ptt = ActivePttInfo(
                start_time=now,
                tx_client_handle=tx_handle,
                frequency_hz=freq,
                band=band,
                mode=mode,
                tx_slice_id=slice_id,
                session_id=session_id,
            )
            logger.info(
                "PTT KEY DOWN: %s on %d Hz (%s, %s), Session: %s",
                session_info.callsign if session_info else "Unknown",
                freq, band, mode, session_id
            )

        # Transition back to READY
        elif state == "READY" and self.current_ptt is not None:
            now = utc_now()
            ptt = self.current_ptt
            self.current_ptt = None

            duration = calculate_duration_float(ptt.start_time, now)

            # Persist PTT event
            async for db_session in self.db.get_session():
                event = PttEvent(
                    session_id=ptt.session_id,
                    client_handle=ptt.tx_client_handle,
                    start_time=ptt.start_time,
                    end_time=now,
                    duration_seconds=duration,
                    frequency_hz=ptt.frequency_hz,
                    band=ptt.band,
                    mode=ptt.mode,
                    tx_slice_id=ptt.tx_slice_id,
                )
                db_session.add(event)
                await db_session.commit()

            logger.info(
                "PTT KEY UP: Duration: %.2f s, Freq: %d Hz (%s)",
                duration, ptt.frequency_hz, ptt.band
            )

    async def process_message(self, msg: ParsedMessage) -> None:
        """Route parsed message to the appropriate handler."""
        if msg.msg_type == "S":
            if msg.object_type == "client":
                await self.handle_client_message(msg)
            elif msg.object_type == "slice":
                await self.handle_slice_message(msg)
            elif msg.object_type == "interlock":
                await self.handle_interlock_message(msg)

    async def on_radio_disconnected(self, reason: str = "RADIO_DISCONNECTED") -> None:
        """Handle loss of connection to the radio."""
        now = utc_now()

        # Finalize any ongoing PTT event
        if self.current_ptt:
            ptt = self.current_ptt
            self.current_ptt = None
            duration = calculate_duration_float(ptt.start_time, now)
            async for db_session in self.db.get_session():
                event = PttEvent(
                    session_id=ptt.session_id,
                    client_handle=ptt.tx_client_handle,
                    start_time=ptt.start_time,
                    end_time=now,
                    duration_seconds=duration,
                    frequency_hz=ptt.frequency_hz,
                    band=ptt.band,
                    mode=ptt.mode,
                    tx_slice_id=ptt.tx_slice_id,
                )
                db_session.add(event)
                await db_session.commit()

        # Close all active sessions in DB
        if self.active_sessions_by_uuid:
            async for db_session in self.db.get_session():
                for info in self.active_sessions_by_uuid.values():
                    stmt = select(Session).where(Session.id == info.db_id)
                    res = await db_session.execute(stmt)
                    record = res.scalar_one_or_none()
                    if record and record.is_active:
                        record.is_active = False
                        record.end_time = now
                        record.duration_seconds = calculate_duration_seconds(info.start_time, now)
                        record.disconnect_reason = reason
                await db_session.commit()
            self.active_sessions_by_uuid.clear()

        self.slices.clear()
        logger.info("Cleared radio tracker state due to disconnect: %s", reason)
