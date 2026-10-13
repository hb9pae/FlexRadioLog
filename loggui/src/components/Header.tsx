import React, { useState } from 'react';
import type { RadioStatusResponse } from '../types';
import { getEffectiveApiUrl, setApiUrlOverride } from '../api';

interface HeaderProps {
  status: RadioStatusResponse | null;
  isLoading: boolean;
  onRefresh: () => void;
}

export const Header: React.FC<HeaderProps> = ({ status, isLoading, onRefresh }) => {
  const [showConfig, setShowConfig] = useState(false);
  const [apiUrl, setApiUrl] = useState(getEffectiveApiUrl());

  const handleSaveApiUrl = (e: React.FormEvent) => {
    e.preventDefault();
    setApiUrlOverride(apiUrl.trim() || null);
    setShowConfig(false);
    onRefresh();
  };

  const isConnected = status?.is_connected ?? false;
  const isTx = status?.is_transmitting ?? false;

  return (
    <header className="header">
      <div className="header-brand">
        <div className="brand-logo">
          <span className="radio-icon">📻</span>
        </div>
        <div>
          <h1 className="header-title">FlexRadio 6400 Log & Monitor</h1>
          <p className="header-subtitle">
            Stationsbelegung & Sendedaten-Auswertung (LogGui)
          </p>
        </div>
      </div>

      <div className="header-actions">
        {/* Status Indicators */}
        <div className="status-badges">
          <div
            className={`status-badge ${isConnected ? 'status-connected' : 'status-disconnected'}`}
            title={isConnected ? `Verbunden mit ${status?.host}:${status?.port}` : 'Keine Verbindung zum FlexRadio'}
          >
            <span className="status-dot"></span>
            <span>{isConnected ? 'Radio Online' : 'Radio Offline'}</span>
          </div>

          {isConnected && isTx && (
            <div className="status-badge status-transmitting animate-pulse" title="Sender ist derzeit aktiv!">
              <span className="status-dot"></span>
              <span>TX AKTIV</span>
            </div>
          )}

          {isConnected && status?.active_clients !== undefined && (
            <div className="status-badge status-clients" title="Aktive SmartSDR/GUI Clients">
              <span className="client-count">{status.active_clients}</span>
              <span>{status.active_clients === 1 ? 'Client' : 'Clients'}</span>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <button
          className="btn btn-secondary btn-icon"
          onClick={() => setShowConfig(!showConfig)}
          title="API-Server Konfiguration"
        >
          ⚙️
        </button>

        <button
          className={`btn btn-primary ${isLoading ? 'btn-loading' : ''}`}
          onClick={onRefresh}
          disabled={isLoading}
          title="Daten manuell aktualisieren"
        >
          {isLoading ? 'Lädt...' : '🔄 Aktualisieren'}
        </button>
      </div>

      {showConfig && (
        <div className="config-popover">
          <form onSubmit={handleSaveApiUrl} className="config-form">
            <label htmlFor="api-url-input">
              <strong>Backend API-URL:</strong>
            </label>
            <input
              id="api-url-input"
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="z.B. http://192.168.84.24:8000/api oder /api"
              className="form-control"
            />
            <div className="config-actions">
              <button type="submit" className="btn btn-primary btn-sm">
                Speichern & Neu laden
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setApiUrlOverride(null);
                  setApiUrl(getEffectiveApiUrl());
                  setShowConfig(false);
                  onRefresh();
                }}
              >
                Standard zurücksetzen
              </button>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => setShowConfig(false)}
              >
                Abbrechen
              </button>
            </div>
          </form>
        </div>
      )}
    </header>
  );
};
