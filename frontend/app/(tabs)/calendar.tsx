// app/(tabs)/calendar.tsx  —  Logistics & Planning Hub
import React, { useEffect, useMemo, useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  SafeAreaView, ActivityIndicator, Platform, Dimensions,
  RefreshControl,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { C, R, S, USER_ID } from "../constants/config";
import { useGet } from "../hooks/useApi";

const MAX_W = 820;
const pad = () => Platform.OS === "web" ? Math.max(16, (Dimensions.get("window").width - MAX_W) / 2) : 16;

type Ev = { id:string; summary?:string; location?:string;
             start?:{dateTime?:string;date?:string};
             end?:{dateTime?:string;date?:string} };

function isBirthday(e:Ev) {
  return ["happy birthday!","birthday"].includes((e.summary||"").toLowerCase().trim());
}
function parseISO(s?:string):Date|null {
  if (!s) return null; try { return new Date(s); } catch { return null; }
}
function evStart(e:Ev) { return parseISO(e.start?.dateTime||e.start?.date); }
function evEnd(e:Ev)   { return parseISO(e.end?.dateTime  ||e.end?.date); }
function fmtTime(iso?:string) {
  const d=parseISO(iso); if(!d) return "All day";
  return d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit",hour12:true});
}

// ── Week grid builder ─────────────────────────────────────────────────────────
function buildWeekGrid(events:Ev[]) {
  const today = new Date(); today.setHours(0,0,0,0);
  const days: Array<{ date:Date; label:string; short:string; dayNum:number; isToday:boolean; events:Ev[] }> = [];
  for (let i=0;i<7;i++) {
    const d = new Date(today.getTime() + i*86400000);
    const dayEvs = events.filter(e => {
      const s = evStart(e);
      return s && s.toDateString() === d.toDateString() && !isBirthday(e);
    }).sort((a,b)=>(evStart(a)?.getTime()||0)-(evStart(b)?.getTime()||0));
    days.push({
      date:d,
      label:d.toLocaleDateString("en-US",{weekday:"long"}),
      short:d.toLocaleDateString("en-US",{weekday:"short"}),
      dayNum:d.getDate(),
      isToday:i===0,
      events:dayEvs,
    });
  }
  return days;
}

// ── Chip color by event type ──────────────────────────────────────────────────
function chipColor(title:string):{bg:string;border:string} {
  const t = title.toLowerCase();
  if (t.includes("gym")||t.includes("fitness")||t.includes("judo")||t.includes("swim")||t.includes("workout"))
    return { bg:"#FEF2F2", border:"#EF4444" };
  if (t.includes("grocery")||t.includes("market")||t.includes("shop"))
    return { bg:"#ECFDF5", border:"#10B981" };
  if (t.includes("doctor")||t.includes("dentist")||t.includes("lab")||t.includes("clinic"))
    return { bg:"#EEF2FF", border:"#4F46E5" };
  if (t.includes("meeting")||t.includes("call")||t.includes("sync")||t.includes("zoom"))
    return { bg:"#EFF6FF", border:"#3B82F6" };
  if (t.includes("dinner")||t.includes("lunch")||t.includes("outing")||t.includes("restaurant"))
    return { bg:"#FFFBEB", border:"#F59E0B" };
  return { bg:"#F8FAFC", border:"#CBD5E1" };
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function BwMetric({ label, value, sub, color=C.indigo }: {
  label:string;value:string;sub?:string;color?:string;
}) {
  return (
    <View style={bm.wrap}>
      <Text style={[bm.val,{color}]}>{value}</Text>
      <Text style={bm.lbl}>{label}</Text>
      {sub?<Text style={bm.sub}>{sub}</Text>:null}
    </View>
  );
}
const bm = StyleSheet.create({
  wrap: { flex:1, alignItems:"center", paddingVertical:14, paddingHorizontal:4 },
  val:  { fontSize:18, fontWeight:"800" },
  lbl:  { fontSize:10, fontWeight:"700", color:C.inkMuted, textAlign:"center", marginTop:2 },
  sub:  { fontSize:10, color:C.inkMuted, textAlign:"center" },
});

function SectionLabel({text}:{text:string}) {
  return <Text style={sl.t}>{text}</Text>;
}
const sl = StyleSheet.create({ t:{ fontSize:10, fontWeight:"800", color:C.inkMuted, letterSpacing:1.2, marginBottom:10 } });

// ─── Main ──────────────────────────────────────────────────────────────────────
export default function CalendarScreen() {
  const router    = useRouter();
  const [refresh, setRefresh] = useState(false);
  const calRes = useGet<{events:Ev[]}>(`/api/calendar?user_id=${USER_ID}`);

  useEffect(()=>{ calRes.refetch(); },[]);
  const onRefresh = async()=>{ setRefresh(true); calRes.refetch(); setRefresh(false); };

  const events = calRes.data?.events || [];
  const grid   = useMemo(()=>buildWeekGrid(events),[events]);

  // Bandwidth stats
  const totalWeek   = grid.reduce((n,d)=>n+d.events.length,0);
  const busiestDay  = [...grid].sort((a,b)=>b.events.length-a.events.length)[0];
  const freeEvenings= grid.filter(d=>{
    return !d.events.some(e=>{ const s=evStart(e); return s && s.getHours()>=17; });
  }).length;
  const pendingDrafts = 0; // future feature

  // Conflicts
  const conflicts: Array<{a:Ev;b:Ev;day:string}> = [];
  grid.forEach(d=>{
    for(let i=0;i<d.events.length;i++){
      for(let j=i+1;j<d.events.length;j++){
        const aE=evEnd(d.events[i]),bS=evStart(d.events[j]);
        if(aE&&bS&&bS<aE)
          conflicts.push({a:d.events[i],b:d.events[j],day:d.label});
      }
    }
  });

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.header}>
        <View>
          <Text style={st.headerSub}>LOGISTICS & PLANNING HUB</Text>
          <Text style={st.headerTitle}>🗓 Calendar</Text>
        </View>
        {calRes.loading
          ? <ActivityIndicator color={C.indigo} />
          : <TouchableOpacity style={st.refreshBtn} onPress={()=>calRes.refetch()}>
              <Ionicons name="refresh-outline" size={16} color={C.inkSub}/>
            </TouchableOpacity>
        }
      </View>

      <ScrollView
        contentContainerStyle={[st.content, {paddingHorizontal:pad()}]}
        refreshControl={<RefreshControl refreshing={refresh} onRefresh={onRefresh} tintColor={C.indigo}/>}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Bandwidth Metrics ─────────────────────────────── */}
        <View>
          <SectionLabel text="📊  WEEKLY BANDWIDTH ANALYSIS" />
          <View style={[st.bwCard, S.xs]}>
            <BwMetric label="Events (7 days)" value={String(totalWeek)}
              sub="this week" color={C.indigo}/>
            <View style={st.bwDivider}/>
            <BwMetric label="Busiest Day" value={busiestDay.short}
              sub={`${busiestDay.events.length} events`} color={C.amber}/>
            <View style={st.bwDivider}/>
            <BwMetric label="Free Evenings" value={String(freeEvenings)}
              sub="evenings free" color={C.green}/>
            <View style={st.bwDivider}/>
            <BwMetric label="Conflicts" value={String(conflicts.length)}
              sub={conflicts.length>0?"needs review":"all clear"}
              color={conflicts.length>0?C.red:C.green}/>
          </View>
        </View>

        {/* ── Conflict Alerts ───────────────────────────────── */}
        {conflicts.length > 0 && (
          <View>
            <SectionLabel text="⚠️  CONFLICT RESOLUTION" />
            {conflicts.map((c,i)=>(
              <View key={i} style={st.conflictCard}>
                <View style={st.conflictTop}>
                  <Ionicons name="warning" size={14} color={C.amber}/>
                  <Text style={st.conflictTitle}>Overlap on {c.day}</Text>
                </View>
                <Text style={st.conflictBody}>
                  <Text style={{fontWeight:"700"}}>{c.a.summary}</Text>
                  {" ends at "}{fmtTime(c.a.end?.dateTime)}
                  {" — overlaps with "}
                  <Text style={{fontWeight:"700"}}>{c.b.summary}</Text>
                  {" starting "}{fmtTime(c.b.start?.dateTime)}
                </Text>
                <View style={st.conflictBtns}>
                  <TouchableOpacity style={st.reschedBtn}
                    onPress={()=>router.push("/(tabs)/chat")}>
                    <Text style={st.reschedText}>🔁 Auto-Reschedule</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={st.ignoreBtn}>
                    <Text style={st.ignoreText}>Ignore</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* ── Week-at-a-Glance Heatmap ──────────────────────── */}
        <View>
          <SectionLabel text="📅  WEEK AT A GLANCE" />
          {calRes.loading
            ? <ActivityIndicator color={C.indigo} style={{marginTop:16}}/>
            : (
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={st.heatmapRow}>
                  {grid.map((day,i)=>(
                    <View key={i} style={[st.heatmapCol, day.isToday && st.heatmapColToday]}>
                      {/* Day header */}
                      <View style={[st.heatmapHeader, day.isToday && {backgroundColor:C.indigo}]}>
                        <Text style={[st.heatmapShort, day.isToday && {color:"#FFF"}]}>{day.short}</Text>
                        <Text style={[st.heatmapNum, day.isToday && {color:"#FFF"}]}>{day.dayNum}</Text>
                      </View>
                      {/* Events */}
                      {day.events.length === 0
                        ? <View style={st.heatmapEmpty}><Text style={st.heatmapEmptyText}>Free</Text></View>
                        : day.events.map((ev,j)=>{
                          const {bg,border}=chipColor(ev.summary||"");
                          return (
                            <View key={j} style={[st.heatmapChip,{backgroundColor:bg,borderLeftColor:border}]}>
                              <Text style={st.heatmapChipTime}>{fmtTime(ev.start?.dateTime||ev.start?.date)}</Text>
                              <Text style={st.heatmapChipTitle} numberOfLines={2}>{ev.summary}</Text>
                            </View>
                          );
                        })
                      }
                    </View>
                  ))}
                </View>
              </ScrollView>
            )
          }
        </View>

        {/* ── Proactive Planning ────────────────────────────── */}
        {freeEvenings > 0 && (
          <View>
            <SectionLabel text="🪄  PROACTIVE PLANNING" />
            <View style={[st.proactiveCard, S.xs]}>
              <View style={st.proactiveHeader}>
                <Ionicons name="sparkles" size={14} color={C.indigo}/>
                <Text style={st.proactiveTitle}>AI Observation</Text>
              </View>
              <Text style={st.proactiveBody}>
                You have {freeEvenings} free evening{freeEvenings!==1?"s":""} this week.
                {" "}A good window to plan a family outing, catch a Sci-Fi film, or schedule a dinner.
              </Text>
              <View style={st.proactiveBtns}>
                <TouchableOpacity style={st.proactiveBtn}
                  onPress={()=>router.push("/(tabs)/chat")}>
                  <Text style={st.proactiveBtnText}>🎬 Suggest Options</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[st.proactiveBtn, st.proactiveBtnOutline]}
                  onPress={()=>router.push("/(tabs)/chat")}>
                  <Text style={[st.proactiveBtnText,{color:C.inkSub}]}>🍽 Dining Ideas</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        )}

        {/* ── Full Event List ───────────────────────────────── */}
        <View>
          <SectionLabel text="UPCOMING EVENTS" />
          <View style={[st.eventList, S.xs]}>
            {events
              .filter(e => !isBirthday(e))
              .filter(e => {
                const s = evStart(e);
                return s && s >= new Date(new Date().setHours(0,0,0,0));
              })
              .slice(0, 20)
              .map((ev,i,arr)=>{
              const s = evStart(ev);
              const dateStr = s?.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"});
              const {bg,border}=chipColor(ev.summary||"");
              return (
                <View key={ev.id||i}
                  style={[st.evRow,i===arr.length-1&&{borderBottomWidth:0}]}>
                  <View style={[st.evAccent,{backgroundColor:border}]}/>
                  <View style={{flex:1, gap:2}}>
                    <Text style={st.evTitle} numberOfLines={1}>{ev.summary||"Untitled"}</Text>
                    <Text style={st.evMeta}>
                      {dateStr}  ·  {fmtTime(ev.start?.dateTime)}
                      {ev.location ? `  ·  📍 ${ev.location}` : ""}
                    </Text>
                  </View>
                </View>
              );
            })}
            {events.filter(e=>!isBirthday(e)).length === 0 && (
              <Text style={st.emptyText}>No upcoming events. Calendar is clear.</Text>
            )}
          </View>
        </View>

        <View style={{height:36}}/>
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe: {flex:1, backgroundColor:C.bg},
  header: {
    flexDirection:"row", alignItems:"center", justifyContent:"space-between",
    paddingHorizontal:20, paddingVertical:14,
    borderBottomWidth:1, borderBottomColor:C.border,
    shadowColor:"#0F172A",shadowOffset:{width:0,height:1},shadowOpacity:0.05,shadowRadius:4,elevation:2,
  },
  headerSub:   {fontSize:10, fontWeight:"800", color:C.inkMuted, letterSpacing:1},
  headerTitle: {fontSize:20, fontWeight:"800", color:C.ink, marginTop:2},
  refreshBtn:  {padding:8, borderRadius:R.sm, backgroundColor:C.bgInput},
  content:     {paddingTop:18, paddingBottom:24, gap:22},

  bwCard: {
    flexDirection:"row", backgroundColor:C.bgCard,
    borderRadius:R.lg, borderWidth:1, borderColor:C.border, overflow:"hidden",
  },
  bwDivider: {width:1, backgroundColor:C.border},

  conflictCard: {
    backgroundColor:C.amberSoft, borderRadius:R.md,
    borderWidth:1, borderColor:C.amberBorder, padding:14, gap:10, marginBottom:10,
  },
  conflictTop:  {flexDirection:"row",alignItems:"center",gap:7},
  conflictTitle:{fontSize:12,fontWeight:"800",color:"#92400E",letterSpacing:0.3},
  conflictBody: {fontSize:13,color:C.inkMid,lineHeight:19},
  conflictBtns: {flexDirection:"row",gap:8},
  reschedBtn:   {flex:1,paddingVertical:9,backgroundColor:C.amber,borderRadius:R.sm,alignItems:"center"},
  reschedText:  {fontSize:12,fontWeight:"800",color:"#FFFFFF"},
  ignoreBtn:    {paddingVertical:9,paddingHorizontal:14,borderRadius:R.sm,backgroundColor:C.bgCard,borderWidth:1,borderColor:C.amberBorder},
  ignoreText:   {fontSize:12,fontWeight:"600",color:C.inkSub},

  heatmapRow:      {flexDirection:"row",gap:8,paddingBottom:4},
  heatmapCol:      {width:110,gap:6,backgroundColor:C.bgCard,borderRadius:R.md,borderWidth:1,borderColor:C.border,overflow:"hidden"},
  heatmapColToday: {borderColor:C.indigo,borderWidth:1.5},
  heatmapHeader:   {alignItems:"center",paddingVertical:8,backgroundColor:C.bgInput},
  heatmapShort:    {fontSize:11,fontWeight:"800",color:C.inkSub},
  heatmapNum:      {fontSize:18,fontWeight:"800",color:C.ink},
  heatmapEmpty:    {margin:6,padding:10,backgroundColor:C.bgInput,borderRadius:R.sm,borderWidth:1,borderStyle:"dashed",borderColor:C.slateLight,alignItems:"center"},
  heatmapEmptyText:{fontSize:11,color:C.inkMuted,fontWeight:"700"},
  heatmapChip:     {margin:6,marginTop:0,padding:7,borderRadius:R.xs,borderLeftWidth:3},
  heatmapChipTime: {fontSize:10,fontWeight:"800",color:C.inkSub},
  heatmapChipTitle:{fontSize:11,fontWeight:"700",color:C.ink,lineHeight:14,marginTop:2},

  proactiveCard: {backgroundColor:C.bgCard,borderRadius:R.lg,borderWidth:1,borderColor:C.indigoBorder,padding:16,gap:12},
  proactiveHeader:{flexDirection:"row",alignItems:"center",gap:7},
  proactiveTitle: {fontSize:12,fontWeight:"800",color:C.indigo,letterSpacing:0.3},
  proactiveBody:  {fontSize:13,color:C.inkMid,lineHeight:19},
  proactiveBtns:  {flexDirection:"row",gap:8},
  proactiveBtn:   {flex:1,paddingVertical:9,backgroundColor:C.indigo,borderRadius:R.sm,alignItems:"center"},
  proactiveBtnOutline: {backgroundColor:C.bgInput,borderWidth:1,borderColor:C.border},
  proactiveBtnText:{fontSize:12,fontWeight:"700",color:"#FFFFFF"},

  eventList:  {backgroundColor:C.bgCard,borderRadius:R.lg,borderWidth:1,borderColor:C.border,overflow:"hidden"},
  evRow:      {flexDirection:"row",alignItems:"center",gap:12,paddingVertical:12,paddingHorizontal:14,borderBottomWidth:1,borderBottomColor:C.borderSoft},
  evAccent:   {width:3,height:36,borderRadius:2},
  evTitle:    {fontSize:14,fontWeight:"700",color:C.ink},
  evMeta:     {fontSize:11,color:C.inkMuted},
  emptyText:  {fontSize:13,color:C.inkMuted,textAlign:"center",padding:20},
});
