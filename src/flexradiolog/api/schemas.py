"""Pydantic schemas for the FlexRadioLog REST API."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RadioStatusResponse(BaseModel):
    """Current connection and monitoring status of the FlexRadio."""
    host: str
    port: int
    is_connected: bool
    connected_at: Optional[str] = None
    last_message_at: Optional[str] = None
    reconnect_count: int = 0
    radio_version: Optional[str] = None
    radio_handle: Optional[str] = None
    active_clients: int = 0
    is_transmitting: bool = False


class IpAllocationCreate(BaseModel):
    """Schema for creating or updating an IP-to-callsign allocation."""
    ip_address: str = Field(..., description="IPv4 or IPv6 address of the client")
    callsign: str = Field(..., description="Amateur radio callsign or operator identifier")
    operator_name: Optional[str] = Field(default="", description="Name of the radio operator")
    notes: Optional[str] = Field(default="", description="Optional remarks")


class IpAllocationResponse(BaseModel):
    """Schema for returning an IP allocation record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    ip_address: str
    callsign: str
    operator_name: Optional[str] = ""
    notes: Optional[str] = ""
    created_at: datetime
    updated_at: datetime


class PttEventResponse(BaseModel):
    """Schema for a single PTT transmission event."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: Optional[int]
    client_handle: Optional[str] = None
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    frequency_hz: int
    band: str
    mode: Optional[str] = ""
    tx_slice_id: Optional[int] = None


class SessionResponse(BaseModel):
    """Schema for a user connection session summary."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_uuid: str
    client_handle: Optional[str] = None
    client_ip: str
    callsign: str
    client_name: Optional[str] = ""
    station: Optional[str] = ""
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = 0
    is_active: bool
    disconnect_reason: Optional[str] = "ACTIVE"
    ptt_count: int = 0
    total_ptt_duration_seconds: float = 0.0


class SessionDetailResponse(SessionResponse):
    """Detailed session schema including associated PTT events."""
    ptt_events: List[PttEventResponse] = Field(default_factory=list)


class OperatorStats(BaseModel):
    """Summary statistics for an individual operator/callsign."""
    callsign: str
    session_count: int
    total_usage_seconds: int
    ptt_count: int
    total_ptt_duration_seconds: float


class BandStats(BaseModel):
    """Summary statistics for an amateur band."""
    band: str
    ptt_count: int
    total_ptt_duration_seconds: float


class StatsSummaryResponse(BaseModel):
    """Aggregated operational statistics."""
    total_sessions: int
    active_sessions: int
    total_usage_seconds: int
    total_ptt_count: int
    total_ptt_duration_seconds: float
    per_operator: List[OperatorStats] = Field(default_factory=list)
    per_band: List[BandStats] = Field(default_factory=list)
