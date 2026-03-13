// app/(tabs)/settings.tsx  —  Context Engine / Memory Bank
import React, { useEffect, useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  SafeAreaView, ActivityIndicator, Linking, Platform,
  Dimensions, TextInput,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { C, R, S, USER_ID, API_BASE } from "../constants/config";
import { useGet, apiPost } from "../hooks/useApi";

const MAX_W = 820;
const pad = () => Platform.OS === "web" ? Math.max(16, (Dimensions.get("window").width - MAX_W) / 2) : 16;

// ── Cluster chip ──────────────────────────────────────────────────────────────
type Confidence = "high" | "med" | "low";

function MemoryPill({ label, confidence = "high" }: { label: string; confidence?: Confidence }) {
  const bg     = confidence === "high" ? C.greenSoft  : confidence === "med" ? C.amberSoft  : C.bgInput;
  const color  = confidence === "high" ? "#065F46"    : confidence === "med" ? "#92400E"    : C.inkSub;
  const border = confidence === "high" ? C.greenBorder: confidence === "med" ? C.amberBorder: C.border;
  return (
    <View style={[pill.wrap, { backgroundColor: bg, borderColor: border }]}>
      <Text style={[pill.text, { color }]}>{label}</Text>
    </View>
  );
}

const pill = StyleSheet.create({
  wrap: { paddingHorizontal:10, paddingVertical:4, borderRadius:R.full, borderWidth:1, margin:3 },
  text: { fontSize:12, fontWeight:"700" },
});

// ── Deduction card ────────────────────────────────────────────────────────────
function DeductionCard({ text, onConfirm, onForget }: {
  text: string; onConfirm: () => void; onForget: () => void;
}) {
  return (
    <View style={dc.wrap}>
      <View style={dc.header}>
        <Ionicons name="hardware-chip-outline" size={13} color={C.indigo} />
        <Text style={dc.label}>AI DEDUCTION</Text>
      </View>
      <Text style={dc.body}>{text}</Text>
      <View style={dc.actions}>
        <TouchableOpacity style={dc.confirm} onPress={onConfirm}>
          <Text style={dc.confirmText}>✅ Confirm</Text>
        </TouchableOpacity>
        <TouchableOpacity style={dc.forget} onPress={onForget}>
          <Text style={dc.forgetText}>❌ Forget</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const dc = StyleSheet.create({
  wrap:        { backgroundColor:C.bgCard, borderRadius:R.md, borderWidth:1, borderColor:C.border, padding:14, marginBottom:10, gap:8, ...S.xs },
  header:      { flexDirection:"row", alignItems:"center", gap:6 },
  label:       { fontSize:10, fontWeight:"800", color:C.indigo, letterSpacing:1 },
  body:        { fontSize:13, color:C.inkMid, lineHeight:19 },
  actions:     { flexDirection:"row", gap:8 },
  confirm:     { flex:1, paddingVertical:8, backgroundColor:C.greenSoft, borderRadius:R.sm, alignItems:"center", borderWidth:1, borderColor:C.greenBorder },
  confirmText: { fontSize:12, fontWeight:"700", color:"#065F46" },
  forget:      { flex:1, paddingVertical:8, backgroundColor:C.bgInput, borderRadius:R.sm, alignItems:"center", borderWidth:1, borderColor:C.border },
  forgetText:  { fontSize:12, fontWeight:"700", color:C.inkSub },
});

// ── Stat row ──────────────────────────────────────────────────────────────────
function StatStrip({ a, b, c }: { a:[string,string]; b:[string,string]; c:[string,string] }) {
  return (
    <View style={ss.row}>
      {[a,b,c].map(([val,lbl],i) => (
        <View key={i} style={[ss.box, i===1 && ss.mid]}>
          <Text style={ss.val}>{val}</Text>
          <Text style={ss.lbl}>{lbl}</Text>
        </View>
      ))}
    </View>
  );
}
const ss = StyleSheet.create({
  row: { flexDirection:"row", backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:1, borderColor:C.border, overflow:"hidden", ...S.xs },
  box: { flex:1, alignItems:"center", paddingVertical:14 },
  mid: { borderLeftWidth:1, borderRightWidth:1, borderColor:C.border },
  val: { fontSize:22, fontWeight:"800", color:C.indigo },
  lbl: { fontSize:11, color:C.inkMuted, marginTop:3 },
});

// ── Section wrapper ───────────────────────────────────────────────────────────
function Section({ label, children, action, onAction }: {
  label: string; children: React.ReactNode; action?: string; onAction?: () => void;
}) {
  return (
    <View style={sec.wrap}>
      <View style={sec.header}>
        <Text style={sec.label}>{label}</Text>
        {action && <TouchableOpacity onPress={onAction}><Text style={sec.action}>{action}</Text></TouchableOpacity>}
      </View>
      {children}
    </View>
  );
}
const sec = StyleSheet.create({
  wrap:   { gap:0 },
  header: { flexDirection:"row", alignItems:"center", justifyContent:"space-between", marginBottom:10 },
  label:  { fontSize:10, fontWeight:"800", color:C.inkMuted, letterSpacing:1.2 },
  action: { fontSize:12, color:C.indigo, fontWeight:"700" },
});

// ── Main Screen ───────────────────────────────────────────────────────────────
export default function ContextEngineScreen() {
  const { data, loading, refetch } = useGet<{ memory: any; ideas: any[] }>(`/api/memory?user_id=${USER_ID}`);
  const [ideaSearch, setIdeaSearch] = useState("");
  const [dismissed,  setDismissed]  = useState<Set<number>>(new Set());
  const [ideaDraft,  setIdeaDraft]  = useState("");

  useEffect(() => { refetch(); }, []);

  const memory = data?.memory || {};
  const ideas  = data?.ideas  || [];

  const location = memory.location || memory.home_city || "Tampa, FL";
  const fam      = Array.isArray(memory.family_members || memory.family)
                 ? (memory.family_members || memory.family) : [];
  const prefs    = memory.preferences || memory.likes || {};

  // Build identity clusters from memory
  const clusters: Record<string, Array<{label:string;confidence:Confidence}>> = {
    "Diet & Dining":        [],
    "Media & Interests":    [],
    "Logistics & Routine":  [],
    "Family":               [],
  };
  if (Object.keys(prefs).length > 0) {
    Object.entries(prefs).forEach(([k,v]) => {
      const label = `${k.replace(/_/g," ")}: ${v}`;
      clusters["Media & Interests"].push({ label, confidence:"high" });
    });
  }
  fam.forEach((m:any) => {
    const name = typeof m==="string" ? m : m.name || "?";
    clusters["Family"].push({ label:name, confidence:"high" });
  });
  if (memory.car || memory.vehicle)
    clusters["Logistics & Routine"].push({ label:`🚗 ${memory.car||memory.vehicle}`, confidence:"high" });
  if (location)
    clusters["Logistics & Routine"].push({ label:`📍 ${location}`, confidence:"high" });

  // Fallback static clusters if memory empty (matches ui_prototype)
  if (clusters["Diet & Dining"].length === 0) {
    clusters["Diet & Dining"] = [
      { label:"🍲 Indian Cuisine", confidence:"high" },
      { label:"👨‍🍳 Home Cooking", confidence:"high" },
      { label:"🥡 Takeout Weekends", confidence:"med" },
    ];
  }
  if (clusters["Media & Interests"].length === 0) {
    clusters["Media & Interests"] = [
      { label:"💻 Python / AI", confidence:"high" },
      { label:"🎬 Hollywood Sci-Fi", confidence:"high" },
      { label:"📺 Hindi Web Series", confidence:"med" },
    ];
  }
  if (clusters["Logistics & Routine"].length === 0) {
    clusters["Logistics & Routine"] = [
      { label:"🚗 Kia Seltos", confidence:"high" },
      { label:"🏋️ EōS Fitness", confidence:"high" },
      { label:"🎸 Yousician", confidence:"med" },
    ];
  }

  // AI Deductions (static — can be made dynamic via backend later)
  const deductions = [
    "You prefer morning workouts on weekends instead of evenings.",
    "You research tech purchases methodically — Lenovo laptops currently in consideration.",
    "Family outings succeed when planned 48h in advance with a concrete destination.",
  ];

  const filteredIdeas = ideas.filter(idea => {
    if (!ideaSearch) return true;
    const text = typeof idea==="string" ? idea : (idea.title||idea.description||idea.text||idea.value||idea.content||(typeof idea==="object"?JSON.stringify(idea):"")).toString().slice(0,200);
    return text.toLowerCase().includes(ideaSearch.toLowerCase());
  });

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.header}>
        <View>
          <Text style={st.headerSub}>FAMILY COO  ·  v2.0</Text>
          <Text style={st.headerTitle}>🧠 Context Engine</Text>
        </View>
        <TouchableOpacity onPress={refetch} style={st.refreshBtn}>
          <Ionicons name="refresh-outline" size={16} color={C.inkSub} />
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={[st.content, { paddingHorizontal: pad() }]}
        showsVerticalScrollIndicator={false}
      >
        {/* Profile strip */}
        <View style={[st.profileCard, S.sm]}>
          <View style={st.avatarRing}><Text style={{ fontSize:28 }}>🏠</Text></View>
          <View style={{ flex:1, gap:2 }}>
            <Text style={st.profileName}>Khandare Household</Text>
            <Text style={st.profileEmail}>{USER_ID}</Text>
            <Text style={st.profileLoc}>📍 {location}</Text>
          </View>
          <View style={st.activeBadge}>
            <View style={st.activeDot} />
            <Text style={st.activeText}>ACTIVE</Text>
          </View>
        </View>

        {/* Stats strip */}
        {!loading && (
          <StatStrip
            a={[String(ideas.length), "Ideas saved"]}
            b={[String(fam.length || "—"), "Family members"]}
            c={[String(Object.keys(memory).length || "—"), "Memory keys"]}
          />
        )}

        {/* ── Household Identity Clusters ──────────────────────── */}
        <Section label="🧬  HOUSEHOLD IDENTITY CLUSTERS">
          <View style={[st.clusterCard, S.xs]}>
            {Object.entries(clusters).map(([cat, pills], ci) => (
              pills.length > 0 ? (
                <View key={ci} style={[st.clusterRow, ci > 0 && { borderTopWidth:1, borderTopColor:C.borderSoft }]}>
                  <Text style={st.clusterCat}>{cat}</Text>
                  <View style={st.pillRow}>
                    {pills.map((p, pi) => <MemoryPill key={pi} label={p.label} confidence={p.confidence} />)}
                  </View>
                </View>
              ) : null
            ))}
          </View>
        </Section>

        {/* ── AI Suggestions ───────────────────────────────────── */}
        <Section label="💡  AI SUGGESTIONS">
          <View style={[st.suggestionCard, S.xs]}>
            {[
              "Since you love both AI and Sci-Fi, queue up Ex Machina or a new tech-thriller this weekend.",
              "To offset weekend takeout, try a quick Palak Paneer on Friday using fresh spinach — 30 minutes prep.",
              "Maximize your commute to EōS Fitness by syncing Yousician audio lessons to the Kia via Bluetooth.",
            ].map((s, i) => (
              <View key={i} style={[st.suggRow, i===0 && { borderTopWidth:0 }]}>
                <View style={st.suggIcon}>
                  <Ionicons name="sparkles" size={12} color={C.indigo} />
                </View>
                <Text style={st.suggText}>{s}</Text>
              </View>
            ))}
          </View>
        </Section>

        {/* ── Recently Learned ─────────────────────────────────── */}
        <Section label="🔍  RECENTLY LEARNED  ·  REVIEW AI DEDUCTIONS">
          {deductions.map((d, i) => (
            dismissed.has(i) ? null : (
              <DeductionCard key={i} text={d}
                onConfirm={() => setDismissed(prev => new Set([...prev, i]))}
                onForget={() => setDismissed(prev => new Set([...prev, i]))}
              />
            )
          ))}
        </Section>

        {/* ── Ideas Inbox ──────────────────────────────────────── */}
        <Section label="📥  QUICK IDEA INBOX"
          action={ideas.length > 0 ? `${ideas.length} saved` : undefined}>
          <View style={st.ideaInputRow}>
            <TextInput
              style={st.ideaInput}
              value={ideaDraft}
              onChangeText={setIdeaDraft}
              placeholder="Drop an idea here…  e.g. plan a weekend hike"
              placeholderTextColor={C.inkMuted}
            />
            <TouchableOpacity style={[st.ideaSave, !ideaDraft && { opacity:0.4 }]}
              disabled={!ideaDraft}
              onPress={() => setIdeaDraft("")}>
              <Text style={st.ideaSaveText}>Save</Text>
            </TouchableOpacity>
          </View>

          {ideas.length > 0 && (
            <>
              <View style={st.ideaSearch}>
                <Ionicons name="search-outline" size={13} color={C.inkMuted} />
                <TextInput
                  style={st.ideaSearchInput}
                  value={ideaSearch}
                  onChangeText={setIdeaSearch}
                  placeholder="Filter ideas…"
                  placeholderTextColor={C.inkMuted}
                />
              </View>
              <View style={[st.ideaList, S.xs]}>
                {(filteredIdeas.length ? filteredIdeas : ideas).slice(0, 6).map((idea:any, i:number) => {
                  const text = typeof idea==="string" ? idea : (idea.title||idea.description||idea.text||idea.value||idea.content||(typeof idea==="object"?JSON.stringify(idea):"")).toString().slice(0,200);
                  const done = idea.status === "done";
                  return (
                    <View key={i} style={[st.ideaRow, i===0 && { borderTopWidth:0 }]}>
                      <Ionicons name={done ? "checkmark-circle":"bulb-outline"} size={14}
                        color={done ? C.green : C.indigo} style={{ marginTop:2 }} />
                      <Text style={[st.ideaText, done && { textDecorationLine:"line-through", color:C.inkMuted }]}>
                        {text}
                      </Text>
                    </View>
                  );
                })}
              </View>
            </>
          )}
        </Section>

        {/* ── Engine Room ──────────────────────────────────────── */}
        <Section label="⚙️  ENGINE ROOM">
          <View style={[st.engineCard, S.xs]}>
            {[
              { icon:"server-outline",           label:"API Endpoint",      val:API_BASE,    color:C.indigo },
              { icon:"shield-checkmark-outline",  label:"Database",          val:"Supabase",  color:C.green  },
              { icon:"calendar-outline",          label:"Google Calendar",   val:"Connected", color:C.green  },
              { icon:"key-outline",               label:"AI Models",         val:"Claude + Groq", color:C.amber },
            ].map(({ icon, label, val, color }, i, arr) => (
              <View key={i} style={[st.engineRow, i===arr.length-1 && { borderBottomWidth:0 }]}>
                <View style={[st.engineIcon, { backgroundColor: color+"18" }]}>
                  <Ionicons name={icon as any} size={14} color={color} />
                </View>
                <Text style={st.engineLabel}>{label}</Text>
                <Text style={[st.engineVal, { color }]}>{val}</Text>
              </View>
            ))}
          </View>
          <TouchableOpacity style={st.docsBtn} onPress={() => Linking.openURL(`${API_BASE}/docs`)}>
            <Ionicons name="code-slash-outline" size={14} color={C.indigo} />
            <Text style={st.docsBtnText}>Open Swagger Docs</Text>
            <Ionicons name="open-outline" size={13} color={C.indigo} />
          </TouchableOpacity>
        </Section>

        <View style={st.footer}>
          <Text style={st.footerText}>Family COO  ·  FastAPI · Supabase · Expo React Native</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe:   { flex:1, backgroundColor:C.bg },
  header: {
    flexDirection:"row", alignItems:"center", justifyContent:"space-between",
    paddingHorizontal:20, paddingVertical:14,
    borderBottomWidth:1, borderBottomColor:C.border,
    shadowColor:"#0F172A", shadowOffset:{width:0,height:1}, shadowOpacity:0.05, shadowRadius:4, elevation:2,
  },
  headerSub:   { fontSize:10, fontWeight:"800", color:C.inkMuted, letterSpacing:1 },
  headerTitle: { fontSize:20, fontWeight:"800", color:C.ink, marginTop:2 },
  refreshBtn:  { padding:8, borderRadius:R.sm, backgroundColor:C.bgInput },

  content: { paddingTop:18, paddingBottom:48, gap:22 },

  profileCard: {
    flexDirection:"row", alignItems:"center", gap:14,
    backgroundColor:C.bgCard, borderRadius:R.xl,
    borderWidth:1, borderColor:C.indigoBorder, padding:16,
  },
  avatarRing: {
    width:56, height:56, borderRadius:28,
    backgroundColor:C.indigoSoft, alignItems:"center", justifyContent:"center",
    borderWidth:2, borderColor:C.indigo,
  },
  profileName:  { fontSize:15, fontWeight:"800", color:C.ink },
  profileEmail: { fontSize:11, color:C.inkSub },
  profileLoc:   { fontSize:11, color:C.inkMuted },
  activeBadge:  { flexDirection:"row", alignItems:"center", gap:5,
                  paddingHorizontal:9, paddingVertical:4,
                  backgroundColor:C.greenSoft, borderRadius:R.full,
                  borderWidth:1, borderColor:C.greenBorder },
  activeDot:    { width:6, height:6, borderRadius:3, backgroundColor:C.green },
  activeText:   { fontSize:10, fontWeight:"800", color:"#065F46", letterSpacing:0.8 },

  clusterCard: { backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:1, borderColor:C.border, overflow:"hidden" },
  clusterRow:  { padding:14, gap:8 },
  clusterCat:  { fontSize:12, fontWeight:"700", color:C.inkMid },
  pillRow:     { flexDirection:"row", flexWrap:"wrap", marginLeft:-3 },

  suggestionCard: { backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:1, borderColor:C.border, overflow:"hidden" },
  suggRow:   { flexDirection:"row", gap:10, padding:14, borderTopWidth:1, borderTopColor:C.borderSoft, alignItems:"flex-start" },
  suggIcon:  { width:22, height:22, borderRadius:R.xs, backgroundColor:C.indigoSoft, alignItems:"center", justifyContent:"center", marginTop:1 },
  suggText:  { flex:1, fontSize:13, color:C.inkMid, lineHeight:19 },

  ideaInputRow: { flexDirection:"row", gap:8, marginBottom:8 },
  ideaInput:    { flex:1, backgroundColor:C.bgCard, borderRadius:R.sm, borderWidth:1, borderColor:C.border, paddingHorizontal:12, paddingVertical:10, fontSize:13, color:C.ink },
  ideaSave:     { paddingHorizontal:16, paddingVertical:10, backgroundColor:C.indigo, borderRadius:R.sm },
  ideaSaveText: { fontSize:13, fontWeight:"700", color:"#FFFFFF" },
  ideaSearch:   { flexDirection:"row", alignItems:"center", gap:8, backgroundColor:C.bgCard, borderRadius:R.sm, borderWidth:1, borderColor:C.border, paddingHorizontal:12, paddingVertical:8, marginBottom:8 },
  ideaSearchInput: { flex:1, fontSize:13, color:C.ink },
  ideaList:     { backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:1, borderColor:C.border, overflow:"hidden" },
  ideaRow:      { flexDirection:"row", gap:10, padding:13, borderTopWidth:1, borderTopColor:C.borderSoft, alignItems:"flex-start" },
  ideaText:     { flex:1, fontSize:13, color:C.inkMid, lineHeight:18 },

  engineCard:  { backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:1, borderColor:C.border, overflow:"hidden", marginBottom:8 },
  engineRow:   { flexDirection:"row", alignItems:"center", gap:12, paddingHorizontal:14, paddingVertical:12, borderBottomWidth:1, borderBottomColor:C.borderSoft },
  engineIcon:  { width:30, height:30, borderRadius:R.xs, alignItems:"center", justifyContent:"center" },
  engineLabel: { flex:1, fontSize:13, color:C.ink, fontWeight:"500" },
  engineVal:   { fontSize:12, fontWeight:"700" },
  docsBtn:     { flexDirection:"row", alignItems:"center", justifyContent:"center", gap:7, paddingVertical:11, backgroundColor:C.indigoSoft, borderRadius:R.sm, borderWidth:1, borderColor:C.indigoBorder },
  docsBtnText: { fontSize:13, fontWeight:"700", color:C.indigo },

  footer:     { alignItems:"center", paddingTop:8 },
  footerText: { fontSize:11, color:C.inkMuted, textAlign:"center" },

  // referenced from config but needed here too
});
