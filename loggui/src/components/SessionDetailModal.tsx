import React, { useEffect, useState } from 'react';
import type { SessionDetailResponse } from '../types';
import { fetchSessionDetails } from '../api';
import { formatDateTime, formatDuration, formatFrequency } from '../utils/dateUtils';

interface SessionDetailModalProps {
  sessionId: number;
  onClose: () => void;
}

export const SessionDetailModal: React.FC<SessionDetailModalProps> = ({ sessionId, onClose }) => {
  const [detail, setDetail] = useState<SessionDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isCurrent = true;
    fetchSessionDetails(sessionId)
      .then((data) => {
        if (isCurrent) {
          setDetail(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isCurrent) {
          setError(err instanceof Error ? err.message : 'Fehler beim Laden');
          setLoading(false);
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [sessionId]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">
            🔍 Session #{sessionId} Details {detail ? `(${detail.callsign})` : ''}
          </h2>
          <button className="btn-close" onClick={onClose} title="Schließen">
            ✖
          </button>
        </div>

        <div className="modal-body">
          {loading && <p className="text-muted">Lade Session-Details und PTT-Events...</p>}
          {error && <p className="text-danger">Fehler: {error}</p>}

          {detail && (
            <>
              {/* Meta information */}
              <div className="session-meta-grid">
                <div>
                  <strong>Rufzeichen:</strong> {detail.callsign}
                </div>
                <div>
                  <strong>Client Name:</strong> {detail.client_name || '-'}
                </div>
                <div>
                  <strong>Station:</strong> {detail.station || '-'}
                </div>
                <div>
                  <strong>Client IP:</strong> {detail.client_ip}
                </div>
                <div>
                  <strong>Start:</strong> {formatDateTime(detail.start_time)}
                </div>
                <div>
                  <strong>Ende:</strong>{' '}
                  {detail.end_time ? formatDateTime(detail.end_time) : 'Noch aktiv'}
                </div>
                <div>
                  <strong>Dauer:</strong> {formatDuration(detail.duration_seconds)}
                </div>
                <div>
                  <strong>PTT Gesamt:</strong> {detail.ptt_count} Events (
                  {formatDuration(detail.total_ptt_duration_seconds)})
                </div>
              </div>

              <h3 className="section-title">
                🎙️ Zugeordnete PTT Sende-Events ({detail.ptt_events.length})
              </h3>

              {detail.ptt_events.length === 0 ? (
                <p className="text-muted">In dieser Sitzung wurden keine TX-Events registriert.</p>
              ) : (
                <div className="table-responsive modal-table">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Startzeit</th>
                        <th>Endzeit</th>
                        <th>Dauer</th>
                        <th>Frequenz</th>
                        <th>Band</th>
                        <th>Mode</th>
                        <th>TX Slice</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.ptt_events.map((p, idx) => (
                        <tr key={p.id}>
                          <td>{idx + 1}</td>
                          <td>{formatDateTime(p.start_time)}</td>
                          <td>{formatDateTime(p.end_time)}</td>
                          <td className="font-bold">{p.duration_seconds.toFixed(2)}s</td>
                          <td>{formatFrequency(p.frequency_hz)}</td>
                          <td>
                            <span className="badge badge-band">{p.band}</span>
                          </td>
                          <td>{p.mode || 'Auto'}</td>
                          <td>{p.tx_slice_id !== null ? `Slice ${p.tx_slice_id}` : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Schließen
          </button>
        </div>
      </div>
    </div>
  );
};
