// hooks/useAdminStats.ts
// Custom hook that polls /api/admin/stats every 30 seconds.
// Merges recent_errors onto each tester row and computes alert state.
// Only called from admin.tsx — never loaded for regular users.

import { useState, useEffect, useCallback, useRef } from "react";
import { API_BASE, APP_PIN } from "../constants/config";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface TesterError {
  error_type:  string;
  error_msg:   string;
  intent:      string;
  created_at:  string;
}

export interface Tester {
  id:            string;
  email:         string;
  display_name:  string;
  request_count: number;
  token_count:   number;
  request_limit: number;
  is_paused:     boolean;
  last_intent:   string;
  last_pulse:    string;   // ISO timestamp
  joined_at:     string;
  recent_errors: TesterError[];
  has_alert:     boolean;
  // Derived client-side
  pulse_mins_ago: number;
  usage_pct:      number;
  status:         "active" | "idle" | "error" | "paused";
}

export interface AdminTotals {
  total_requests: number;
  total_tokens:   number;
  active_today:   number;
  alert_count:    number;
}

export interface AdminStats {
  testers: Tester[];
  totals:  AdminTotals;
}

// ── Derived fields ─────────────────────────────────────────────────────────────

function deriveFields(t: any): Tester {
  const now     = Date.now();
  const pulse   = t.last_pulse ? new Date(t.last_pulse).getTime() : 0;
  const mins    = pulse ? Math.round((now - pulse) / 60000) : 9999;
  const limit   = Math.max(t.request_limit || 50, 1);
  const used    = t.request_count || 0;
  const pct     = Math.round((used / limit) * 100);
  const hasErr  = (t.recent_errors || []).length > 0;

  let status: Tester["status"] = "idle";
  if (t.is_paused)    status = "paused";
  else if (hasErr)    status = "error";
  else if (mins < 30) status = "active";

  return {
    ...t,
    pulse_mins_ago: mins,
    usage_pct:      pct,
    status,
    recent_errors:  t.recent_errors || [],
    has_alert:      t.has_alert || hasErr || pct >= 84,
  };
}

// ── Hook ──────────────────────────────────────────────────────────────────────

const POLL_MS = 30_000; // 30-second polling interval

export function useAdminStats() {
  const [stats,   setStats]   = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url = `${API_BASE}/api/admin/stats?admin_pin=${encodeURIComponent(APP_PIN)}`;
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `HTTP ${res.status}`);
      }
      const json = await res.json();
      const derived: AdminStats = {
        testers: (json.testers || []).map(deriveFields),
        totals:  json.totals  || { total_requests:0, total_tokens:0, active_today:0, alert_count:0 },
      };
      setStats(derived);
      setLastFetched(new Date());
    } catch (e: any) {
      setError(e.message || "Network error");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch + polling
  useEffect(() => {
    fetch_();
    timerRef.current = setInterval(fetch_, POLL_MS);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [fetch_]);

  // Admin actions — each calls the backend and refreshes immediately

  const bumpLimit = useCallback(async (email: string): Promise<void> => {
    await fetch(`${API_BASE}/api/admin/bump`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ email, admin_pin: APP_PIN }),
    });
    await fetch_();
  }, [fetch_]);

  const setPaused = useCallback(async (email: string, paused: boolean): Promise<void> => {
    await fetch(`${API_BASE}/api/admin/pause`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ email, paused, admin_pin: APP_PIN }),
    });
    await fetch_();
  }, [fetch_]);

  return {
    stats,
    loading,
    error,
    lastFetched,
    refetch: fetch_,
    bumpLimit,
    setPaused,
  };
}
