// app/(tabs)/index.tsx  —  Executive Briefing Dashboard (lively version)
import React, { useEffect, useMemo, useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, ActivityIndicator,
  StyleSheet, SafeAreaView, RefreshControl, Platform, Dimensions, Animated,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { C, R, S, USER_ID } from "../constants/config";
import { useGet } from "../hooks/useApi";

const MAX_W = 820;
const pad = () => Platform.OS === "web" ? Math.max(16, (Dimensions.get("window").width - MAX_W) / 2) : 16;

// ── Motivation quotes — rotates daily ────────────────────────────────────────
const QUOTES = [
  { text: "The secret of getting ahead is getting started.", author: "Mark Twain" },
  { text: "Small daily improvements are the key to staggering long-term results.", author: "Robin Sharma" },
  { text: "A family that plans together, stays together.", author: "Family COO" },
  { text: "Your future is created by what you do today, not tomorrow.", author: "Robert Kiyosaki" },
  { text: "Discipline is the bridge between goals and accomplishment.", author: "Jim Rohn" },
  { text: "The best time to plant a tree was 20 years ago. The second best time is now.", author: "Chinese Proverb" },
  { text: "Focus on being productive instead of busy.", author: "Tim Ferriss" },
  { text: "Plans are nothing; planning is everything.", author: "Dwight D. Eisenhower" },
  { text: "Take care of your family and your family will take care of you.", author: "Family COO" },
  { text: "A goal without a plan is just a wish.", author: "Antoine de Saint-Exupéry" },
  { text: "Momentum builds when small wins stack up every single day.", author: "Family COO" },
  { text: "First, have a definite, clear, practical ideal — a goal.", author: "Aristotle" },
  { text: "The key is not to prioritize what's on your schedule, but to schedule your priorities.", author: "Stephen Covey" },
  { text: "Energy and persistence conquer all things.", author: "Benjamin Franklin" },
];

function getDailyQuote() {
  const day = Math.floor(Date.now() / 86400000);
  return QUOTES[day % QUOTES.length];
}

// ── Time helpers ──────────────────────────────────────────────────────────────
function parseISO(s?: string): Date | null {
  if (!s) return null; try { return new Date(s); } catch { return null; }
}
function fmtTime(iso?: string) {
  const d = parseISO(iso); if (!d) return "All day";
  return d.toLocaleTimeString("en-US", { hour:"numeric", minute:"2-digit", hour12:true });
}
function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}
function todayLabel() {
  return new Date().toLocaleDateString("en-US", { weekday:"long", month:"long", day:"numeric" });
}

type Ev = { id:string; summary?:string; location?:string;
             start?:{dateTime?:string;date?:string};
             end?:{dateTime?:string;date?:string} };
type EvStatus = "past"|"active"|"future";

