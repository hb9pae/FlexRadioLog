import React, { useState, useMemo } from 'react';
import type { SessionResponse } from '../types';
import { formatDateTime, formatDuration } from '../utils/dateUtils';

interface SessionsTableProps {
  sessions: SessionResponse[];
  onSelectSession: (sessionId: number) => void;
  isLoading: boolean;
}

type SortField = 'id' | 'start_time' | 'callsign' | 'duration_seconds' | 'ptt_count' | 'total_ptt_duration_seconds';
type SortDirection = 'asc' | 'desc';

export const SessionsTable: React.FC<SessionsTableProps> = ({
  sessions,
  onSelectSession,
  isLoading,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState<SortField>('start_time');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  // Filter by local text search (IP, callsign, station, client_name)
  const filtered = useMemo(() => {
    if (!searchTerm.trim()) return sessions;
    const term = searchTerm.toLowerCase();
    return sessions.filter(
      (s) =>
        s.callsign.toLowerCase().includes(term) ||
        (s.client_name && s.client_name.toLowerCase().includes(term)) ||
        (s.station && s.station.toLowerCase().includes(term)) ||
        s.client_ip.toLowerCase().includes(term) ||
        (s.client_handle && s.client_handle.toLowerCase().includes(term))
    );
  }, [sessions, searchTerm]);

  // Sort
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let valA: string | number = a[sortField] ?? 0;
      let valB: string | number = b[sortField] ?? 0;

      if (sortField === 'start_time') {
        valA = new Date(a.start_time).getTime();
        valB = new Date(b.start_time).getTime();
      }

      if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
      if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }, [filtered, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const getSortIndicator = (field: SortField) => {
    if (sortField !== field) return '↕️';
    return sortDirection === 'asc' ? '↑' : '↓';
  };

  return (
    <section className="card table-card">
      <div className="table-header-row">
        <div>
          <h2 className="table-title">
            📋 Sitzungsprotokoll ({sorted.length} {sorted.length === 1 ? 'Eintrag' : 'Einträge'})
          </h2>
          <p className="table-subtitle">
            Klicken Sie auf eine Zeile oder die Detail-Schaltfläche für die Liste der PTT-Übertragungen.
          </p>
        </div>

        <div className="table-search">
          <input
            type="text"
            className="form-control"
            placeholder="🔍 In Tabelle suchen (Callsign, IP, Name)..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      <div className="table-responsive">
        <table className="table sessions-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('id')} className="sortable-th">
                ID {getSortIndicator('id')}
              </th>
              <th onClick={() => handleSort('callsign')} className="sortable-th">
                Rufzeichen / Operator {getSortIndicator('callsign')}
              </th>
              <th>Station / IP</th>
              <th onClick={() => handleSort('start_time')} className="sortable-th">
                Startzeit {getSortIndicator('start_time')}
              </th>
              <th>Endzeit</th>
              <th onClick={() => handleSort('duration_seconds')} className="sortable-th">
                Dauer {getSortIndicator('duration_seconds')}
              </th>
              <th onClick={() => handleSort('ptt_count')} className="sortable-th">
                PTT Events {getSortIndicator('ptt_count')}
              </th>
              <th onClick={() => handleSort('total_ptt_duration_seconds')} className="sortable-th">
                PTT Sendedauer {getSortIndicator('total_ptt_duration_seconds')}
              </th>
              <th>Status</th>
              <th>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && sessions.length === 0 ? (
              <tr>
                <td colSpan={10} className="text-center py-4">
                  ⏳ Lade Sitzungsdaten...
                </td>
              </tr>
            ) : sorted.length === 0 ? (
              <tr>
                <td colSpan={10} className="text-center py-4 text-muted">
                  Keine Sitzungen im ausgewählten Filterbereich gefunden.
                </td>
              </tr>
            ) : (
              sorted.map((s) => (
                <tr
                  key={s.id}
                  className={`session-row ${s.is_active ? 'row-active' : ''}`}
                  onClick={() => onSelectSession(s.id)}
                >
                  <td className="font-mono">#{s.id}</td>
                  <td>
                    <div className="operator-cell">
                      <strong className="callsign-badge">{s.callsign}</strong>
                      {s.client_name && <span className="client-name">{s.client_name}</span>}
                    </div>
                  </td>
                  <td>
                    <div className="station-cell">
                      <span>{s.station || '-'}</span>
                      <span className="ip-badge font-mono">{s.client_ip}</span>
                    </div>
                  </td>
                  <td>{formatDateTime(s.start_time)}</td>
                  <td>
                    {s.end_time ? (
                      formatDateTime(s.end_time)
                    ) : (
                      <span className="badge badge-success">Aktiv</span>
                    )}
                  </td>
                  <td className="font-bold">{formatDuration(s.duration_seconds)}</td>
                  <td>
                    <span className="ptt-count-badge">{s.ptt_count}</span>
                  </td>
                  <td>
                    <span className="ptt-duration-badge">
                      {formatDuration(s.total_ptt_duration_seconds)}
                    </span>
                  </td>
                  <td>
                    {s.is_active ? (
                      <span className="badge badge-success">Online</span>
                    ) : (
                      <span
                        className="badge badge-secondary"
                        title={s.disconnect_reason || 'Beendet'}
                      >
                        Beendet
                      </span>
                    )}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className="btn btn-outline btn-sm"
                      onClick={() => onSelectSession(s.id)}
                      title="PTT-Details anzeigen"
                    >
                      Details
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};
