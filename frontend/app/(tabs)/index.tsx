// app/(tabs)/index.tsx  —  Briefing (v3 Lavender)
import React, { useEffect, useMemo, useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, ActivityIndicator,
  StyleSheet, SafeAreaView, RefreshControl, Platform, Dimensions, Animated,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { C, R, S, USER_ID } from "../constants/config";
import { ctxDailyBriefing, ctxQuickAction } from "../context/ChatContextStore";
import { useGet } from "../hooks/useApi";

const MAX_W = 820;
const hp = () => Platform.OS === "web" ? Math.max(16, (Dimensions.get("window").width - MAX_W) / 2) : 16;

// ── Quotes ────────────────────────────────────────────────────────────────────
const QUOTES = [
  { text:"Your future is created by what you do today, not tomorrow.", author:"Robert Kiyosaki" },
  { text:"A family that plans together, stays together.", author:"Family COO" },
  { text:"Small daily improvements are the key to staggering long-term results.", author:"Robin Sharma" },
  { text:"Discipline is the bridge between goals and accomplishment.", author:"Jim Rohn" },
  { text:"The key is not to prioritize what's on your schedule, but to schedule your priorities.", author:"Stephen Covey" },
  { text:"Plans are nothing; planning is everything.", author:"Dwight D. Eisenhower" },
  { text:"Focus on being productive instead of busy.", author:"Tim Ferriss" },
  { text:"Momentum builds when small wins stack up every single day.", author:"Family COO" },
  { text:"A goal without a plan is just a wish.", author:"Antoine de Saint-Exupéry" },
  { text:"Energy and persistence conquer all things.", author:"Benjamin Franklin" },
  { text:"Take care of your family and your family will take care of you.", author:"Family COO" },
  { text:"The secret of getting ahead is getting started.", author:"Mark Twain" },
  { text:"First, have a definite, clear, practical ideal — a goal.", author:"Aristotle" },
  { text:"The best time to plant a tree was 20 years ago. The second best time is now.", author:"Chinese Proverb" },
];

function getDailyQuote() {
  return QUOTES[Math.floor(Date.now() / 86400000) % QUOTES.length];
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
function greetLabel() {
  const h = new Date().getHours();
  return h < 12 ? "☀️ MORNING BRIEFING" : h < 17 ? "⚡ AFTERNOON UPDATE" : "🌙 EVENING REVIEW";
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
  const dayCounts:Record<string,number>={}, dayNames:Record<string,string>={};
  week.forEach(e => {
    const s=evStart(e); if (!s) return;
    const k=s.toDateString(); dayCounts[k]=(dayCounts[k]||0)+1;
    dayNames[k]=s.toLocaleDateString("en-US",{weekday:"long"});
  });
  let busiestCount=0, busiestDay="—";
  Object.entries(dayCounts).forEach(([k,v])=>{ if(v>busiestCount){busiestCount=v;busiestDay=dayNames[k];} });
  const eveningBusy=new Set<string>();
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
function generateBriefing(todayEvs:Ev[], pending:number):string {
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
    const t=(e.summary||"").toLowerCase();
    if(t.includes("gym")||t.includes("eos")||t.includes("fitness")) add("🏋️",`Traffic to ${e.location||"gym"}`);
    else if(t.includes("grocery")||t.includes("market")) add("🛒",`Prep ${e.location||"shopping"} list`);
    else if(t.includes("meeting")||t.includes("call")||t.includes("sync")) add("📋",`Review agenda — ${e.summary}`);
    else if(t.includes("judo")||t.includes("class")||t.includes("lesson")) add("👟","Pack gear bag");
    else if(t.includes("doctor")||t.includes("dentist")||t.includes("lab")) add("📁","Grab insurance card");
  });
  add("🚗","Check Tampa traffic"); add("📱","Review Ideas Inbox");
  return actions.slice(0,5);
}

// ── Weather (Open-Meteo, no API key) ─────────────────────────────────────────
function useWeather() {
  const [weather, setWeather] = useState<{temp:number;desc:string;icon:string}|null>(null);
  useEffect(()=>{
    fetch(`https://api.open-meteo.com/v1/forecast?latitude=27.9506&longitude=-82.4572&current_weather=true&temperature_unit=fahrenheit`)
      .then(r=>r.json())
      .then(d=>{
        const wc=d?.current_weather?.weathercode??0;
        const temp=Math.round(d?.current_weather?.temperature??0);
        const icon=wc===0?"☀️":wc<=3?"⛅":wc<=48?"🌫️":wc<=67?"🌧️":"⛈️";
        const desc=wc===0?"Sunny":wc<=3?"Partly Cloudy":wc<=48?"Cloudy":wc<=67?"Rainy":"Stormy";
        setWeather({temp,desc,icon});
      }).catch(()=>{});
  },[]);
  return weather;
}

// ── Sub-components ────────────────────────────────────────────────────────────
function SLabel({text}:{text:string}) { return <Text style={st.sl}>{text}</Text>; }

function BwPill({label,value,sub,color=C.acc}:{label:string;value:string;sub?:string;color?:string}) {
  return (
    <View style={[st.bwPill, S.xs]}>
      <Text style={[st.bwVal,{color}]}>{value}</Text>
      <Text style={st.bwLbl}>{label}</Text>
      {sub?<Text style={st.bwSub}>{sub}</Text>:null}
    </View>
  );
}

function TlDot({status}:{status:EvStatus}) {
  const bg = status==="past"?C.green:status==="active"?C.acc:"#D1D5DB";
  return (
    <View style={st.dotWrap}>
      <View style={[st.dot,{backgroundColor:bg},
        status==="active"&&{shadowColor:C.acc,shadowOffset:{width:0,height:0},shadowOpacity:0.4,shadowRadius:6,elevation:4}]}/>
    </View>
  );
}

function TlItem({ev,isLast}:{ev:Ev;isLast:boolean}) {
  const status=evStatus(ev), isPast=status==="past", isActive=status==="active";
  return (
    <View style={st.tlRow}>
      <View style={st.tlLeft}>
        <TlDot status={status}/>
        {!isLast&&<View style={[st.tlLine,isPast&&{backgroundColor:C.greenB}]}/>}
      </View>
      <View style={[st.tlCard,
        isActive&&{borderLeftWidth:3,borderLeftColor:C.acc,backgroundColor:C.soft},
        isPast&&{opacity:0.5},
      ]}>
        <Text style={st.tlTime}>{fmtTime(ev.start?.dateTime||ev.start?.date)}</Text>
        <Text style={[st.tlTitle,isPast&&{textDecorationLine:"line-through",color:C.ink3}]}>
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

// ── Main ──────────────────────────────────────────────────────────────────────
export default function BriefingScreen() {
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);
  const [dismissedConflict, setDismissed] = useState<string|null>(null);
  const weather = useWeather();
  const quote   = getDailyQuote();

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
  const kpis       = insRes.data?.kpis      || {};
  const insights   = insRes.data?.insights  || [];
  const pending    = missRes.data?.missions?.length ?? kpis.pending_missions ?? 0;
  const briefing   = useMemo(()=>generateBriefing(todayEvs,pending),[todayEvs,pending]);
  const activeConflict = conflicts.find(c=>`${c.a.id}-${c.b.id}`!==dismissedConflict);

  return (
    <SafeAreaView style={st.safe}>
      {/* ── Purple header ──────────────────────────────────────── */}
      <View style={st.header}>
        <View style={{flex:1}}>
          <Text style={st.headerLabel}>{greetLabel()}</Text>
          <Text style={st.headerGreeting}>{greeting()}, Tushar 👋</Text>
          <Text style={st.headerDate}>{todayLabel()}</Text>
        </View>
        <TouchableOpacity style={st.refreshBtn} onPress={refetchAll}>
          <Ionicons name="refresh-outline" size={16} color="rgba(255,255,255,0.8)"/>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={[st.content,{paddingHorizontal:hp()}]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.acc}/>}
        showsVerticalScrollIndicator={false}
      >
        {/* Weather */}
        {weather && (
          <View style={[st.weatherCard, S.sm]}>
            <Text style={{fontSize:32}}>{weather.icon}</Text>
            <View style={{flex:1}}>
              <Text style={st.weatherTemp}>{weather.temp}°F · Tampa, FL</Text>
              <Text style={st.weatherDesc}>{weather.desc} today</Text>
            </View>
            <View style={st.liveBadge}><Text style={st.liveBadgeText}>LIVE</Text></View>
          </View>
        )}

        {/* Quote */}
        <View style={[st.quoteCard, S.xs]}>
          <View style={st.quoteTop}>
            <View style={st.quoteIconWrap}><Text style={{fontSize:13}}>✦</Text></View>
            <Text style={st.quoteDay}>DAILY INSPIRATION</Text>
          </View>
          <Text style={st.quoteText}>"{quote.text}"</Text>
          <View style={{alignItems:"flex-end"}}>
            <Text style={st.quoteAuthor}>— {quote.author}</Text>
          </View>
        </View>

        {/* Conflict alert */}
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
            <View style={{flexDirection:"row",gap:8}}>
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

        {/* AI Brief */}
        <View style={[st.briefCard, S.xs]}>
          <View style={st.briefTop}>
            <View style={st.briefIconWrap}><Ionicons name="sparkles" size={13} color={C.acc}/></View>
            <Text style={st.briefLabel}>DAILY BRIEF · AI INFERENCE</Text>
            {todayEvs.length>0&&(
              <View style={st.briefBadge}><Text style={st.briefBadgeText}>{todayEvs.length} events</Text></View>
            )}
          </View>
          <Text style={st.briefText}>{briefing}</Text>
          <TouchableOpacity style={st.briefCta} onPress={()=>{
      ctxDailyBriefing(todayEvs.map(e=>e.summary||""), pending);
      router.push("/(tabs)/chat");
    }}>
            <Ionicons name="chatbubble-outline" size={12} color={C.acc}/>
            <Text style={st.briefCtaText}>Discuss with Family COO →</Text>
          </TouchableOpacity>
        </View>

        {/* Bandwidth */}
        <SLabel text="📊 ANALYTICAL BANDWIDTH · NEXT 7 DAYS"/>
        <View style={st.bwRow}>
          <BwPill label="Events"    value={String(bw.total)}              sub="this week"           color={C.acc}/>
          <BwPill label="Busiest"   value={bw.busiestDay.slice(0,3)}      sub={`${bw.busiestCount} events`} color={C.amber}/>
          <BwPill label="Free Eve." value={String(bw.freeEvenings)}       sub="available"           color={C.green}/>
          <BwPill label="Pending"   value={String(pending)}               sub="missions"            color={pending>0?C.red:C.green}/>
        </View>

        {/* Flight plan */}
        <View style={st.sRow}>
          <SLabel text="✈ TODAY'S FLIGHT PLAN"/>
          {calRes.loading&&<ActivityIndicator size="small" color={C.acc}/>}
        </View>
        {!calRes.loading&&todayEvs.length===0
          ? <View style={[st.emptyBox,S.xs]}><Text style={st.emptyText}>Runway is clear — no events today.</Text></View>
          : <View style={[st.tlContainer,S.xs]}>
              {todayEvs.map((ev,i)=><TlItem key={ev.id||i} ev={ev} isLast={i===todayEvs.length-1}/>)}
            </View>
        }

        {/* Pattern insights */}
        {insights.length>0&&(
          <View style={{gap:8}}>
            <SLabel text="PATTERN INSIGHTS"/>
            {insights.slice(0,3).map((ins:any,i:number)=>{
              const configs:Record<string,[string,string]> = {
                win:   [C.greenS, C.green],
                watch: [C.amberS, C.amber],
                tip:   [C.soft,   C.acc],
              };
              const [bg,border] = configs[ins.type] || [C.bg2, C.border2];
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

        {/* Quick actions */}
        <SLabel text="⚡ CONTEXTUAL QUICK ACTIONS"/>
        <Text style={st.actSub}>Anticipated needs based on today's schedule</Text>
        <View style={[st.actCard,S.xs]}>
          {actions.map((a,i)=>(
            <TouchableOpacity key={i}
              style={[st.actRow,i===actions.length-1&&{borderBottomWidth:0}]}
              onPress={()=>{
                const prompts:Record<string,string>={
                  "Check Tampa traffic":`What is the current traffic situation in Tampa, FL? I have ${todayEvs.length} events today. Should I leave early for any of them?`,
                  "Prep Patel Brothers list":"Help me build a Patel Brothers grocery list based on my family's Indian cuisine preferences. Include staples and any items for Paneer or lentil dishes.",
                  "Review Ideas Inbox":"Review my pending ideas and help me decide which ones to convert into missions this week.",
                };
                const key=a.label;
                const prompt=prompts[key]||`Help me with: ${key}`;
                ctxQuickAction(a.label, prompt);
                router.push("/(tabs)/chat");
              }}>
              <Text style={{fontSize:18,width:26,textAlign:"center"}}>{a.emoji}</Text>
              <Text style={st.actLabel}>{a.label}</Text>
              <Ionicons name="chevron-forward" size={13} color={C.ink3}/>
            </TouchableOpacity>
          ))}
        </View>

        <View style={{height:32}}/>
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe:        {flex:1,backgroundColor:C.bg},
  header:      {
    flexDirection:"row",alignItems:"flex-start",
    paddingHorizontal:20,paddingTop:16,paddingBottom:20,
    backgroundColor:C.acc2,
    shadowColor:"#6D28D9",shadowOffset:{width:0,height:3},shadowOpacity:0.15,shadowRadius:8,elevation:6,
  },
  headerLabel:   {fontSize:10,fontWeight:"700",color:"rgba(255,255,255,0.65)",letterSpacing:1.5,marginBottom:4},
  headerGreeting:{fontSize:22,fontWeight:"800",color:"#fff"},
  headerDate:    {fontSize:12,color:"rgba(255,255,255,0.75)",marginTop:2},
  refreshBtn:    {padding:8,borderRadius:R.sm,backgroundColor:"rgba(255,255,255,0.15)",marginTop:2},
  content:       {paddingTop:16,paddingBottom:24,gap:14},
  sl:            {fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1.2,marginBottom:8},
  sRow:          {flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:8},
  // Weather
  weatherCard:   {
    flexDirection:"row",alignItems:"center",gap:13,
    backgroundColor:"linear-gradient(135deg,#EDE9FE,#F8F7FF)" as any,
    borderRadius:R.xl,borderWidth:0.5,borderColor:C.border,
    backgroundColor:C.soft,padding:14,
  },
  weatherTemp:   {fontSize:18,fontWeight:"800",color:C.ink},
  weatherDesc:   {fontSize:12,color:C.ink2,marginTop:2},
  liveBadge:     {backgroundColor:C.greenS,borderRadius:R.full,borderWidth:0.5,borderColor:C.greenB,paddingHorizontal:9,paddingVertical:4},
  liveBadgeText: {fontSize:10,fontWeight:"700",color:C.green,letterSpacing:0.5},
  // Quote
  quoteCard:     {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,padding:15,gap:9},
  quoteTop:      {flexDirection:"row",alignItems:"center",gap:7},
  quoteIconWrap: {width:22,height:22,borderRadius:R.xs,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},
  quoteDay:      {fontSize:10,fontWeight:"700",color:C.acc,letterSpacing:1.2},
  quoteText:     {fontSize:14,color:C.ink2,lineHeight:22,fontStyle:"italic",borderLeftWidth:3,borderLeftColor:C.border,paddingLeft:12},
  quoteAuthor:   {fontSize:11,fontWeight:"700",color:C.acc},
  // Conflict
  conflictBox:   {backgroundColor:C.amberS,borderRadius:R.lg,borderWidth:0.5,borderColor:C.amberB,padding:13,gap:8},
  conflictTop:   {flexDirection:"row",alignItems:"center",gap:7},
  conflictTitle: {fontSize:12,fontWeight:"700",color:"#92400E",letterSpacing:0.3},
  conflictBody:  {fontSize:13,color:C.ink2,lineHeight:19},
  reschedBtn:    {flex:1,paddingVertical:9,backgroundColor:C.amber,borderRadius:R.sm,alignItems:"center"},
  reschedText:   {fontSize:12,fontWeight:"700",color:"#fff"},
  dismissBtn:    {paddingVertical:9,paddingHorizontal:14,borderRadius:R.sm,backgroundColor:C.bgCard,borderWidth:0.5,borderColor:C.amberB},
  dismissText:   {fontSize:12,fontWeight:"600",color:C.ink2},
  // Brief
  briefCard:     {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,padding:15,gap:9},
  briefTop:      {flexDirection:"row",alignItems:"center",gap:7},
  briefIconWrap: {width:22,height:22,borderRadius:R.xs,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},
  briefLabel:    {flex:1,fontSize:10,fontWeight:"700",color:C.acc,letterSpacing:1},
  briefBadge:    {backgroundColor:C.soft,borderRadius:R.full,paddingHorizontal:8,paddingVertical:3},
  briefBadgeText:{fontSize:11,fontWeight:"700",color:C.acc},
  briefText:     {fontSize:13,color:C.ink2,lineHeight:20},
  briefCta:      {flexDirection:"row",alignItems:"center",gap:6,alignSelf:"flex-start",backgroundColor:C.soft,borderRadius:R.full,borderWidth:0.5,borderColor:C.border,paddingVertical:7,paddingHorizontal:13},
  briefCtaText:  {fontSize:11,fontWeight:"700",color:C.acc},
  // Bandwidth
  bwRow:         {flexDirection:"row",gap:8},
  bwPill:        {flex:1,backgroundColor:C.bgCard,borderRadius:R.lg,borderWidth:0.5,borderColor:C.border2,padding:11,alignItems:"center",gap:2},
  bwVal:         {fontSize:18,fontWeight:"800"},
  bwLbl:         {fontSize:9,fontWeight:"700",color:C.ink3,textAlign:"center"},
  bwSub:         {fontSize:9,color:C.ink3,textAlign:"center"},
  // Timeline
  tlContainer:   {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,overflow:"hidden"},
  tlRow:         {flexDirection:"row"},
  tlLeft:        {width:40,alignItems:"center",paddingTop:14},
  dotWrap:       {width:20,alignItems:"center"},
  dot:           {width:10,height:10,borderRadius:5,borderWidth:2,borderColor:C.bgCard},
  tlLine:        {width:1.5,flex:1,marginTop:3,backgroundColor:C.border2},
  tlCard:        {flex:1,marginRight:12,marginTop:10,marginBottom:10,backgroundColor:C.bgCard,borderRadius:R.md,borderWidth:0.5,borderColor:C.border2,padding:10,gap:2},
  tlTime:        {fontSize:10,fontWeight:"700",color:C.ink3},
  tlTitle:       {fontSize:13,fontWeight:"700",color:C.ink},
  tlMeta:        {fontSize:11,color:C.ink3},
  activeBadge:   {flexDirection:"row",alignItems:"center",gap:4,marginTop:4,backgroundColor:C.acc,borderRadius:R.full,paddingHorizontal:8,paddingVertical:2,alignSelf:"flex-start"},
  activePulse:   {width:5,height:5,borderRadius:3,backgroundColor:"#fff"},
  activeText:    {fontSize:9,fontWeight:"700",color:"#fff",letterSpacing:0.8},
  emptyBox:      {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,padding:20},
  emptyText:     {fontSize:13,color:C.ink3,textAlign:"center"},
  // Insights
  insightRow:    {flexDirection:"row",alignItems:"flex-start",gap:10,borderRadius:R.lg,borderWidth:0.5,padding:12},
  insightHead:   {fontSize:13,fontWeight:"700",color:C.ink},
  insightSub:    {fontSize:12,color:C.ink2,lineHeight:17,marginTop:2},
  // Actions
  actSub:        {fontSize:11,color:C.ink3,marginBottom:8,marginTop:-4},
  actCard:       {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,overflow:"hidden"},
  actRow:        {flexDirection:"row",alignItems:"center",gap:11,paddingHorizontal:13,paddingVertical:12,borderBottomWidth:0.5,borderBottomColor:C.bg2},
  actLabel:      {flex:1,fontSize:13,color:C.ink2,fontWeight:"500"},
});