function evStart(e:Ev) { return parseISO(e.start?.dateTime||e.start?.date); }
function evEnd(e:Ev)   { return parseISO(e.end?.dateTime  ||e.end?.date); }
function evStatus(e:Ev): EvStatus {
  const s=evStart(e), en=evEnd(e), n=new Date();
  if (!s) return "future";
  if (en && n > en) return "past";
  if (n >= s) return "active";
  return "future";
}
function isBirthday(e:Ev) {
  return ["happy birthday!","birthday"].includes((e.summary||"").toLowerCase().trim());
}
function todayEvents(events:Ev[]): Ev[] {
  const today = new Date().toDateString();
  return events
    .filter(e => !isBirthday(e) && evStart(e)?.toDateString() === today)
    .sort((a,b) => (evStart(a)?.getTime()||0) - (evStart(b)?.getTime()||0));
}
function weekBandwidth(events:Ev[]) {
  const n = new Date(); n.setHours(0,0,0,0);
  const cut = new Date(n.getTime()+7*86400000);
  const week = events.filter(e => { const s=evStart(e); return s&&s>=n&&s<=cut&&!isBirthday(e); });
  const dayCounts: Record<string,number> = {};
  const dayNames:  Record<string,string>  = {};
  week.forEach(e => {
    const s=evStart(e); if (!s) return;
    const k=s.toDateString();
    dayCounts[k]=(dayCounts[k]||0)+1;
    dayNames[k]=s.toLocaleDateString("en-US",{weekday:"long"});
  });
  let busiestCount=0, busiestDay="—";
  Object.entries(dayCounts).forEach(([k,v])=>{ if(v>busiestCount){busiestCount=v;busiestDay=dayNames[k];} });
  const eveningBusy = new Set<string>();
  week.forEach(e=>{const s=evStart(e);if(s&&s.getHours()>=17)eveningBusy.add(s.toDateString());});
  return { total:week.length, busiestDay, busiestCount, freeEvenings:7-eveningBusy.size };
}
function findConflicts(events:Ev[]) {
  const today=todayEvents(events);
  const out:Array<{a:Ev;b:Ev}>=[];
  for(let i=0;i<today.length;i++)
    for(let j=i+1;j<today.length;j++){
      const aE=evEnd(today[i]),bS=evStart(today[j]);
      if(aE&&bS&&bS<aE) out.push({a:today[i],b:today[j]});
    }
  return out;
}
function generateBriefing(todayEvs:Ev[],pending:number):string {
  const h=new Date().getHours(), part=h<12?"morning":h<17?"afternoon":"evening";
  if(todayEvs.length===0) return `Your schedule is clear this ${part}. No events — a good window to plan the week ahead or process your Ideas Inbox.`;
  const active=todayEvs.find(e=>evStatus(e)==="active");
  const next  =todayEvs.find(e=>evStatus(e)==="future");
  const last  =[...todayEvs].reverse().find(e=>evEnd(e));
  let brief="";
  if(active){ brief+=`You're currently in **${active.summary}**.`; if(next) brief+=` Up next: **${next.summary}** at ${fmtTime(next.start?.dateTime)}.`; }
  else if(next) brief+=`Next up: **${next.summary}** at ${fmtTime(next.start?.dateTime)}.`;
  if(last) brief+=` Your ${part} wraps at ${fmtTime(last.end?.dateTime)}.`;
  if(pending>0) brief+=` You have ${pending} pending mission${pending!==1?"s":""} to review.`;
  return brief||`You have ${todayEvs.length} event${todayEvs.length!==1?"s":""} today.`;
}
function inferActions(evs:Ev[]) {
  const actions:Array<{emoji:string;label:string}>=[];
  const seen=new Set<string>();
  const add=(emoji:string,label:string)=>{ if(!seen.has(label)){seen.add(label);actions.push({emoji,label});} };
  evs.forEach(e=>{
    const t=(e.summary||"").toLowerCase(), l=(e.location||"").toLowerCase();
    if(t.includes("gym")||t.includes("eos")||t.includes("fitness")) add("🏋️",`Traffic to ${e.location||"gym"}`);
    else if(t.includes("grocery")||t.includes("market")) add("🛒",`Prep ${e.location||"shopping"} list`);
    else if(t.includes("meeting")||t.includes("call")||t.includes("sync")) add("📋",`Review agenda — ${e.summary}`);
    else if(t.includes("judo")||t.includes("class")||t.includes("lesson")) add("👟","Pack gear bag");
    else if(t.includes("doctor")||t.includes("dentist")||t.includes("lab")) add("📁","Grab insurance card");
  });
  add("🚗","Check Tampa traffic"); add("📱","Review Ideas Inbox");
  return actions.slice(0,5);
}

// ── Sub-components ────────────────────────────────────────────────────────────
function SLabel({ text }:{text:string}) { return <Text style={st.sLabel}>{text}</Text>; }

function QuoteCard() {
  const q = getDailyQuote();
  return (
    <View style={st.quoteCard}>
      <View style={st.quoteAccent} />
      <View style={{ flex:1, gap:4 }}>
        <Text style={st.quoteIcon}>✦</Text>
        <Text style={st.quoteText}>"{q.text}"</Text>
        <Text style={st.quoteAuthor}>— {q.author}</Text>
      </View>
    </View>
  );
}

function BwPill({ label,value,sub,color=C.indigo }:{label:string;value:string;sub?:string;color?:string}) {
  return (
    <View style={[st.bwPill,{borderColor:color+"30"}]}>
      <Text style={[st.bwVal,{color}]}>{value}</Text>
      <Text style={st.bwLbl}>{label}</Text>
      {sub?<Text style={st.bwSub}>{sub}</Text>:null}
    </View>
  );
}

