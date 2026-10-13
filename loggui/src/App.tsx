import { useCallback, useEffect, useMemo, useState } from 'react';
import type {
  FilterParams,
  IpAllocationResponse,
  RadioStatusResponse,
  SessionResponse,
  StatsSummaryResponse,
} from './types';
import {
  fetchIpAllocations,
  fetchRadioStatus,
  fetchSessions,
  fetchStatsSummary,
} from './api';
import { getPresetDateRange } from './utils/dateUtils';
import { exportSessionsToCsv } from './utils/exportCsv';
import { Header } from './components/Header';
import { FilterBar } from './components/FilterBar';
import { StatsCards } from './components/StatsCards';
import { BandDistribution } from './components/BandDistribution';
import { SessionsTable } from './components/SessionsTable';
import { SessionDetailModal } from './components/SessionDetailModal';
import './App.css';

export function App() {
  // Application Data States
  const [radioStatus, setRadioStatus] = useState<RadioStatusResponse | null>(null);
  const [statsSummary, setStatsSummary] = useState<StatsSummaryResponse | null>(null);
  const [allocations, setAllocations] = useState<IpAllocationResponse[]>([]);
  const [sessions, setSessions] = useState<SessionResponse[]>([]);

  // UI & Loading States
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);

  // Filter State (Default preset: 24h as requested in requirements)
  const [filters, setFilters] = useState<FilterParams>({
    preset: '24h',
    callsign: 'all',
  });

  // Calculate actual date boundaries for fetching
  const activeDateRange = useMemo(() => {
    if (filters.preset === 'custom') {
      return {
        fromDate: filters.fromDate ? new Date(filters.fromDate).toISOString() : undefined,
        toDate: filters.toDate ? new Date(filters.toDate).toISOString() : undefined,
      };
    }
    return getPresetDateRange(filters.preset);
  }, [filters.preset, filters.fromDate, filters.toDate]);

  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Load all required data
  useEffect(() => {
    let isCurrent = true;

    async function fetchData() {
      try {
        const [statusRes, summaryRes, allocRes, sessionsRes] = await Promise.all([
          fetchRadioStatus().catch((err) => {
            console.warn('Status fetch error:', err);
            return null;
          }),
          fetchStatsSummary().catch((err) => {
            console.warn('Summary fetch error:', err);
            return null;
          }),
          fetchIpAllocations().catch((err) => {
            console.warn('Allocations fetch error:', err);
            return [];
          }),
          fetchSessions({
            callsign: filters.callsign,
            fromDate: activeDateRange.fromDate,
            toDate: activeDateRange.toDate,
            limit: 500,
          }),
        ]);

        if (!isCurrent) return;
        if (statusRes) setRadioStatus(statusRes);
        if (summaryRes) setStatsSummary(summaryRes);
        if (allocRes) setAllocations(allocRes);
        setSessions(sessionsRes);
        setErrorMessage(null);
      } catch (err) {
        if (!isCurrent) return;
        setErrorMessage(
          err instanceof Error
            ? err.message
            : 'Verbindungsfehler beim Abrufen der Daten vom FlexRadio-Server.'
        );
      } finally {
        if (isCurrent) {
          setIsLoading(false);
        }
      }
    }

    void fetchData();

    return () => {
      isCurrent = false;
    };
  }, [filters.callsign, activeDateRange, refreshTrigger]);

  const handleManualRefresh = useCallback(() => {
    setIsLoading(true);
    setRefreshTrigger((prev) => prev + 1);
  }, []);

  // Auto-refresh interval (10 seconds)
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      setRefreshTrigger((prev) => prev + 1);
    }, 10000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  // Aggregate known callsigns from allocations, summary, and current sessions
  const knownCallsigns = useMemo(() => {
    const set = new Set<string>();
    allocations.forEach((a) => {
      if (a.callsign) set.add(a.callsign);
    });
    if (statsSummary?.per_operator) {
      statsSummary.per_operator.forEach((o) => {
        if (o.callsign) set.add(o.callsign);
      });
    }
    sessions.forEach((s) => {
      if (s.callsign) set.add(s.callsign);
    });
    return Array.from(set).sort();
  }, [allocations, statsSummary, sessions]);

  // Handle filter changes
  const handleFilterChange = (updated: Partial<FilterParams>) => {
    setFilters((prev) => ({ ...prev, ...updated }));
  };

  // CSV export handler
  const handleExportCsv = () => {
    const prefix = `flexradio_${filters.preset}_${filters.callsign || 'all'}`;
    exportSessionsToCsv(sessions, prefix);
  };

  const activeSessionsCount = useMemo(() => {
    return sessions.filter((s) => s.is_active).length;
  }, [sessions]);

  return (
    <div className="app-container">
      <Header
        status={radioStatus}
        isLoading={isLoading}
        onRefresh={handleManualRefresh}
      />

      <main className="main-content">
        {errorMessage && (
          <div className="alert alert-error">
            <span className="alert-icon">⚠️</span>
            <div className="alert-body">
              <strong>Verbindungshinweis:</strong> {errorMessage}
              <div className="alert-help">
                Stellen Sie sicher, dass der FlexRadioLog Backend-Dienst läuft (z.B. Port 8000).
                Sie können die API-URL über das ⚙️ Zahnrad-Symbol oben rechts anpassen.
              </div>
            </div>
            <button
              className="btn btn-sm btn-outline"
              onClick={handleManualRefresh}
            >
              Erneut versuchen
            </button>
          </div>
        )}

        {/* Filter controls */}
        <FilterBar
          filters={filters}
          onFilterChange={handleFilterChange}
          knownCallsigns={knownCallsigns}
          allocations={allocations}
          onExportCsv={handleExportCsv}
          autoRefresh={autoRefresh}
          onToggleAutoRefresh={setAutoRefresh}
          totalFilteredCount={sessions.length}
        />

        {/* Dynamic Metric Cards */}
        <StatsCards
          sessions={sessions}
          activeSessionsCount={activeSessionsCount}
        />

        {/* Band and Operator Distribution Charts */}
        <BandDistribution summary={statsSummary} />

        {/* Detailed Session Table */}
        <SessionsTable
          sessions={sessions}
          onSelectSession={setSelectedSessionId}
          isLoading={isLoading}
        />
      </main>

      <footer className="footer">
        <p>
          FlexRadioLog &bull; FlexRadio 6400 Stationsauswertung &bull; Ausgeführt auf Raspberry Pi
        </p>
      </footer>

      {/* Detail Modal */}
      {selectedSessionId !== null && (
        <SessionDetailModal
          sessionId={selectedSessionId}
          onClose={() => setSelectedSessionId(null)}
        />
      )}
    </div>
  );
}

export default App;
