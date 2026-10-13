import React from 'react';
import type { StatsSummaryResponse } from '../types';
import { formatDuration } from '../utils/dateUtils';

interface BandDistributionProps {
  summary: StatsSummaryResponse | null;
}

export const BandDistribution: React.FC<BandDistributionProps> = ({ summary }) => {
  if (!summary) return null;

  const bands = summary.per_band || [];
  const operators = summary.per_operator || [];

  const maxBandPtt = Math.max(...bands.map((b) => b.ptt_count), 1);
  const maxOpDuration = Math.max(...operators.map((o) => o.total_usage_seconds), 1);

  return (
    <section className="distribution-grid">
      {/* Band Auswertung */}
      <div className="card distribution-card">
        <h3 className="card-title">📡 Sendeaktivität nach Band (PTT Events)</h3>
        {bands.length === 0 ? (
          <p className="text-muted">Keine Sendedaten vorhanden.</p>
        ) : (
          <div className="bars-list">
            {bands.map((b) => {
              const pct = Math.round((b.ptt_count / maxBandPtt) * 100);
              return (
                <div key={b.band} className="bar-item">
                  <div className="bar-labels">
                    <span className="bar-name">{b.band || 'Unbekannt'}</span>
                    <span className="bar-value">
                      {b.ptt_count} TX ({formatDuration(b.total_ptt_duration_seconds)})
                    </span>
                  </div>
                  <div className="bar-track">
                    <div
                      className="bar-fill bar-fill-band"
                      style={{ width: `${Math.max(pct, 4)}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Operator Belegung */}
      <div className="card distribution-card">
        <h3 className="card-title">👤 Belegung nach Benutzer (Top Operators)</h3>
        {operators.length === 0 ? (
          <p className="text-muted">Keine Benutzerdaten vorhanden.</p>
        ) : (
          <div className="bars-list">
            {operators.slice(0, 7).map((op) => {
              const pct = Math.round((op.total_usage_seconds / maxOpDuration) * 100);
              return (
                <div key={op.callsign} className="bar-item">
                  <div className="bar-labels">
                    <span className="bar-name">{op.callsign}</span>
                    <span className="bar-value">
                      {formatDuration(op.total_usage_seconds)} ({op.session_count} Sessions)
                    </span>
                  </div>
                  <div className="bar-track">
                    <div
                      className="bar-fill bar-fill-operator"
                      style={{ width: `${Math.max(pct, 4)}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
};
