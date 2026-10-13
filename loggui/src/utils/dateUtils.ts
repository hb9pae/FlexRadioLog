/**
 * Date and time helper functions for LogGui
 */

/**
 * Formats seconds into human-readable duration (e.g. "2h 15m 30s" or "45s")
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || isNaN(seconds) || seconds <= 0) {
    return '0s';
  }

  const sec = Math.round(seconds);
  const hours = Math.floor(sec / 3600);
  const minutes = Math.floor((sec % 3600) / 60);
  const remainingSec = sec % 60;

  const parts: string[] = [];
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0 || hours > 0) parts.push(`${minutes}m`);
  parts.push(`${remainingSec}s`);

  return parts.join(' ');
}

/**
 * Formats ISO datetime string to German localized format: "DD.MM.YYYY HH:mm:ss"
 */
export function formatDateTime(isoString: string | null | undefined): string {
  if (!isoString) return '-';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return isoString;
  }
}

/**
 * Formats frequency in Hz to MHz string (e.g. 14200000 -> "14.200000 MHz")
 */
export function formatFrequency(hz: number | null | undefined): string {
  if (!hz) return '-';
  return (hz / 1000000).toFixed(6) + ' MHz';
}

/**
 * Calculates start and end ISO strings based on preset.
 */
export function getPresetDateRange(preset: string): { fromDate?: string; toDate?: string } {
  const now = new Date();

  switch (preset) {
    case '24h': {
      const from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      return {
        fromDate: from.toISOString(),
        toDate: now.toISOString(),
      };
    }
    case 'current_week': {
      // Monday as first day of calendar week (ISO 8601)
      const day = now.getDay();
      const diffToMonday = (day + 6) % 7; // Sunday (0) becomes 6, Monday (1) becomes 0
      const startOfWeek = new Date(now);
      startOfWeek.setDate(now.getDate() - diffToMonday);
      startOfWeek.setHours(0, 0, 0, 0);

      return {
        fromDate: startOfWeek.toISOString(),
        toDate: now.toISOString(),
      };
    }
    case 'current_month': {
      // 1st of current month 00:00:00
      const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0, 0);
      return {
        fromDate: startOfMonth.toISOString(),
        toDate: now.toISOString(),
      };
    }
    case 'last_7_days': {
      const from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      return {
        fromDate: from.toISOString(),
        toDate: now.toISOString(),
      };
    }
    case 'all':
    default:
      return {};
  }
}

/**
 * Format a Date to datetime-local input string YYYY-MM-DDTHH:mm
 */
export function toInputDateTime(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  const year = d.getFullYear();
  const month = pad(d.getMonth() + 1);
  const day = pad(d.getDate());
  const hours = pad(d.getHours());
  const minutes = pad(d.getMinutes());
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}
