/**
 * API client service for FlexRadioLog backend
 */

import type {
  IpAllocationResponse,
  RadioStatusResponse,
  SessionDetailResponse,
  SessionResponse,
  StatsSummaryResponse,
} from './types';

// In development or when reverse-proxied, '/api' can be used.
// When running standalone on port 8080 without reverse proxy, fall back to hostname:8000.
function getBaseUrl(): string {
  // Check if an explicit override is stored in localStorage
  const saved = localStorage.getItem('flexradiolog_api_url');
  if (saved) {
    return saved.replace(/\/+$/, '');
  }

  // If page is served on port 8080 (the default RPI LogGui port), API is typically at port 8000
  if (typeof window !== 'undefined' && window.location) {
    const { protocol, hostname, port } = window.location;
    if (port === '8080') {
      return `${protocol}//${hostname}:8000/api`;
    }
  }

  return '/api';
}

export function setApiUrlOverride(url: string | null): void {
  if (url) {
    localStorage.setItem('flexradiolog_api_url', url);
  } else {
    localStorage.removeItem('flexradiolog_api_url');
  }
}

export function getEffectiveApiUrl(): string {
  return getBaseUrl();
}

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const base = getBaseUrl();
  const url = `${base}${endpoint.startsWith('/') ? endpoint : '/' + endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore json parse errors
    }
    throw new Error(`API Fehler (${response.status}): ${errorDetail}`);
  }

  return response.json();
}

export async function fetchRadioStatus(): Promise<RadioStatusResponse> {
  return fetchJson<RadioStatusResponse>('/status');
}

export async function fetchStatsSummary(): Promise<StatsSummaryResponse> {
  return fetchJson<StatsSummaryResponse>('/stats/summary');
}

export async function fetchIpAllocations(): Promise<IpAllocationResponse[]> {
  return fetchJson<IpAllocationResponse[]>('/allocations');
}

export interface FetchSessionsParams {
  callsign?: string;
  fromDate?: string;
  toDate?: string;
  isActive?: boolean;
  limit?: number;
  offset?: number;
}

export async function fetchSessions(params: FetchSessionsParams = {}): Promise<SessionResponse[]> {
  const query = new URLSearchParams();

  if (params.callsign && params.callsign.trim() && params.callsign !== 'all') {
    query.append('callsign', params.callsign.trim());
  }
  if (params.fromDate) {
    query.append('from_date', params.fromDate);
  }
  if (params.toDate) {
    query.append('to_date', params.toDate);
  }
  if (params.isActive !== undefined) {
    query.append('is_active', String(params.isActive));
  }
  query.append('limit', String(params.limit ?? 500));
  if (params.offset) {
    query.append('offset', String(params.offset));
  }

  const queryString = query.toString();
  return fetchJson<SessionResponse[]>(`/sessions${queryString ? '?' + queryString : ''}`);
}

export async function fetchSessionDetails(sessionId: number): Promise<SessionDetailResponse> {
  return fetchJson<SessionDetailResponse>(`/sessions/${sessionId}`);
}
