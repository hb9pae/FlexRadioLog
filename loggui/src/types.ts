/**
 * TypeScript type definitions for FlexRadioLog API and LogGui
 */

export interface RadioStatusResponse {
  host: string;
  port: number;
  is_connected: boolean;
  connected_at: string | null;
  last_message_at: string | null;
  reconnect_count: number;
  radio_version: string | null;
  radio_handle: string | null;
  active_clients: number;
  is_transmitting: boolean;
}

export interface IpAllocationResponse {
  id: number;
  ip_address: string;
  callsign: string;
  operator_name?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface PttEventResponse {
  id: number;
  session_id: number | null;
  client_handle: string | null;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  frequency_hz: number;
  band: string;
  mode: string;
  tx_slice_id: number | null;
}

export interface SessionResponse {
  id: number;
  client_uuid: string;
  client_handle: string | null;
  client_ip: string;
  callsign: string;
  client_name: string;
  station: string;
  start_time: string;
  end_time: string | null;
  duration_seconds: number;
  is_active: boolean;
  disconnect_reason: string | null;
  ptt_count: number;
  total_ptt_duration_seconds: number;
}

export interface SessionDetailResponse extends SessionResponse {
  ptt_events: PttEventResponse[];
}

export interface OperatorStats {
  callsign: string;
  session_count: number;
  total_usage_seconds: number;
  ptt_count: number;
  total_ptt_duration_seconds: number;
}

export interface BandStats {
  band: string;
  ptt_count: number;
  total_ptt_duration_seconds: number;
}

export interface StatsSummaryResponse {
  total_sessions: number;
  active_sessions: number;
  total_usage_seconds: number;
  total_ptt_count: number;
  total_ptt_duration_seconds: number;
  per_operator: OperatorStats[];
  per_band: BandStats[];
}

export type TimeRangePreset =
  | '24h'
  | 'current_week'
  | 'current_month'
  | 'last_7_days'
  | 'all'
  | 'custom';

export interface FilterParams {
  preset: TimeRangePreset;
  fromDate?: string; // ISO string or YYYY-MM-DDTHH:mm
  toDate?: string;   // ISO string or YYYY-MM-DDTHH:mm
  callsign?: string; // empty string or 'all' for all users
}
