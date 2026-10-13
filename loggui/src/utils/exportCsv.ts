/**
 * CSV Export utility for session data
 */

import type { SessionResponse } from '../types';
import { formatDateTime } from './dateUtils';

/**
 * Escapes CSV field value according to RFC 4180
 */
function escapeCsvValue(val: string | number | boolean | null | undefined): string {
  if (val === null || val === undefined) return '';
  const str = String(val);
  if (str.includes(';') || str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Exports sessions to a CSV file with UTF-8 BOM (for Excel compatibility)
 * and triggers a browser download.
 */
export function exportSessionsToCsv(
  sessions: SessionResponse[],
  filenamePrefix: string = 'flexradio_sessions'
): void {
  // Semicolon delimiter is standard for German Excel locales
  const delimiter = ';';

  const headers = [
    'ID',
    'Rufzeichen (Callsign)',
    'Operator / Name',
    'Station',
    'Client IP',
    'Client Handle',
    'Startzeit',
    'Endzeit',
    'Dauer (Sekunden)',
    'PTT Anzahl',
    'PTT Gesamtdauer (Sekunden)',
    'Status',
    'Trennugsgrund (Reason)',
  ];

  const rows = sessions.map((s) => [
    s.id,
    s.callsign,
    s.client_name || '',
    s.station || '',
    s.client_ip,
    s.client_handle || '',
    formatDateTime(s.start_time),
    s.end_time ? formatDateTime(s.end_time) : 'Aktiv',
    s.duration_seconds || 0,
    s.ptt_count,
    s.total_ptt_duration_seconds.toFixed(2),
    s.is_active ? 'Aktiv' : 'Beendet',
    s.disconnect_reason || '',
  ]);

  const csvContent = [
    headers.map(escapeCsvValue).join(delimiter),
    ...rows.map((row) => row.map(escapeCsvValue).join(delimiter)),
  ].join('\r\n');

  // Prepend UTF-8 BOM (Byte Order Mark: \uFEFF) so Excel displays German umlauts correctly
  const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const downloadLink = document.createElement('a');
  downloadLink.href = url;
  downloadLink.download = `${filenamePrefix}_${timestamp}.csv`;
  document.body.appendChild(downloadLink);
  downloadLink.click();
  document.body.removeChild(downloadLink);
  URL.revokeObjectURL(url);
}
