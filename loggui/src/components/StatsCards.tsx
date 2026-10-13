import React from 'react';
import type { SessionResponse } from '../types';
import { formatDuration } from '../utils/dateUtils';

interface StatsCardsProps {
  sessions: SessionResponse[];
  activeSessionsCount: number;
}

export const StatsCards: React.FC<StatsCardsProps> = ({ sessions, activeSessionsCount }) => {
  const totalSessions = sessions.length;

  // Sum total session usage duration
  const totalUsageSeconds = sessions.reduce((acc, s) => acc + (s.duration_seconds || 0), 0);

  // Sum total PTT events and duration
  const totalPttCount = sessions.reduce((acc, s) => acc + (s.ptt_count || 0), 0);
  const totalPttDuration = sessions.reduce(
    (acc, s) => acc + (s.total_ptt_duration_seconds || 0),
    0
  );

  // Calculate duty cycle / transmit percentage
  const dutyCyclePercent =
    totalUsageSeconds > 0
      ? ((totalPttDuration / totalUsageSeconds) * 100).toFixed(1)
      : '0.0';

  // Distinct operators in filtered set
  const uniqueOperators = new Set(sessions.map((s) => s.callsign.toUpperCase())).size;

  return (
    <section className="stats-cards-grid">
      <div className="card stat-card">
        <div className="stat-icon">📊</div>
        <div className="stat-content">
          <div className="stat-value">{totalSessions}</div>
          <div className="stat-label">Sitzungen (Sessions)</div>
          <div className="stat-sub">
            {activeSessionsCount > 0 ? (
              <span className="text-success font-bold">🟢 {activeSessionsCount} aktiv</span>
            ) : (
              <span>Keine aktiven Verbindungen</span>
            )}
          </div>
        </div>
      </div>

      <div className="card stat-card">
        <div className="stat-icon">🕒</div>
        <div className="stat-content">
          <div className="stat-value">{formatDuration(totalUsageSeconds)}</div>
          <div className="stat-label">Gesamte Belegungszeit</div>
          <div className="stat-sub">{totalUsageSeconds.toLocaleString('de-DE')} Sekunden</div>
        </div>
      </div>

      <div className="card stat-card">
        <div className="stat-icon">🎙️</div>
        <div className="stat-content">
          <div className="stat-value">{formatDuration(totalPttDuration)}</div>
          <div className="stat-label">Sendezeit (PTT TX)</div>
          <div className="stat-sub">{totalPttCount} Sende-Events</div>
        </div>
      </div>

      <div className="card stat-card">
        <div className="stat-icon">⚡</div>
        <div className="stat-content">
          <div className="stat-value">{dutyCyclePercent}%</div>
          <div className="stat-label">TX Duty Cycle</div>
          <div className="stat-sub">Verhältnis Senden zu Empfang</div>
        </div>
      </div>

      <div className="card stat-card">
        <div className="stat-icon">👥</div>
        <div className="stat-content">
          <div className="stat-value">{uniqueOperators}</div>
          <div className="stat-label">Aktive Benutzer</div>
          <div className="stat-sub">Im gewählten Zeitraum</div>
        </div>
      </div>
    </section>
  );
};
