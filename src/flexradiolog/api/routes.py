"""API route definitions for FlexRadioLog."""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from flexradiolog.api.schemas import (
    BandStats,
    IpAllocationCreate,
    IpAllocationResponse,
    OperatorStats,
    PttEventResponse,
    RadioStatusResponse,
    SessionDetailResponse,
    SessionResponse,
    StatsSummaryResponse,
)
from flexradiolog.db.database import Database
from flexradiolog.db.models import IpAllocation, PttEvent, Session, utc_now
from flexradiolog.radio.client import RadioClient
from flexradiolog.radio.tracker import RadioStateTracker

router = APIRouter(prefix="/api", tags=["Monitoring & Logging"])


def get_radio_client(request: Request) -> RadioClient:
    """Extract RadioClient instance from application state."""
    return request.app.state.radio_client


def get_radio_tracker(request: Request) -> RadioStateTracker:
    """Extract RadioStateTracker instance from application state."""
    return request.app.state.tracker


def get_database(request: Request) -> Database:
    """Extract Database instance from application state."""
    return request.app.state.db


@router.get("/status", response_model=RadioStatusResponse, summary="Get current radio status")
async def get_status(client: RadioClient = Depends(get_radio_client)):
    """Return live status of the FlexRadio connection, active sessions, and PTT state."""
    return client.status_summary


# --- IP Allocation Management ---


@router.get("/allocations", response_model=List[IpAllocationResponse], summary="List IP allocations")
async def list_allocations(db: Database = Depends(get_database)):
    """Return all configured IP to callsign mappings."""
    async for session in db.get_session():
        stmt = select(IpAllocation).order_by(IpAllocation.callsign)
        res = await session.execute(stmt)
        return res.scalars().all()


@router.post("/allocations", response_model=IpAllocationResponse, summary="Create or update IP allocation")
async def set_allocation(
    payload: IpAllocationCreate,
    db: Database = Depends(get_database),
    tracker: RadioStateTracker = Depends(get_radio_tracker),
):
    """Register or update an IP address allocation to a callsign."""
    async for session in db.get_session():
        stmt = select(IpAllocation).where(IpAllocation.ip_address == payload.ip_address)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.callsign = payload.callsign
            existing.operator_name = payload.operator_name or ""
            existing.notes = payload.notes or ""
            existing.updated_at = utc_now()
            target = existing
        else:
            target = IpAllocation(
                ip_address=payload.ip_address,
                callsign=payload.callsign,
                operator_name=payload.operator_name or "",
                notes=payload.notes or "",
            )
            session.add(target)

        await session.commit()
        await session.refresh(target)

        # Update cache in tracker immediately
        await tracker.reload_ip_cache()
        return target


@router.delete("/allocations/{allocation_id}", summary="Delete an IP allocation")
async def delete_allocation(
    allocation_id: int,
    db: Database = Depends(get_database),
    tracker: RadioStateTracker = Depends(get_radio_tracker),
):
    """Remove an IP address allocation."""
    async for session in db.get_session():
        stmt = delete(IpAllocation).where(IpAllocation.id == allocation_id)
        result = await session.execute(stmt)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Allocation not found")
        await session.commit()
        await tracker.reload_ip_cache()
        return {"status": "deleted", "id": allocation_id}


# --- Session Monitoring ---


