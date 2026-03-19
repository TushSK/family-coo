// app/(tabs)/admin.tsx  —  Mission Control · Admin Dashboard
// Hidden from the tab bar for non-admin users.
// Entry: long-press the app logo on the Briefing screen → router.push("/(tabs)/admin")
// Guard: redirects non-admin USER_IDs immediately on mount.

import React, { useState, useCallback, useEffect } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  SafeAreaView, ActivityIndicator, Platform, Dimensions,
  Modal, Alert, RefreshControl,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useFocusEffect } from "expo-router";
import { C, R, S, USER_ID } from "../constants/config";  
import { useAdminStats, Tester, TesterError } from "../hooks/useAdminStats";

// ── Constants ─────────────────────────────────────────────────────────────────

const ADMIN_EMAILS = ["tushar.khandare@gmail.com"];
const MAX_W  = 820;
const hp = () => Platform.OS === "web"
  ? Math.max(16, (Dimensions.get("window").width - MAX_W) / 2)
  : 16;

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtPulse(mins: number): string {
  if (mins < 1)    return "just now";
  if (mins < 60)   return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
  return `${Math.floor(mins / 1440)}d ago`;
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function fmtCost(tokens: number): string {
  // claude-sonnet-4: $3/1M input + $15/1M output — blended ~$6/1M for estimates
  return `$${((tokens / 1_000_000) * 6).toFixed(3)}`;
}

function barColor(pct: number): string {
  if (pct >= 90) return C.red;
  if (pct >= 70) return C.amber;
  return C.green;
}

function statusColor(status: Tester["status"]): string {
  switch (status) {
    case "active":  return C.green;
    case "error":   return C.red;
    case "idle":    return C.amber;
    case "paused":  return C.ink3;
  }
}

function statusLabel(t: Tester): string {
  if (t.is_paused) return "Paused";
  switch (t.status) {
    case "active": return "Active";
    case "error":  return "Error";
    case "idle":   return "Idle";
    default:       return "Unknown";
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function HealthCard({ label, value, sub, alert = false }: {
  label: string; value: string | number; sub: string; alert?: boolean;
}) {
  return (
    <View style={[st.hsCard, alert && st.hsCardAlert]}>
      <Text style={[st.hsLabel, alert && { color: C.red }]}>{label}</Text>
      <Text style={[st.hsVal,   alert && { color: C.red }]}>{value}</Text>
      <Text style={[st.hsSub,   alert && { color: C.red }]}>{sub}</Text>
    </View>
  );
}

function ErrorBanner({ err }: { err: TesterError }) {
  return (
    <View style={st.errBanner}>
      <View style={st.errIcon}>
        <Ionicons name="warning-outline" size={12} color={C.red} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={st.errType}>{err.error_type}</Text>
        <Text style={st.errMsg} numberOfLines={2}>{err.error_msg}</Text>
        <Text style={st.errTime}>
          {err.intent ? `While: ${err.intent.slice(0, 50)}  ·  ` : ""}
          {new Date(err.created_at).toLocaleTimeString("en-US", {
            hour: "numeric", minute: "2-digit",
          })}
        </Text>
      </View>
    </View>
  );
}

function TesterCard({ tester, onBump, onPause, onDetail }: {
  tester:   Tester;
  onBump:   () => void;
  onPause:  () => void;
  onDetail: () => void;
}) {
  const pct  = tester.usage_pct;
  const bc   = barColor(pct);
  const near = pct >= 84 && !tester.is_paused;

  const initials = (tester.display_name || tester.email)
    .split(/[\s@.]+/)
    .slice(0, 2)
    .map((w: string) => w[0]?.toUpperCase() || "")
    .join("");

  return (
    <View style={[
      st.tCard,
      tester.status === "error"  && st.tCardError,
      tester.is_paused           && st.tCardPaused,
    ]}>
      {/* Header */}
      <View style={st.tHeader}>
        <View style={st.avatar}>
          <Text style={st.avatarText}>{initials}</Text>
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={st.tName} numberOfLines={1}>{tester.display_name || tester.email}</Text>
          <Text style={st.tEmail} numberOfLines={1}>{tester.email}</Text>
        </View>
        <View style={{ alignItems: "flex-end", gap: 3 }}>
          <View style={st.statusRow}>
            <View style={[st.dot, { backgroundColor: statusColor(tester.status) }]} />
            <Text style={st.statusText}>{statusLabel(tester)}</Text>
          </View>
        </View>
      </View>

      {/* Recent errors */}
      {tester.recent_errors.slice(0, 2).map((e, i) => (
        <ErrorBanner key={i} err={e} />
      ))}

      {/* Near-limit warning */}
      {near && tester.recent_errors.length === 0 && (
        <View style={st.nearBanner}>
          <Ionicons name="alert-circle-outline" size={13} color={C.amber} />
          <Text style={st.nearText}>
            Near limit — {tester.request_count}/{tester.request_limit} used. Bump to extend.
          </Text>
        </View>
      )}

      {/* Usage bar */}
      <View style={st.usageSection}>
        <View style={st.usageRow}>
          <Text style={st.usageLabel}>REQUESTS</Text>
          <Text style={st.usageNums}>
            {tester.request_count} / {tester.request_limit}
          </Text>
        </View>
        <View style={st.barBg}>
          <View style={[st.barFill, {
            width: `${Math.min(pct, 100)}%` as any,
            backgroundColor: bc,
          }]} />
        </View>
        <View style={st.tokensRow}>
          <View style={st.tokenBadge}>
            <Text style={st.tokenBadgeText}>{fmtTokens(tester.token_count)} tokens</Text>
          </View>
          <View style={st.tokenBadge}>
            <Text style={st.tokenBadgeText}>{fmtCost(tester.token_count)} est.</Text>
          </View>
          <Text style={st.usagePct}>{pct}%</Text>
        </View>
      </View>

      {/* Meta grid */}
      <View style={st.metaGrid}>
        <View style={st.metaCell}>
          <Text style={st.metaLabel}>LAST PULSE</Text>
          <Text style={st.metaVal}>{fmtPulse(tester.pulse_mins_ago)}</Text>
        </View>
        <View style={st.metaCell}>
          <Text style={st.metaLabel}>LAST INTENT</Text>
          <Text style={st.metaVal} numberOfLines={1}>
            {tester.last_intent || "—"}
          </Text>
        </View>
      </View>

      {/* Actions */}
      <View style={st.actRow}>
        <TouchableOpacity style={[st.actBtn, st.actBump]} onPress={onBump}>
          <Ionicons name="add-circle-outline" size={13} color="#185fa5" />
          <Text style={[st.actText, { color: "#185fa5" }]}>+25 Limit</Text>
        </TouchableOpacity>

        {tester.is_paused ? (
          <TouchableOpacity style={[st.actBtn, st.actUnpause]} onPress={onPause}>
            <Ionicons name="play-circle-outline" size={13} color={C.green} />
            <Text style={[st.actText, { color: C.green }]}>Unpause</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={[st.actBtn, st.actPause]} onPress={onPause}>
            <Ionicons name="pause-circle-outline" size={13} color={C.red} />
            <Text style={[st.actText, { color: C.red }]}>Pause</Text>
          </TouchableOpacity>
        )}

        <TouchableOpacity style={[st.actBtn, st.actDetail]} onPress={onDetail}>
          <Ionicons name="document-text-outline" size={13} color={C.ink2} />
          <Text style={[st.actText, { color: C.ink2 }]}>Logs</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

export default function AdminScreen() {
  const router = useRouter();

  // Route guard — non-admin users get bounced immediately
  useEffect(() => {
    if (!ADMIN_EMAILS.includes(USER_ID)) {
      router.replace("/(tabs)/index");
    }
  }, []);

  const { stats, loading, error, lastFetched, refetch, bumpLimit, setPaused }
    = useAdminStats();

  const [filter, setFilter] = useState<"all" | "active" | "alerts">("all");
  const [pauseModal, setPauseModal] = useState<{ tester: Tester; action: "pause" | "unpause" } | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [bumpConfirm, setBumpConfirm] = useState<string | null>(null); // email

  // Refetch on focus
  useFocusEffect(useCallback(() => { refetch(); }, []));

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  }, [refetch]);

  // Filtered tester list
  const visibleTesters = (stats?.testers || []).filter(t => {
    if (filter === "active") return !t.is_paused && t.status === "active";
    if (filter === "alerts") return t.has_alert;
    return true;
  });

  const totals = stats?.totals;

  async function handleBump(t: Tester) {
    try {
      await bumpLimit(t.email);
      setBumpConfirm(t.email);
      setTimeout(() => setBumpConfirm(null), 2500);
    } catch {
      Alert.alert("Error", "Could not bump limit. Check your connection.");
    }
  }

  function handlePausePress(t: Tester) {
    setPauseModal({ tester: t, action: t.is_paused ? "unpause" : "pause" });
  }

  async function confirmPause() {
    if (!pauseModal) return;
    try {
      await setPaused(pauseModal.tester.email, pauseModal.action === "pause");
    } catch {
      Alert.alert("Error", "Could not update tester status.");
    }
    setPauseModal(null);
  }

  const ph = hp();

  return (
    <SafeAreaView style={st.safe}>
      {/* Header */}
      <View style={[st.header, { paddingHorizontal: ph }]}>
        <View>
          <Text style={st.headerSub}>ADMIN</Text>
          <Text style={st.headerTitle}>Mission Control</Text>
        </View>
        <View style={st.headerRight}>
          {lastFetched && (
            <Text style={st.syncTime}>
              {lastFetched.toLocaleTimeString("en-US", {
                hour: "2-digit", minute: "2-digit", second: "2-digit",
              })}
            </Text>
          )}
          <View style={st.liveDot} />
          {loading && <ActivityIndicator size="small" color={C.acc} style={{ marginLeft: 8 }} />}
        </View>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingHorizontal: ph, paddingBottom: 32 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Error state */}
        {error && (
          <View style={st.errState}>
            <Ionicons name="cloud-offline-outline" size={20} color={C.red} />
            <Text style={st.errStateText}>{error}</Text>
          </View>
        )}

        {/* Health strip */}
        <View style={st.healthStrip}>
          <HealthCard
            label="AI REQUESTS"
            value={totals?.total_requests ?? "—"}
            sub={totals ? `${fmtTokens(totals.total_tokens)} tokens · ${fmtCost(totals.total_tokens)}` : "loading…"}
          />
          <HealthCard
            label="ACTIVE TODAY"
            value={totals?.active_today ?? "—"}
            sub={`of ${stats?.testers.length ?? "—"} testers`}
          />
          <HealthCard
            label="SYSTEM ALERTS"
            value={totals?.alert_count ?? "—"}
            sub={totals?.alert_count
              ? `${stats?.testers.filter(t => t.recent_errors.length > 0).length ?? 0} error · ${stats?.testers.filter(t => !t.recent_errors.length && t.has_alert).length ?? 0} near limit`
              : "All systems healthy"
            }
            alert={(totals?.alert_count ?? 0) > 0}
          />
        </View>

        {/* Filter pills */}
        <View style={st.filterRow}>
          <Text style={st.sectionLabel}>TESTER ROSTER</Text>
          <View style={st.filterPills}>
            {(["all","active","alerts"] as const).map(f => (
              <TouchableOpacity
                key={f}
                style={[st.filterPill, filter === f && st.filterPillOn]}
                onPress={() => setFilter(f)}
              >
                <Text style={[st.filterPillText, filter === f && st.filterPillTextOn]}>
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Tester cards */}
        {!stats && !loading && !error && (
          <View style={st.emptyState}>
            <Text style={st.emptyText}>
              Run the Supabase SQL setup first, then seed tester emails.
            </Text>
          </View>
        )}

        {visibleTesters.map(t => (
          <View key={t.email}>
            <TesterCard
              tester={t}
              onBump={() => handleBump(t)}
              onPause={() => handlePausePress(t)}
              onDetail={() => router.push(`/(tabs)/admin?detail=${encodeURIComponent(t.email)}`)}
            />
            {bumpConfirm === t.email && (
              <Text style={st.bumpConfirm}>
                Limit extended to {t.request_limit + 25} ✓
              </Text>
            )}
          </View>
        ))}
      </ScrollView>

      {/* Pause confirmation modal */}
      <Modal
        visible={!!pauseModal}
        animationType="slide"
        transparent
        onRequestClose={() => setPauseModal(null)}
      >
        <View style={st.modalOverlay}>
          <View style={st.modalSheet}>
            <View style={st.sheetHandle} />
            <Text style={st.modalTitle}>
              {pauseModal?.action === "pause"
                ? `Pause ${pauseModal?.tester.display_name}?`
                : `Unpause ${pauseModal?.tester.display_name}?`
              }
            </Text>
            <Text style={st.modalSub}>
              {pauseModal?.action === "pause"
                ? "This immediately blocks their API calls. You can restore access at any time."
                : "This restores their access immediately."}
            </Text>
            <View style={st.modalActions}>
              <TouchableOpacity style={st.modalCancel} onPress={() => setPauseModal(null)}>
                <Text style={st.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[st.modalConfirm,
                  pauseModal?.action === "pause" ? st.modalConfirmPause : st.modalConfirmUnpause
                ]}
                onPress={confirmPause}
              >
                <Text style={st.modalConfirmText}>
                  {pauseModal?.action === "pause" ? "Pause access" : "Restore access"}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const st = StyleSheet.create({
  safe:        { flex: 1, backgroundColor: C.bg },
  header:      {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingVertical: 13,
    backgroundColor: C.bgCard, borderBottomWidth: 0.5, borderBottomColor: C.border2,
    ...S.xs,
  },
  headerSub:   { fontSize: 10, fontWeight: "700", color: C.ink3, letterSpacing: 1 },
  headerTitle: { fontSize: 18, fontWeight: "800", color: C.ink },
  headerRight: { flexDirection: "row", alignItems: "center", gap: 6 },
  syncTime:    { fontSize: 11, color: C.ink3, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  liveDot:     {
    width: 7, height: 7, borderRadius: 4,
    backgroundColor: C.green,
  },

  // Health strip
  healthStrip: { flexDirection: "row", gap: 10, marginTop: 14, marginBottom: 14 },
  hsCard:      {
    flex: 1, backgroundColor: C.bgCard,
    borderRadius: R.lg, borderWidth: 0.5, borderColor: C.border2,
    padding: 12, gap: 2, ...S.xs,
  },
  hsCardAlert: { backgroundColor: "#FFF5F5", borderColor: C.redB },
  hsLabel:     { fontSize: 9, fontWeight: "700", color: C.ink3, letterSpacing: .8 },
  hsVal:       { fontSize: 22, fontWeight: "800", color: C.ink, lineHeight: 26 },
  hsSub:       { fontSize: 9, color: C.ink3, lineHeight: 13 },

  // Filter row
  filterRow:   {
    flexDirection: "row", alignItems: "center",
    justifyContent: "space-between", marginBottom: 10,
  },
  sectionLabel:{ fontSize: 10, fontWeight: "700", color: C.ink3, letterSpacing: 1 },
  filterPills: { flexDirection: "row", gap: 6 },
  filterPill:  {
    paddingHorizontal: 12, paddingVertical: 5,
    borderRadius: R.full, borderWidth: 0.5, borderColor: C.border2,
    backgroundColor: C.bgCard,
  },
  filterPillOn:     { backgroundColor: C.soft, borderColor: C.border },
  filterPillText:   { fontSize: 11, fontWeight: "600", color: C.ink2 },
  filterPillTextOn: { color: C.acc, fontWeight: "700" },

  // Tester card
  tCard:       {
    backgroundColor: C.bgCard, borderRadius: R.xl,
    borderWidth: 0.5, borderColor: C.border2,
    padding: 14, marginBottom: 10, gap: 0, ...S.xs,
  },
  tCardError:  { borderColor: C.redB, backgroundColor: "#FFFBFB" },
  tCardPaused: { opacity: 0.55 },
  tHeader:     { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 12 },
  avatar:      {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: C.soft, alignItems: "center", justifyContent: "center",
    borderWidth: 0.5, borderColor: C.border,
  },
  avatarText:  { fontSize: 12, fontWeight: "700", color: C.acc },
  tName:       { fontSize: 14, fontWeight: "700", color: C.ink },
  tEmail:      { fontSize: 11, color: C.ink3, marginTop: 1 },
  statusRow:   { flexDirection: "row", alignItems: "center", gap: 5 },
  dot:         { width: 8, height: 8, borderRadius: 4 },
  statusText:  { fontSize: 11, color: C.ink2 },

  // Error banner
  errBanner:   {
    flexDirection: "row", alignItems: "flex-start", gap: 8,
    backgroundColor: C.redS, borderRadius: R.md,
    borderWidth: 0.5, borderColor: C.redB,
    padding: 9, marginBottom: 8,
  },
  errIcon:     { marginTop: 1 },
  errType:     { fontSize: 11, fontWeight: "700", color: C.red },
  errMsg:      { fontSize: 11, color: C.ink2, marginTop: 1, lineHeight: 15 },
  errTime:     { fontSize: 10, color: C.ink3, marginTop: 2 },

  // Near-limit banner
  nearBanner:  {
    flexDirection: "row", alignItems: "center", gap: 7,
    backgroundColor: C.amberS, borderRadius: R.md,
    borderWidth: 0.5, borderColor: C.amberB,
    padding: 9, marginBottom: 8,
  },
  nearText:    { flex: 1, fontSize: 11, color: C.amber, lineHeight: 15 },

  // Usage bar
  usageSection:{ marginBottom: 10 },
  usageRow:    { flexDirection: "row", justifyContent: "space-between", marginBottom: 5 },
  usageLabel:  { fontSize: 9, fontWeight: "700", color: C.ink3, letterSpacing: .8 },
  usageNums:   { fontSize: 12, fontWeight: "700", color: C.ink },
  barBg:       { height: 6, backgroundColor: C.bg2, borderRadius: 3, overflow: "hidden" },
  barFill:     { height: 6, borderRadius: 3 },
  tokensRow:   { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 5 },
  tokenBadge:  {
    backgroundColor: C.bg2, borderRadius: R.sm,
    paddingHorizontal: 7, paddingVertical: 2,
    borderWidth: 0.5, borderColor: C.border2,
  },
  tokenBadgeText: { fontSize: 10, color: C.ink2 },
  usagePct:    { marginLeft: "auto" as any, fontSize: 10, color: C.ink3 },

  // Meta grid
  metaGrid:    { flexDirection: "row", gap: 8, marginBottom: 12 },
  metaCell:    {
    flex: 1, backgroundColor: C.bg2, borderRadius: R.md,
    padding: 9, borderWidth: 0.5, borderColor: C.border2,
  },
  metaLabel:   { fontSize: 9, fontWeight: "700", color: C.ink3, letterSpacing: .8, marginBottom: 3 },
  metaVal:     { fontSize: 12, fontWeight: "600", color: C.ink },

  // Action row
  actRow:      { flexDirection: "row", gap: 8 },
  actBtn:      {
    flex: 1, flexDirection: "row", alignItems: "center",
    justifyContent: "center", gap: 5,
    paddingVertical: 8, borderRadius: R.md,
    borderWidth: 0.5,
  },
  actText:     { fontSize: 11, fontWeight: "700" },
  actBump:     { backgroundColor: "#EFF6FF", borderColor: "#BFDBFE" },
  actPause:    { backgroundColor: C.redS,   borderColor: C.redB   },
  actUnpause:  { backgroundColor: C.greenS, borderColor: C.greenB },
  actDetail:   { backgroundColor: C.bg2,    borderColor: C.border2 },

  // Bump confirm
  bumpConfirm: { fontSize: 11, color: C.green, textAlign: "center", marginTop: -4, marginBottom: 10 },

  // Empty / error states
  emptyState:  { padding: 24, alignItems: "center" },
  emptyText:   { fontSize: 13, color: C.ink3, textAlign: "center", lineHeight: 20 },
  errState:    {
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: C.redS, borderRadius: R.lg,
    padding: 12, marginBottom: 14,
    borderWidth: 0.5, borderColor: C.redB,
  },
  errStateText:{ flex: 1, fontSize: 13, color: C.red },

  // Pause modal
  modalOverlay:{ flex: 1, backgroundColor: "rgba(0,0,0,0.45)", justifyContent: "flex-end",
    ...(Platform.OS === "web"
      ? { position: "fixed" as any, top: 0, left: 0, right: 0, bottom: 0, zIndex: 999 }
      : {})
  },
  modalSheet:  {
    backgroundColor: C.bgCard, borderTopLeftRadius: 24, borderTopRightRadius: 24,
    padding: 20, paddingBottom: Platform.OS === "ios" ? 40 : 28, gap: 10,
  },
  sheetHandle: {
    width: 44, height: 4, borderRadius: 2,
    backgroundColor: C.border2, alignSelf: "center", marginBottom: 6,
  },
  modalTitle:       { fontSize: 17, fontWeight: "800", color: C.ink },
  modalSub:         { fontSize: 13, color: C.ink2, lineHeight: 19 },
  modalActions:     { flexDirection: "row", gap: 10, marginTop: 6 },
  modalCancel:      {
    flex: 1, alignItems: "center", justifyContent: "center",
    borderRadius: R.lg, paddingVertical: 13,
    backgroundColor: C.bg2, borderWidth: 0.5, borderColor: C.border2,
  },
  modalCancelText:  { fontSize: 13, fontWeight: "600", color: C.ink2 },
  modalConfirm:     {
    flex: 2, flexDirection: "row", alignItems: "center", justifyContent: "center",
    borderRadius: R.lg, paddingVertical: 13, gap: 6,
  },
  modalConfirmPause:  { backgroundColor: C.red },
  modalConfirmUnpause:{ backgroundColor: C.green },
  modalConfirmText:   { fontSize: 14, fontWeight: "800", color: "#fff" },
});
