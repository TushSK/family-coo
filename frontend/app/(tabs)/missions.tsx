// app/(tabs)/missions.tsx  —  Missions + Smart Suggestions
import React, { useEffect, useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, ActivityIndicator,
  StyleSheet, SafeAreaView, RefreshControl, Platform, Dimensions,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { C, R, S, USER_ID } from "../constants/config";
import { useGet, apiPost } from "../hooks/useApi";

const MAX_W = 820;
const pad = () => Platform.OS === "web" ? Math.max(16, (Dimensions.get("window").width - MAX_W) / 2) : 16;

type FilterTab = "pending" | "reviewed" | "all";

interface Mission {
  id: string; title: string;
  status: "pending"|"reviewed";
  end_time: string|null;
  snoozed_until?: string|null;
}

function isPast(iso:string|null):boolean { return iso ? new Date(iso).getTime() < Date.now() : false; }
function fmtRel(iso:string|null):string {
  if (!iso) return "";
  try {
    const diff = new Date(iso).getTime()-Date.now();
    const days = Math.round(diff/86400000);
    if (days===0) return "Today"; if (days===1) return "Tomorrow"; if (days===-1) return "Yesterday";
    if (days<0) return `${Math.abs(days)}d ago`; return `In ${days}d`;
  } catch { return iso.slice(0,10); }
}

// ── Productivity habits & suggestions ────────────────────────────────────────
const HABIT_SUGGESTIONS = [
  { emoji:"🏋️", title:"Gym session", desc:"Stay consistent — EōS Fitness M/W/F", color:C.redSoft,   border:C.redBorder   },
  { emoji:"🛒", title:"Weekly grocery run", desc:"Patel Brothers — restock essentials", color:C.greenSoft, border:C.greenBorder },
  { emoji:"🎸", title:"Yousician practice", desc:"30 min daily builds real skill fast",  color:C.amberSoft, border:C.amberBorder },
  { emoji:"👨‍👧", title:"Family outing",    desc:"Plan something fun this weekend",      color:C.indigoSoft,border:C.indigoBorder },
  { emoji:"💊", title:"Health check-in",   desc:"Schedule next doctor visit",            color:C.redSoft,   border:C.redBorder   },
];

const PRODUCTIVITY_TIPS = [
  { icon:"bulb-outline",      color:C.amber,  tip:"Batch similar errands together — saves 40% of driving time." },
  { icon:"time-outline",      color:C.indigo, tip:"The best time to plan next week is Sunday evening." },
  { icon:"trending-up-outline",color:C.green, tip:"Tracking completion rate boosts follow-through by 25%." },
  { icon:"heart-outline",     color:C.red,    tip:"Family dinner 3× per week correlates with stronger bonds." },
];

// ── Mission card ──────────────────────────────────────────────────────────────
function MissionCard({ mission, onComplete, onSnooze }: {
  mission:Mission; onComplete:(id:string)=>void; onSnooze:(id:string)=>void;
}) {
  const past    = isPast(mission.end_time);
  const pending = mission.status === "pending";
  const time    = fmtRel(mission.end_time);
  const isOverdue = past && pending;

  return (
    <View style={[mc.card, isOverdue&&mc.overdue, !pending&&mc.done]}>
      <View style={[mc.accent, {backgroundColor: !pending?C.green:isOverdue?C.red:C.indigo}]}/>
      <View style={mc.icon}>
        <Ionicons
          name={!pending?"checkmark-circle":isOverdue?"alert-circle":"ellipse-outline"}
          size={20}
          color={!pending?C.green:isOverdue?C.red:C.indigo}
        />
      </View>
      <View style={mc.body}>
        <Text style={[mc.title, !pending&&mc.titleDone]} numberOfLines={2}>{mission.title}</Text>
        {mission.end_time && (
          <View style={mc.metaRow}>
            <Ionicons name="time-outline" size={11} color={isOverdue?C.red:C.inkMuted}/>
            <Text style={[mc.meta, isOverdue&&{color:C.red,fontWeight:"700"}]}>{time}</Text>
            {isOverdue && <View style={mc.overdueTag}><Text style={mc.overdueText}>OVERDUE</Text></View>}
          </View>
        )}
      </View>
      {pending && (
        <View style={mc.actions}>
          <TouchableOpacity style={mc.completeBtn} onPress={()=>onComplete(mission.id)}>
            <Ionicons name="checkmark" size={14} color="#fff"/>
          </TouchableOpacity>
          <TouchableOpacity style={mc.snoozeBtn} onPress={()=>onSnooze(mission.id)}>
            <Ionicons name="alarm-outline" size={14} color={C.inkSub}/>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const mc = StyleSheet.create({
  card:       { flexDirection:"row", alignItems:"center", backgroundColor:C.bgCard, borderRadius:R.md, borderWidth:1, borderColor:C.border, marginBottom:8, overflow:"hidden", ...S.xs },
  overdue:    { borderColor:C.redBorder, backgroundColor:C.redSoft },
  done:       { opacity:0.6 },
  accent:     { width:3, alignSelf:"stretch" },
  icon:       { padding:12 },
  body:       { flex:1, paddingVertical:12, paddingRight:8, gap:4 },
  title:      { fontSize:14, fontWeight:"600", color:C.ink },
  titleDone:  { textDecorationLine:"line-through", color:C.inkSub },
  metaRow:    { flexDirection:"row", alignItems:"center", gap:5 },
  meta:       { fontSize:12, color:C.inkMuted },
  overdueTag: { paddingHorizontal:6, paddingVertical:1, backgroundColor:C.redBorder, borderRadius:R.full },
  overdueText:{ fontSize:9, fontWeight:"800", color:C.red, letterSpacing:0.5 },
  actions:    { flexDirection:"row", gap:6, paddingRight:12 },
  completeBtn:{ width:32, height:32, borderRadius:16, backgroundColor:C.green, alignItems:"center", justifyContent:"center" },
  snoozeBtn:  { width:32, height:32, borderRadius:16, backgroundColor:C.bgInput, alignItems:"center", justifyContent:"center", borderWidth:1, borderColor:C.border },
});

// ── Main Screen ───────────────────────────────────────────────────────────────
export default function MissionsScreen() {
  const router = useRouter();
  const [filter,     setFilter]     = useState<FilterTab>("pending");
  const [refreshing, setRefreshing] = useState(false);
  const [completing, setCompleting] = useState<Set<string>>(new Set());

  const res = useGet<{missions:Mission[]}>(`/api/missions?user_id=${USER_ID}&status=${filter}`);
  useEffect(()=>{ res.refetch(); },[filter]);
  const onRefresh = async()=>{ setRefreshing(true); res.refetch(); setRefreshing(false); };

  const missions  = res.data?.missions || [];
  const overdue   = missions.filter(m => m.status==="pending" && isPast(m.end_time));
  const onTime    = missions.filter(m => m.status==="pending" && !isPast(m.end_time));
  const reviewed  = missions.filter(m => m.status==="reviewed");

  const handleComplete = async (id:string) => {
    setCompleting(prev=>new Set([...prev,id]));
    try { await apiPost(`/api/missions/${id}/complete`,{}); res.refetch(); }
    catch{}
    setCompleting(prev=>{ const n=new Set(prev); n.delete(id); return n; });
  };

  const handleSnooze = async (id:string) => {
    const until = new Date(Date.now()+86400000).toISOString();
    try { await apiPost(`/api/missions/${id}/snooze`,{snoozed_until:until}); res.refetch(); }
    catch{}
  };

  const completionPct = missions.length > 0
    ? Math.round((reviewed.length / (missions.length + reviewed.length)) * 100) : 0;

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.header}>
        <View>
          <Text style={st.headerSub}>FAMILY COO  ·  COMMAND CENTER</Text>
          <Text style={st.headerTitle}>Missions</Text>
        </View>
        <TouchableOpacity style={st.addBtn} onPress={()=>router.push("/(tabs)/chat")}>
          <Ionicons name="add" size={18} color="#fff"/>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={[st.content,{paddingHorizontal:pad()}]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.indigo}/>}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Stats strip ──────────────────────────────────────── */}
        <View style={[st.statsRow, S.xs]}>
          <View style={st.statBox}>
            <Text style={[st.statNum,{color:C.indigo}]}>{onTime.length}</Text>
            <Text style={st.statLbl}>On Track</Text>
          </View>
          <View style={[st.statBox,st.statMid]}>
            <Text style={[st.statNum,{color:overdue.length>0?C.red:C.green}]}>{overdue.length}</Text>
            <Text style={st.statLbl}>Overdue</Text>
          </View>
          <View style={st.statBox}>
            <Text style={[st.statNum,{color:C.green}]}>{reviewed.length}</Text>
            <Text style={st.statLbl}>Completed</Text>
          </View>
        </View>

        {/* ── Overdue alert ────────────────────────────────────── */}
        {overdue.length>0 && (
          <View style={st.overdueAlert}>
            <Ionicons name="alert-circle" size={16} color={C.red}/>
            <Text style={st.overdueAlertText}>
              {overdue.length} mission{overdue.length!==1?"s":""} past due — tap to complete or reschedule.
            </Text>
          </View>
        )}

        {/* ── Filter tabs ──────────────────────────────────────── */}
        <View style={st.filterRow}>
          {(["pending","reviewed","all"] as FilterTab[]).map(f=>(
            <TouchableOpacity key={f} onPress={()=>setFilter(f)}
              style={[st.filterTab, filter===f&&st.filterTabActive]}>
              <Text style={[st.filterText, filter===f&&st.filterTextActive]}>
                {f==="pending"?"Active":f==="reviewed"?"Done":"All"}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* ── Mission list ─────────────────────────────────────── */}
        {res.loading
          ? <ActivityIndicator color={C.indigo} style={{marginVertical:24}}/>
          : missions.length===0
            ? (
              <View style={st.emptyWrap}>
                <Text style={st.emptyEmoji}>🎯</Text>
                <Text style={st.emptyTitle}>No missions here</Text>
                <Text style={st.emptySub}>Chat with Family COO to create your first mission.</Text>
                <TouchableOpacity style={st.emptyBtn} onPress={()=>router.push("/(tabs)/chat")}>
                  <Text style={st.emptyBtnText}>Open Chat</Text>
                </TouchableOpacity>
              </View>
            )
            : missions.map(m=>(
              <MissionCard key={m.id} mission={m}
                onComplete={handleComplete} onSnooze={handleSnooze}/>
            ))
        }

        {/* ── Habit Suggestions ────────────────────────────────── */}
        <View style={{gap:10}}>
          <Text style={st.sLabel}>💡  SUGGESTED HABITS FOR YOUR FAMILY</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            <View style={st.habitRow}>
              {HABIT_SUGGESTIONS.map((h,i)=>(
                <TouchableOpacity key={i}
                  style={[st.habitCard,{backgroundColor:h.color,borderColor:h.border}]}
                  onPress={()=>router.push("/(tabs)/chat")}>
                  <Text style={st.habitEmoji}>{h.emoji}</Text>
                  <Text style={st.habitTitle}>{h.title}</Text>
                  <Text style={st.habitDesc}>{h.desc}</Text>
                  <View style={[st.habitAddBtn,{borderColor:h.border}]}>
                    <Ionicons name="add" size={12} color={C.indigo}/>
                    <Text style={st.habitAddText}>Add Mission</Text>
                  </View>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>
        </View>

        {/* ── Productivity Insights ────────────────────────────── */}
        <View style={{gap:10}}>
          <Text style={st.sLabel}>🧠  PRODUCTIVITY INSIGHTS</Text>
          <View style={[st.tipsCard,S.xs]}>
            {PRODUCTIVITY_TIPS.map((t,i)=>(
              <View key={i} style={[st.tipRow,i===PRODUCTIVITY_TIPS.length-1&&{borderBottomWidth:0}]}>
                <View style={[st.tipIcon,{backgroundColor:t.color+"18"}]}>
                  <Ionicons name={t.icon as any} size={15} color={t.color}/>
                </View>
                <Text style={st.tipText}>{t.tip}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* ── Create via Chat CTA ──────────────────────────────── */}
        <TouchableOpacity style={st.chatCta} onPress={()=>router.push("/(tabs)/chat")}>
          <Ionicons name="chatbubble-outline" size={18} color="#fff"/>
          <Text style={st.chatCtaText}>Create a mission via Chat</Text>
          <Ionicons name="arrow-forward" size={14} color="#fff"/>
        </TouchableOpacity>

        <View style={{height:32}}/>
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe: { flex:1, backgroundColor:C.bg },
  header: {
    flexDirection:"row", alignItems:"center", justifyContent:"space-between",
    paddingHorizontal:20, paddingVertical:14,
    backgroundColor:C.bgCard, borderBottomWidth:1, borderBottomColor:C.border,
    shadowColor:"#0F172A", shadowOffset:{width:0,height:1}, shadowOpacity:0.05, shadowRadius:4, elevation:2,
  },
  headerSub:   { fontSize:10, fontWeight:"800", color:C.inkMuted, letterSpacing:1 },
  headerTitle: { fontSize:20, fontWeight:"800", color:C.ink, marginTop:2 },
  addBtn:      { width:36, height:36, borderRadius:18, backgroundColor:C.indigo, alignItems:"center", justifyContent:"center" },

  content: { paddingTop:16, paddingBottom:24, gap:18 },
  sLabel:  { fontSize:10, fontWeight:"800", color:C.inkMuted, letterSpacing:1.2 },

  statsRow:  { flexDirection:"row", backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:1, borderColor:C.border, overflow:"hidden" },
  statBox:   { flex:1, alignItems:"center", paddingVertical:14 },
  statMid:   { borderLeftWidth:1, borderRightWidth:1, borderColor:C.border },
  statNum:   { fontSize:22, fontWeight:"800" },
  statLbl:   { fontSize:11, color:C.inkMuted, marginTop:3 },

  overdueAlert: { flexDirection:"row", alignItems:"center", gap:8, backgroundColor:C.redSoft, borderRadius:R.md, borderWidth:1, borderColor:C.redBorder, padding:12 },
  overdueAlertText: { flex:1, fontSize:13, color:C.red, fontWeight:"600" },

  filterRow:       { flexDirection:"row", backgroundColor:C.bgInput, borderRadius:R.md, padding:4, gap:4 },
  filterTab:       { flex:1, paddingVertical:8, borderRadius:R.sm, alignItems:"center" },
  filterTabActive: { backgroundColor:C.bgCard, shadowColor:"#0F172A", shadowOffset:{width:0,height:1}, shadowOpacity:0.08, shadowRadius:4, elevation:2 },
  filterText:      { fontSize:13, fontWeight:"600", color:C.inkSub },
  filterTextActive:{ color:C.indigo, fontWeight:"800" },

  emptyWrap:  { alignItems:"center", paddingVertical:32, gap:8 },
  emptyEmoji: { fontSize:40 },
  emptyTitle: { fontSize:16, fontWeight:"700", color:C.ink },
  emptySub:   { fontSize:13, color:C.inkSub, textAlign:"center" },
  emptyBtn:   { marginTop:8, paddingHorizontal:24, paddingVertical:10, backgroundColor:C.indigo, borderRadius:R.full },
  emptyBtnText:{ fontSize:13, fontWeight:"700", color:"#fff" },

  habitRow:  { flexDirection:"row", gap:10, paddingBottom:4 },
  habitCard: { width:150, borderRadius:R.lg, borderWidth:1, padding:14, gap:6 },
  habitEmoji:{ fontSize:26 },
  habitTitle:{ fontSize:13, fontWeight:"800", color:C.ink },
  habitDesc: { fontSize:11, color:C.inkSub, lineHeight:16 },
  habitAddBtn:{ flexDirection:"row", alignItems:"center", gap:4, marginTop:4, paddingVertical:5, paddingHorizontal:8, borderRadius:R.full, borderWidth:1, backgroundColor:C.bgCard },
  habitAddText:{ fontSize:11, fontWeight:"700", color:C.indigo },

  tipsCard: { backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:1, borderColor:C.border, overflow:"hidden" },
  tipRow:   { flexDirection:"row", alignItems:"flex-start", gap:12, padding:13, borderBottomWidth:1, borderBottomColor:C.borderSoft },
  tipIcon:  { width:30, height:30, borderRadius:R.xs, alignItems:"center", justifyContent:"center" },
  tipText:  { flex:1, fontSize:13, color:C.inkMid, lineHeight:19 },

  chatCta:  { flexDirection:"row", alignItems:"center", justifyContent:"center", gap:10, backgroundColor:C.indigo, borderRadius:R.lg, padding:15,
              shadowColor:C.indigo, shadowOffset:{width:0,height:4}, shadowOpacity:0.25, shadowRadius:8, elevation:6 },
  chatCtaText:{ fontSize:15, fontWeight:"700", color:"#fff" },

  // referenced colors
});