@router.get("/sessions", response_model=List[SessionResponse], summary="List user sessions")
async def list_sessions(
    callsign: Optional[str] = Query(None, description="Filter by callsign"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    from_date: Optional[datetime] = Query(None, description="Start date (ISO-8601)"),
    to_date: Optional[datetime] = Query(None, description="End date (ISO-8601)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Database = Depends(get_database),
):
    """Retrieve logged user sessions with pagination and filtering."""
    async for db_session in db.get_session():
        stmt = select(Session).order_by(Session.start_time.desc())

        if callsign:
            stmt = stmt.where(Session.callsign.ilike(f"%{callsign}%"))
        if is_active is not None:
            stmt = stmt.where(Session.is_active == is_active)
        if from_date:
            stmt = stmt.where(Session.start_time >= from_date)
        if to_date:
            stmt = stmt.where(Session.start_time <= to_date)

        stmt = stmt.limit(limit).offset(offset)
        result = await db_session.execute(stmt)
        sessions = result.scalars().all()

        output: List[SessionResponse] = []
        for s in sessions:
            # Aggregate PTT counts and duration for this session
            ptt_stmt = select(
                func.count(PttEvent.id).label("count"),
                func.coalesce(func.sum(PttEvent.duration_seconds), 0.0).label("total_duration"),
            ).where(PttEvent.session_id == s.id)
            ptt_res = await db_session.execute(ptt_stmt)
            count, dur = ptt_res.one()

            output.append(
                SessionResponse(
                    id=s.id,
                    client_uuid=s.client_uuid,
                    client_handle=s.client_handle,
                    client_ip=s.client_ip,
                    callsign=s.callsign,
                    client_name=s.client_name,
                    station=s.station,
                    start_time=s.start_time,
                    end_time=s.end_time,
                    duration_seconds=s.duration_seconds or 0,
                    is_active=s.is_active,
                    disconnect_reason=s.disconnect_reason,
                    ptt_count=count,
                    total_ptt_duration_seconds=round(dur, 2),
                )
            )

        return output


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse, summary="Get session details")
async def get_session(session_id: int, db: Database = Depends(get_database)):
    """Retrieve full details of a specific session including all associated PTT events."""
    async for db_session in db.get_session():
        stmt = select(Session).where(Session.id == session_id)
        res = await db_session.execute(stmt)
        s = res.scalar_one_or_none()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")

        ptt_stmt = select(PttEvent).where(PttEvent.session_id == session_id).order_by(PttEvent.start_time.asc())
        ptt_res = await db_session.execute(ptt_stmt)
        ptts = ptt_res.scalars().all()

        total_dur = sum(p.duration_seconds for p in ptts)

        return SessionDetailResponse(
            id=s.id,
            client_uuid=s.client_uuid,
            client_handle=s.client_handle,
            client_ip=s.client_ip,
            callsign=s.callsign,
            client_name=s.client_name,
            station=s.station,
            start_time=s.start_time,
            end_time=s.end_time,
            duration_seconds=s.duration_seconds or 0,
            is_active=s.is_active,
            disconnect_reason=s.disconnect_reason,
            ptt_count=len(ptts),
            total_ptt_duration_seconds=round(total_dur, 2),
            ptt_events=[PttEventResponse.model_validate(p) for p in ptts],
        )


@router.get("/sessions/{session_id}/ptt", response_model=List[PttEventResponse], summary="Get PTT events for session")
async def get_session_ptt(session_id: int, db: Database = Depends(get_database)):
    """Retrieve all PTT events for a specific session."""
    async for db_session in db.get_session():
        stmt = select(PttEvent).where(PttEvent.session_id == session_id).order_by(PttEvent.start_time.asc())
        res = await db_session.execute(stmt)
        return res.scalars().all()


# --- PTT Event Querying ---


@router.get("/ptt", response_model=List[PttEventResponse], summary="List PTT events")
async def list_ptt_events(
    callsign: Optional[str] = Query(None, description="Filter by operator callsign"),
    band: Optional[str] = Query(None, description="Filter by amateur band (e.g., 20m)"),
    mode: Optional[str] = Query(None, description="Filter by mode (e.g., USB, CW)"),
    from_date: Optional[datetime] = Query(None, description="Start date (ISO-8601)"),
    to_date: Optional[datetime] = Query(None, description="End date (ISO-8601)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Database = Depends(get_database),
):
    """Retrieve logged PTT transmissions with filters."""
    async for db_session in db.get_session():
        stmt = select(PttEvent).order_by(PttEvent.start_time.desc())

        if callsign:
            stmt = stmt.join(Session, PttEvent.session_id == Session.id).where(Session.callsign.ilike(f"%{callsign}%"))
        if band:
            stmt = stmt.where(PttEvent.band.ilike(band))
        if mode:
            stmt = stmt.where(PttEvent.mode.ilike(mode))
        if from_date:
            stmt = stmt.where(PttEvent.start_time >= from_date)
        if to_date:
            stmt = stmt.where(PttEvent.start_time <= to_date)

        stmt = stmt.limit(limit).offset(offset)
        res = await db_session.execute(stmt)
        return res.scalars().all()


# --- Statistical Summaries ---


@router.get("/stats/summary", response_model=StatsSummaryResponse, summary="Aggregated statistics")
async def get_stats_summary(db: Database = Depends(get_database)):
    """Provide aggregated operational statistics for dashboards and reports."""
    async for db_session in db.get_session():
        # Overall session counts
        total_sessions = (await db_session.execute(select(func.count(Session.id)))).scalar_one() or 0
        active_sessions = (await db_session.execute(select(func.count(Session.id)).where(Session.is_active == True))).scalar_one() or 0  # noqa: E712
        total_usage_seconds = (await db_session.execute(select(func.coalesce(func.sum(Session.duration_seconds), 0)))).scalar_one() or 0

        # Overall PTT metrics
        total_ptt_count = (await db_session.execute(select(func.count(PttEvent.id)))).scalar_one() or 0
        total_ptt_duration = (await db_session.execute(select(func.coalesce(func.sum(PttEvent.duration_seconds), 0.0)))).scalar_one() or 0.0

        # Per operator stats
        op_stmt = (
            select(
                Session.callsign,
                func.count(func.distinct(Session.id)).label("sess_count"),
                func.coalesce(func.sum(Session.duration_seconds), 0).label("usage_sec"),
            )
            .group_by(Session.callsign)
            .order_by(func.sum(Session.duration_seconds).desc())
        )
        op_res = await db_session.execute(op_stmt)

        per_op: List[OperatorStats] = []
        for call, s_cnt, u_sec in op_res.all():
            ptt_for_op_stmt = (
                select(
                    func.count(PttEvent.id),
                    func.coalesce(func.sum(PttEvent.duration_seconds), 0.0),
                )
                .join(Session, PttEvent.session_id == Session.id)
                .where(Session.callsign == call)
            )
            p_cnt, p_dur = (await db_session.execute(ptt_for_op_stmt)).one()
            per_op.append(
                OperatorStats(
                    callsign=call,
                    session_count=s_cnt,
                    total_usage_seconds=int(u_sec),
                    ptt_count=p_cnt,
                    total_ptt_duration_seconds=round(p_dur, 2),
                )
            )

        # Per band stats
        band_stmt = (
            select(
                PttEvent.band,
                func.count(PttEvent.id).label("ptt_cnt"),
                func.coalesce(func.sum(PttEvent.duration_seconds), 0.0).label("ptt_dur"),
            )
            .group_by(PttEvent.band)
            .order_by(func.count(PttEvent.id).desc())
        )
        band_res = await db_session.execute(band_stmt)
        per_band = [
            BandStats(band=b, ptt_count=cnt, total_ptt_duration_seconds=round(dur, 2))
            for b, cnt, dur in band_res.all()
        ]

        return StatsSummaryResponse(
            total_sessions=total_sessions,
            active_sessions=active_sessions,
            total_usage_seconds=int(total_usage_seconds),
            total_ptt_count=total_ptt_count,
            total_ptt_duration_seconds=round(total_ptt_duration, 2),
            per_operator=per_op,
            per_band=per_band,
        )
