import React from 'react';
import type { FilterParams, IpAllocationResponse, TimeRangePreset } from '../types';

interface FilterBarProps {
  filters: FilterParams;
  onFilterChange: (updated: Partial<FilterParams>) => void;
  knownCallsigns: string[];
  allocations: IpAllocationResponse[];
  onExportCsv: () => void;
  autoRefresh: boolean;
  onToggleAutoRefresh: (enabled: boolean) => void;
  totalFilteredCount: number;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  filters,
  onFilterChange,
  knownCallsigns,
  allocations,
  onExportCsv,
  autoRefresh,
  onToggleAutoRefresh,
  totalFilteredCount,
}) => {
  const presets: { id: TimeRangePreset; label: string; icon: string }[] = [
    { id: '24h', label: 'Letzte 24h', icon: '⏱️' },
    { id: 'current_week', label: 'Kalenderwoche', icon: '📅' },
    { id: 'current_month', label: 'Kalendermonat', icon: '🗓️' },
    { id: 'all', label: 'Gesamt / Alle', icon: '♾️' },
    { id: 'custom', label: 'Individuell', icon: '⚙️' },
  ];

  // Helper mapping callsign to operator name
  const getOpName = (call: string) => {
    const alloc = allocations.find((a) => a.callsign.toUpperCase() === call.toUpperCase());
    return alloc?.operator_name ? ` (${alloc.operator_name})` : '';
  };

  return (
    <section className="filter-bar">
      <div className="filter-row-top">
        {/* Preset Time Interval Buttons */}
        <div className="filter-group">
          <label className="filter-label">Zeitintervall:</label>
          <div className="preset-buttons">
            {presets.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`btn btn-preset ${filters.preset === p.id ? 'active' : ''}`}
                onClick={() => onFilterChange({ preset: p.id })}
              >
                <span className="preset-icon">{p.icon}</span>
                <span>{p.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* User / Callsign Selector */}
        <div className="filter-group">
          <label className="filter-label" htmlFor="callsign-select">
            Benutzer / Rufzeichen:
          </label>
          <select
            id="callsign-select"
            className="form-control select-callsign"
            value={filters.callsign || 'all'}
            onChange={(e) => onFilterChange({ callsign: e.target.value })}
          >
            <option value="all">Alle Benutzer (Gesamt)</option>
            {knownCallsigns.map((cs) => (
              <option key={cs} value={cs}>
                {cs} {getOpName(cs)}
              </option>
            ))}
          </select>
        </div>

        {/* Export & Auto-refresh */}
        <div className="filter-group filter-actions">
          <button
            type="button"
            className="btn btn-export"
            onClick={onExportCsv}
            disabled={totalFilteredCount === 0}
            title="Gefilterte Sessions als CSV-Datei herunterladen"
          >
            📥 CSV Export ({totalFilteredCount})
          </button>

          <label className="checkbox-label" title="Automatisches Neuladen alle 10 Sekunden">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => onToggleAutoRefresh(e.target.checked)}
            />
            <span>Auto-Refresh (10s)</span>
          </label>
        </div>
      </div>

      {/* Custom Date Window (Visible when 'custom' is selected) */}
      {filters.preset === 'custom' && (
        <div className="filter-row-custom">
          <div className="filter-input-date">
            <label htmlFor="custom-from">Von (Datum & Uhrzeit):</label>
            <input
              id="custom-from"
              type="datetime-local"
              className="form-control"
              value={filters.fromDate || ''}
              onChange={(e) => onFilterChange({ fromDate: e.target.value })}
            />
          </div>

          <div className="filter-input-date">
            <label htmlFor="custom-to">Bis (Datum & Uhrzeit):</label>
            <input
              id="custom-to"
              type="datetime-local"
              className="form-control"
              value={filters.toDate || ''}
              onChange={(e) => onFilterChange({ toDate: e.target.value })}
            />
          </div>

          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => onFilterChange({ fromDate: '', toDate: '' })}
          >
            Filter zurücksetzen
          </button>
        </div>
      )}
    </section>
  );
};