function TlDot({status}:{status:EvStatus}) {
  const bg = status==="past"?C.green:status==="active"?C.indigo:C.slateLight;
  return <View style={st.dotWrap}><View style={[st.dot,{backgroundColor:bg},status==="active"&&st.dotGlow]}/></View>;
}

function TlItem({ev,isLast}:{ev:Ev;isLast:boolean}) {
  const status=evStatus(ev), isPast=status==="past", isActive=status==="active";
  return (
    <View style={st.tlRow}>
      <View style={st.tlLeft}>
        <TlDot status={status}/>
        {!isLast&&<View style={[st.tlLine,isPast&&{backgroundColor:C.green+"50"}]}/>}
      </View>
      <View style={[st.tlCard,isActive&&{borderLeftWidth:3,borderLeftColor:C.indigo},isPast&&{opacity:0.5}]}>
        <Text style={st.tlTime}>{fmtTime(ev.start?.dateTime||ev.start?.date)}</Text>
        <Text style={[st.tlTitle,isPast&&{textDecorationLine:"line-through",color:C.inkSub}]}>
          {ev.summary||"Untitled"}
        </Text>
        {ev.location?<Text style={st.tlMeta}>📍 {ev.location}</Text>:null}
        {isActive&&(
          <View style={st.activeBadge}>
            <View style={st.activePulse}/><Text style={st.activeText}>LIVE NOW</Text>
          </View>
        )}
      </View>
    </View>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────
export default function BriefingScreen() {
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);
  const [dismissedConflict, setDismissed] = useState<string|null>(null);

  const calRes  = useGet<{events:Ev[]}>(`/api/calendar?user_id=${USER_ID}`);
  const insRes  = useGet<{kpis:any;insights:any[]}>(`/api/insights?user_id=${USER_ID}`);
  const missRes = useGet<{missions:any[]}>(`/api/missions?user_id=${USER_ID}&status=pending`);

  const refetchAll = () => { calRes.refetch(); insRes.refetch(); missRes.refetch(); };
  useEffect(()=>{ refetchAll(); },[]);
  const onRefresh = async()=>{ setRefreshing(true); refetchAll(); setRefreshing(false); };

  const allEvents  = calRes.data?.events     || [];
  const todayEvs   = useMemo(()=>todayEvents(allEvents),[allEvents]);
  const bw         = useMemo(()=>weekBandwidth(allEvents),[allEvents]);
  const conflicts  = useMemo(()=>findConflicts(allEvents),[allEvents]);
  const actions    = useMemo(()=>inferActions(todayEvs),[todayEvs]);
  const kpis       = insRes.data?.kpis     || {};
  const insights   = insRes.data?.insights || [];
  const pending    = missRes.data?.missions?.length ?? kpis.pending_missions ?? 0;
  const briefing   = useMemo(()=>generateBriefing(todayEvs,pending),[todayEvs,pending]);
  const activeConflict = conflicts.find(c=>`${c.a.id}-${c.b.id}`!==dismissedConflict);
  const hour = new Date().getHours();

  // Lively header gradient background approximation via color
  const headerBg = hour < 12 ? "#4338CA" : hour < 17 ? "#4F46E5" : "#3730A3";

  return (
    <SafeAreaView style={st.safe}>
      {/* ── Lively Header ──────────────────────────────────────── */}
      <View style={[st.header,{backgroundColor:headerBg}]}>
        <View style={{ flex:1 }}>
          <Text style={st.headerLabel}>
            {hour<12?"☀️ MORNING BRIEFING":hour<17?"⚡ AFTERNOON UPDATE":"🌙 EVENING REVIEW"}
          </Text>
          <Text style={st.headerGreeting}>{greeting()}, Tushar 👋</Text>
          <Text style={st.headerDate}>{todayLabel()}</Text>
        </View>
        <TouchableOpacity style={st.headerRefresh} onPress={refetchAll}>
          <Ionicons name="refresh-outline" size={16} color="rgba(255,255,255,0.8)" />
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={[st.content,{paddingHorizontal:pad()}]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.indigo}/>}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Motivation Quote ─────────────────────────────────── */}
        <QuoteCard />

        {/* ── AI Briefing Card ─────────────────────────────────── */}
        <View style={st.briefCard}>
          <View style={st.briefTopRow}>
            <View style={st.briefIconWrap}>
              <Ionicons name="sparkles" size={13} color={C.indigo} />
            </View>
            <Text style={st.briefLabel}>DAILY BRIEF  ·  AI INFERENCE</Text>
            {todayEvs.length>0&&(
              <View style={st.briefBadge}>
                <Text style={st.briefBadgeText}>{todayEvs.length} events</Text>
              </View>
            )}
          </View>
          <Text style={st.briefText}>{briefing}</Text>
          <TouchableOpacity style={st.briefCta} onPress={()=>router.push("/(tabs)/chat")}>
            <Ionicons name="chatbubble-outline" size={13} color={C.indigo} />
            <Text style={st.briefCtaText}>Discuss with Family COO</Text>
            <Ionicons name="arrow-forward" size={12} color={C.indigo} />
          </TouchableOpacity>
        </View>

        {/* ── Conflict Alert ──────────────────────────────────── */}
        {activeConflict&&(
          <View style={st.conflictBox}>
            <View style={st.conflictTop}>
              <Ionicons name="warning" size={14} color={C.amber}/>
              <Text style={st.conflictTitle}>Schedule Conflict Detected</Text>
            </View>
            <Text style={st.conflictBody}>
              <Text style={{fontWeight:"700"}}>{activeConflict.a.summary}</Text>
              {" overlaps with "}
              <Text style={{fontWeight:"700"}}>{activeConflict.b.summary}</Text>
            </Text>
            <View style={st.conflictBtns}>
              <TouchableOpacity style={st.reschedBtn}
                onPress={()=>{setDismissed(`${activeConflict.a.id}-${activeConflict.b.id}`);router.push("/(tabs)/chat");}}>
                <Text style={st.reschedText}>🔁 Auto-Reschedule</Text>
              </TouchableOpacity>
              <TouchableOpacity style={st.dismissBtn}
                onPress={()=>setDismissed(`${activeConflict.a.id}-${activeConflict.b.id}`)}>
                <Text style={st.dismissText}>Dismiss</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* ── Weekly Bandwidth ─────────────────────────────────── */}
        <View>
          <SLabel text="📊  ANALYTICAL BANDWIDTH  ·  NEXT 7 DAYS" />
          <View style={st.bwRow}>
            <BwPill label="Events" value={String(bw.total)} sub="this week" color={C.indigo}/>
            <BwPill label="Busiest" value={bw.busiestDay.slice(0,3)} sub={`${bw.busiestCount} events`} color={C.amber}/>
            <BwPill label="Free Eve." value={String(bw.freeEvenings)} sub="available" color={C.green}/>
            <BwPill label="Pending" value={String(pending)} sub="missions" color={pending>0?C.red:C.green}/>
          </View>
        </View>

        {/* ── Today's Flight Plan ──────────────────────────────── */}
        <View>
          <View style={st.sRow}>
            <SLabel text="✈  TODAY'S FLIGHT PLAN" />
            {calRes.loading&&<ActivityIndicator size="small" color={C.indigo}/>}
          </View>
          {!calRes.loading&&todayEvs.length===0
            ? <View style={st.emptyBox}><Text style={st.emptyText}>Runway is clear — no events today.</Text></View>
            : <View style={st.tlContainer}>
                {todayEvs.map((ev,i)=><TlItem key={ev.id||i} ev={ev} isLast={i===todayEvs.length-1}/>)}
              </View>
          }
        </View>

        {/* ── Pattern Insights ─────────────────────────────────── */}
        {insights.length>0&&(
          <View style={{gap:8}}>
            <SLabel text="PATTERN INSIGHTS"/>
            {insights.slice(0,3).map((ins:any,i:number)=>{
              const bg=ins.type==="win"?C.greenSoft:ins.type==="watch"?C.amberSoft:ins.type==="tip"?C.indigoSoft:"#F8FAFC";
              const border=ins.type==="win"?C.greenBorder:ins.type==="watch"?C.amberBorder:ins.type==="tip"?C.indigoBorder:C.border;
              return (
                <View key={i} style={[st.insightRow,{backgroundColor:bg,borderColor:border}]}>
                  <Text style={{fontSize:18}}>{ins.emoji}</Text>
                  <View style={{flex:1}}>
                    <Text style={st.insightHead}>{ins.headline}</Text>
                    <Text style={st.insightSub}>{ins.detail}</Text>
                  </View>
                </View>
              );
            })}
          </View>
        )}

        {/* ── Contextual Actions ───────────────────────────────── */}
        <View>
          <SLabel text="⚡  CONTEXTUAL QUICK ACTIONS"/>
          <Text style={st.actSub}>Anticipated needs based on today's schedule</Text>
          <View style={st.actCard}>
            {actions.map((a,i)=>(
              <TouchableOpacity key={i}
                style={[st.actRow,i===actions.length-1&&{borderBottomWidth:0}]}
                onPress={()=>router.push("/(tabs)/chat")}>
                <Text style={{fontSize:18,width:26,textAlign:"center"}}>{a.emoji}</Text>
                <Text style={st.actLabel}>{a.label}</Text>
                <Ionicons name="chevron-forward" size={13} color={C.inkMuted}/>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <View style={{height:36}}/>
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe: { flex:1, backgroundColor:C.bg },

  // Lively header
  header: {
    paddingHorizontal:20, paddingTop:16, paddingBottom:18,
    shadowColor:"#000", shadowOffset:{width:0,height:3}, shadowOpacity:0.15, shadowRadius:8, elevation:6,
  },
  headerLabel:   { fontSize:10, fontWeight:"800", color:"rgba(255,255,255,0.7)", letterSpacing:1.5, marginBottom:4 },
  headerGreeting:{ fontSize:22, fontWeight:"800", color:"#FFFFFF" },
  headerDate:    { fontSize:12, color:"rgba(255,255,255,0.75)", marginTop:2 },
  headerRefresh: { position:"absolute", right:20, top:20, padding:8,
                   borderRadius:R.sm, backgroundColor:"rgba(255,255,255,0.15)" },

  content: { paddingTop:18, paddingBottom:24, gap:20 },
  sLabel:  { fontSize:10, fontWeight:"800", color:C.inkMuted, letterSpacing:1.2, marginBottom:10 },
  sRow:    { flexDirection:"row", alignItems:"center", justifyContent:"space-between", marginBottom:10 },

  // Quote
  quoteCard: {
    flexDirection:"row", gap:12,
    backgroundColor:C.bgCard, borderRadius:R.lg,
    borderWidth:1, borderColor:C.indigoBorder,
    padding:16,
    shadowColor:"#0F172A", shadowOffset:{width:0,height:2}, shadowOpacity:0.06, shadowRadius:6, elevation:2,
  },
  quoteAccent: { width:3, borderRadius:2, backgroundColor:C.indigo, alignSelf:"stretch" },
  quoteIcon:   { fontSize:14, color:C.indigo },
  quoteText:   { fontSize:14, color:C.inkMid, lineHeight:21, fontStyle:"italic" },
  quoteAuthor: { fontSize:12, fontWeight:"700", color:C.indigo, marginTop:2 },

  // Briefing
  briefCard: {
    backgroundColor:C.bgCard, borderRadius:R.lg,
    borderWidth:1, borderColor:C.border, padding:16, gap:10,
    shadowColor:"#0F172A", shadowOffset:{width:0,height:2}, shadowOpacity:0.06, shadowRadius:6, elevation:2,
  },
  briefTopRow:  { flexDirection:"row", alignItems:"center", gap:8 },
  briefIconWrap:{ width:22, height:22, borderRadius:R.xs, backgroundColor:C.indigoSoft, alignItems:"center", justifyContent:"center" },
  briefLabel:   { flex:1, fontSize:10, fontWeight:"800", color:C.indigo, letterSpacing:1 },
  briefBadge:   { paddingHorizontal:8, paddingVertical:3, backgroundColor:C.indigoSoft, borderRadius:R.full },
  briefBadgeText:{ fontSize:11, fontWeight:"700", color:C.indigo },
  briefText:    { fontSize:14, color:C.inkMid, lineHeight:21 },
  briefCta:     { flexDirection:"row", alignItems:"center", gap:7, alignSelf:"flex-start",
                  paddingVertical:7, paddingHorizontal:13,
                  backgroundColor:C.indigoSoft, borderRadius:R.full,
                  borderWidth:1, borderColor:C.indigoBorder },
  briefCtaText: { fontSize:12, fontWeight:"700", color:C.indigo },

  // Conflict
  conflictBox:  { backgroundColor:C.amberSoft, borderRadius:R.md, borderWidth:1, borderColor:C.amberBorder, padding:14, gap:8 },
  conflictTop:  { flexDirection:"row", alignItems:"center", gap:7 },
  conflictTitle:{ fontSize:12, fontWeight:"800", color:"#92400E", letterSpacing:0.3 },
  conflictBody: { fontSize:13, color:C.inkMid, lineHeight:19 },
  conflictBtns: { flexDirection:"row", gap:8 },
  reschedBtn:   { flex:1, paddingVertical:9, backgroundColor:C.amber, borderRadius:R.sm, alignItems:"center" },
  reschedText:  { fontSize:12, fontWeight:"800", color:"#fff" },
  dismissBtn:   { paddingVertical:9, paddingHorizontal:14, borderRadius:R.sm, backgroundColor:C.bgCard, borderWidth:1, borderColor:C.amberBorder },
  dismissText:  { fontSize:12, fontWeight:"600", color:C.inkSub },

  // Bandwidth
  bwRow: { flexDirection:"row", gap:8 },
  bwPill:{ flex:1, backgroundColor:C.bgCard, borderRadius:R.md, borderWidth:1, padding:12, alignItems:"center", gap:3,
           shadowColor:"#0F172A", shadowOffset:{width:0,height:1}, shadowOpacity:0.04, shadowRadius:3, elevation:1 },
  bwVal: { fontSize:20, fontWeight:"800" },
  bwLbl: { fontSize:10, fontWeight:"700", color:C.inkMuted, textAlign:"center" },
  bwSub: { fontSize:10, color:C.inkMuted, textAlign:"center" },

  // Timeline
  tlContainer: { backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:1, borderColor:C.border, overflow:"hidden",
                  shadowColor:"#0F172A", shadowOffset:{width:0,height:1}, shadowOpacity:0.04, shadowRadius:3, elevation:1 },
  tlRow:  { flexDirection:"row" },
  tlLeft: { width:44, alignItems:"center", paddingTop:16 },
  dotWrap:{ width:22, alignItems:"center" },
  dot:    { width:11, height:11, borderRadius:6, borderWidth:2, borderColor:C.bgCard },
  dotGlow:{ shadowColor:C.indigo, shadowOffset:{width:0,height:0}, shadowOpacity:0.5, shadowRadius:6, elevation:4 },
  tlLine: { width:2, flex:1, marginTop:3, backgroundColor:C.border },
  tlCard: { flex:1, marginRight:12, marginTop:12, marginBottom:12,
            backgroundColor:C.bgCard, borderRadius:R.sm,
            borderWidth:1, borderColor:C.border, padding:11, gap:3 },
  tlTime:  { fontSize:11, fontWeight:"800", color:C.inkSub },
  tlTitle: { fontSize:14, fontWeight:"700", color:C.ink },
  tlMeta:  { fontSize:11, color:C.inkMuted },
  activeBadge: { flexDirection:"row", alignItems:"center", gap:5, alignSelf:"flex-start", marginTop:4,
                 paddingHorizontal:8, paddingVertical:3, backgroundColor:C.indigoSoft, borderRadius:R.full },
  activePulse: { width:6, height:6, borderRadius:3, backgroundColor:C.indigo },
  activeText:  { fontSize:10, fontWeight:"800", color:C.indigo, letterSpacing:0.8 },
  emptyBox:    { backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:1, borderColor:C.border, padding:20 },
  emptyText:   { fontSize:13, color:C.inkMuted, textAlign:"center" },

  // Insights
  insightRow: { flexDirection:"row", alignItems:"flex-start", gap:10, borderRadius:R.md, borderWidth:1, padding:12 },
  insightHead:{ fontSize:13, fontWeight:"700", color:C.ink },
  insightSub: { fontSize:12, color:C.inkSub, lineHeight:17, marginTop:2 },

  // Actions
  actSub:  { fontSize:11, color:C.inkSub, marginBottom:10, marginTop:-6 },
  actCard: { backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:1, borderColor:C.border, overflow:"hidden",
              shadowColor:"#0F172A", shadowOffset:{width:0,height:1}, shadowOpacity:0.04, shadowRadius:3, elevation:1 },
  actRow:  { flexDirection:"row", alignItems:"center", gap:12, paddingHorizontal:14, paddingVertical:13,
              borderBottomWidth:1, borderBottomColor:C.borderSoft },
  actLabel:{ flex:1, fontSize:14, color:C.inkMid, fontWeight:"500" },
});
