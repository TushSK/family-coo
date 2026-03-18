// app/(tabs)/calendar.tsx  —  Calendar (v3 Lavender)
import React, { useEffect, useCallback, useMemo, useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  SafeAreaView, ActivityIndicator, Platform, Dimensions,
  RefreshControl, TextInput, Modal,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useFocusEffect } from "expo-router";
import { ctxDiningIdeas, ctxSuggestActivities, ctxRescheduleConflict } from "../context/ChatContextStore";
import { C, R, S, USER_ID } from "../constants/config";
import { useGet } from "../hooks/useApi";

const MAX_W = 820;
const hp = () => Platform.OS==="web" ? Math.max(16,(Dimensions.get("window").width-MAX_W)/2) : 16;

type Ev = { id:string; summary?:string; location?:string;
             start?:{dateTime?:string;date?:string};
             end?:{dateTime?:string;date?:string} };

function isBirthday(e:Ev) { return ["happy birthday!","birthday"].includes((e.summary||"").toLowerCase().trim()); }
function parseISO(s?:string):Date|null { if(!s)return null; try{return new Date(s);}catch{return null;} }
function evStart(e:Ev) { return parseISO(e.start?.dateTime||e.start?.date); }
function evEnd(e:Ev)   { return parseISO(e.end?.dateTime  ||e.end?.date); }
function fmtTime(iso?:string) {
  const d=parseISO(iso); if(!d)return "All day";
  return d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit",hour12:true});
}

function buildWeekGrid(events:Ev[]) {
  const today=new Date(); today.setHours(0,0,0,0);

  // Start from Sunday of the current week so the full 7-day week is always
  // visible — including past days like Sunday, Monday, Tuesday.
  // Without this, the grid starts from today and the first half of the week
  // is invisible even though those events exist in Google Calendar.
  const dayOfWeek = today.getDay(); // 0=Sun, 1=Mon ... 6=Sat
  const weekStart = new Date(today.getTime() - dayOfWeek * 86400000);

  return Array.from({length:7},(_,i)=>{
    const d=new Date(weekStart.getTime()+i*86400000);
    const isToday=d.toDateString()===today.toDateString();
    const isPast=d<today;
    const dayEvs=events.filter(e=>{
      const s=evStart(e); return s&&s.toDateString()===d.toDateString()&&!isBirthday(e);
    }).sort((a,b)=>(evStart(a)?.getTime()||0)-(evStart(b)?.getTime()||0));
    return {
      date:d, short:d.toLocaleDateString("en-US",{weekday:"short"}),
      dayNum:d.getDate(), isToday, isPast, events:dayEvs,
    };
  });
}

function chipStyle(title:string):{bg:string;border:string} {
  const t=title.toLowerCase();
  if(t.includes("gym")||t.includes("fitness")||t.includes("judo")||t.includes("swim"))
    return {bg:C.redS,border:C.red};
  if(t.includes("grocery")||t.includes("market"))
    return {bg:C.greenS,border:C.green};
  if(t.includes("doctor")||t.includes("dentist")||t.includes("lab"))
    return {bg:C.soft,border:C.acc};
  if(t.includes("meeting")||t.includes("call")||t.includes("sync"))
    return {bg:C.soft,border:C.acc};
  if(t.includes("dinner")||t.includes("lunch")||t.includes("outing"))
    return {bg:C.amberS,border:C.amber};
  return {bg:C.bg2,border:C.border};
}

const ACT_OPTS = [
  {val:"family-outing",    label:"Family outing"},
  {val:"date-night",       label:"Date night — Tushar & Sonam"},
  {val:"kids-activity",    label:"Kids activity — Drishti"},
  {val:"outdoor-adventure",label:"Outdoor adventure"},
  {val:"dining-out",       label:"Dining out"},
  {val:"cultural-visit",   label:"Museum / cultural visit"},
  {val:"sports-fitness",   label:"Sports & fitness"},
  {val:"home-project",     label:"Home project"},
];

const GEN_OPTS:Record<string,Array<{icon:string;title:string;desc:string;dist:string;time:string;fit:string;ctx:string}>> = {
  "family-outing":[
    {icon:"🦁",title:"Busch Gardens Tampa",desc:"Theme park — rides + animals. Great for Drishti.",dist:"12 mi",time:"3–5 hrs",fit:"High",ctx:"Tell me more about Busch Gardens Tampa for a family outing this Saturday. We have 9am–1pm, 30-mile radius, sunny 78°F weather."},
    {icon:"🌿",title:"Hillsborough River State Park",desc:"Hiking trails + picnic. Free for kids under 6.",dist:"24 mi",time:"2–3 hrs",fit:"High",ctx:"Tell me more about Hillsborough River State Park for a family hike Saturday. Drishti is coming — what trails work for kids?"},
    {icon:"🎳",title:"Ybor City + Splitsville",desc:"Lunch at Columbia + bowling.",dist:"8 mi",time:"2–3 hrs",fit:"Medium",ctx:"Tell me more about an Ybor City outing — lunch at Columbia then bowling at Splitsville. Cost and timing for a family of 3?"},
  ],
  "date-night":[
    {icon:"🍽️",title:"Bern's Steak House",desc:"Tampa's iconic fine dining. Book ahead.",dist:"4 mi",time:"2 hrs",fit:"High",ctx:"Tell me more about Bern's Steak House for a date night this Saturday. Price range, dress code, availability?"},
    {icon:"🎬",title:"Rooftop Cinema + Dinner",desc:"Outdoor screening + Indian takeout.",dist:"6 mi",time:"3 hrs",fit:"High",ctx:"Tell me about rooftop cinema options in Tampa this Saturday evening — what's screening and cost?"},
  ],
  "outdoor-adventure":[
    {icon:"🏄",title:"Caladesi Island Kayaking",desc:"State park kayak trail through mangroves.",dist:"28 mi",time:"3–4 hrs",fit:"High",ctx:"Tell me about kayaking at Caladesi Island this Saturday. Rentals, trail length, beginner-friendly?"},
    {icon:"🚴",title:"Pinellas Trail Cycling",desc:"46-mile paved trail. Rent bikes at trailhead.",dist:"22 mi",time:"2–3 hrs",fit:"High",ctx:"Tell me about cycling on the Pinellas Trail — best start point from Tampa, bike rentals, most scenic section?"},
  ],
  "dining-out":[
    {icon:"🍲",title:"Patel Brothers + Swadesi",desc:"Grocery run then authentic South Indian lunch.",dist:"6 mi",time:"1.5 hrs",fit:"High",ctx:"Tell me about combining Patel Brothers grocery run with lunch at Swadesi this Saturday. Opening hours and must-order dishes?"},
    {icon:"🍜",title:"Noodle & Co — Ybor City",desc:"Quick Asian fusion. Kid-friendly menu.",dist:"8 mi",time:"1 hr",fit:"High",ctx:"Tell me about Noodle & Co in Ybor City — good for families, must-order dishes, Saturday hours?"},
  ],
};

function SLabel({text}:{text:string}){ return <Text style={st.sl}>{text}</Text>; }

export default function CalendarScreen() {
  const router  = useRouter();
  const [refresh,    setRefresh]    = useState(false);
  const [actVal,     setActVal]     = useState("family-outing");
  const [genDone,    setGenDone]    = useState(false);
  const [showAdd,    setShowAdd]    = useState(false);
  const [showSignals,setShowSignals] = useState(false);
  const [signals, setSignals] = useState({
    slot:"Saturday 9:00 AM – 1:00 PM",
    radius:"30",
    budget:"Under $50",
    energy:"Moderate",
    kidFriendly:"Yes — Drishti is coming",
  });
  const [chatCtx,    setChatCtx]    = useState<{title:string;ctx:string}|null>(null);

  const calRes = useGet<{events:Ev[]}>(`/api/calendar?user_id=${USER_ID}`);

  // Refetch every time the Calendar tab comes into focus
  // This ensures new events added via Chat appear immediately
  useFocusEffect(
    useCallback(() => {
      calRes.refetch();
    }, [])
  );
  const onRefresh=async()=>{ setRefresh(true); calRes.refetch(); setRefresh(false); };

  const events = calRes.data?.events||[];
  const grid   = useMemo(()=>buildWeekGrid(events),[events]);

  const totalWeek   = grid.reduce((n,d)=>n+d.events.length,0);
  const busiestDay  = [...grid].sort((a,b)=>b.events.length-a.events.length)[0];
  // Free evenings: only count today + future days (past evenings can't be planned)
  const freeEvenings= grid.filter(d=>!d.isPast&&!d.events.some(e=>{const s=evStart(e);return s&&s.getHours()>=17;})).length;
  const conflicts:Array<{a:Ev;b:Ev;day:string}>=[];
  grid.forEach(d=>{ for(let i=0;i<d.events.length;i++) for(let j=i+1;j<d.events.length;j++){
    const aE=evEnd(d.events[i]),bS=evStart(d.events[j]);
    if(aE&&bS&&bS<aE) conflicts.push({a:d.events[i],b:d.events[j],day:d.short});
  }});

  const opts = GEN_OPTS[actVal]||GEN_OPTS["family-outing"];

  function openMoreDetails(opt:{title:string;ctx:string}) {
    setChatCtx(opt); router.push("/(tabs)/chat");
  }
  function tapEvent(ev:Ev) {
    setChatCtx({title:ev.summary||"Event",ctx:`Tell me more about "${ev.summary}" — full details, preparation needed, and any relevant tips.`});
    router.push("/(tabs)/chat");
  }

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.header}>
        <View>
          <Text style={st.headerSub}>LOGISTICS & PLANNING HUB</Text>
          <Text style={st.headerTitle}>Calendar</Text>
        </View>
        <View style={{flexDirection:"row",gap:8,alignItems:"center"}}>
          <View style={{flexDirection:"row",gap:5}}>
            {[["T",C.tushar],["S",C.sonam],["D",C.drishti],["F",C.family]].map(([l,c])=>(
              <View key={l} style={[st.memberBadge,{borderColor:c as string}]}>
                <Text style={[st.memberBadgeText,{color:c as string}]}>{l}</Text>
              </View>
            ))}
          </View>
          <TouchableOpacity style={[st.addBtn,S.sm]} onPress={()=>setShowAdd(true)}>
            <Ionicons name="add" size={16} color="#fff"/>
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={[st.content,{paddingHorizontal:hp()}]}
        refreshControl={<RefreshControl refreshing={refresh} onRefresh={onRefresh} tintColor={C.acc}/>}
        showsVerticalScrollIndicator={false}
      >
        {/* Bandwidth */}
        <View style={[st.bwCard,S.xs]}>
          {[
            [String(totalWeek),"Events","var(--acc)" as any,C.acc],
            [busiestDay.short,"Busiest",null,C.amber],
            [String(freeEvenings),"Free Eve.",null,C.green],
            [String(conflicts.length),"Conflicts",null,conflicts.length>0?C.red:C.green],
          ].map(([v,l,,c],i)=>(
            <View key={i} style={[st.bwBox,i<3&&{borderRightWidth:0.5,borderRightColor:C.bg2}]}>
              <Text style={[st.bwVal,{color:c as string}]}>{v}</Text>
              <Text style={st.bwLbl}>{l}</Text>
            </View>
          ))}
        </View>

        {/* Conflict alerts */}
        {conflicts.length>0&&conflicts.map((c,i)=>(
          <View key={i} style={st.conflictCard}>
            <View style={{flexDirection:"row",alignItems:"center",gap:7}}>
              <Ionicons name="warning" size={14} color={C.amber}/>
              <Text style={st.conflictTitle}>Overlap on {c.day}</Text>
            </View>
            <Text style={st.conflictBody}>
              <Text style={{fontWeight:"700"}}>{c.a.summary}</Text>
              {" overlaps with "}
              <Text style={{fontWeight:"700"}}>{c.b.summary}</Text>
            </Text>
            <View style={{flexDirection:"row",gap:8}}>
              <TouchableOpacity style={st.reschedBtn} onPress={()=>{
                conflicts.length>0&&ctxRescheduleConflict(conflicts[0].a.summary||"Event A",conflicts[0].b.summary||"Event B",busiestDay.short);
                router.push("/(tabs)/chat");
              }}>
                <Text style={st.reschedText}>🔁 Auto-Reschedule</Text>
              </TouchableOpacity>
              <TouchableOpacity style={st.ignoreBtn}>
                <Text style={st.ignoreText}>Ignore</Text>
              </TouchableOpacity>
            </View>
          </View>
        ))}

        {/* Week heatmap */}
        <SLabel text="📅 WEEK AT A GLANCE"/>
        {calRes.loading
          ? <ActivityIndicator color={C.acc} style={{marginTop:8}}/>
          : (
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={st.heatmapRow}>
                {grid.map((day,i)=>(
                  <View key={i} style={[
                    st.heatmapCol,
                    day.isToday&&{borderColor:C.acc,borderWidth:1.5},
                    day.isPast&&{opacity:0.6},
                  ]}>
                    <View style={[
                      st.heatmapHeader,
                      day.isToday&&{backgroundColor:C.acc},
                      day.isPast&&!day.isToday&&{backgroundColor:C.border2},
                    ]}>
                      <Text style={[st.heatmapShort,day.isToday&&{color:"#fff"}]}>{day.short}</Text>
                      <Text style={[st.heatmapNum,day.isToday&&{color:"#fff"}]}>{day.dayNum}</Text>
                    </View>
                    <View style={st.heatmapBody}>
                      {day.events.length===0
                        ? <View style={st.heatmapEmpty}><Text style={st.heatmapEmptyText}>Free</Text></View>
                        : day.events.map((ev,j)=>{
                          const {bg,border}=chipStyle(ev.summary||"");
                          return (
                            <TouchableOpacity key={j}
                              style={[st.heatmapChip,{backgroundColor:bg,borderLeftColor:border}]}
                              onPress={()=>tapEvent(ev)}>
                              <Text style={st.heatmapChipTime}>{fmtTime(ev.start?.dateTime||ev.start?.date)}</Text>
                              <Text style={st.heatmapChipTitle} numberOfLines={2}>{ev.summary}</Text>
                            </TouchableOpacity>
                          );
                        })
                      }
                    </View>
                  </View>
                ))}
              </View>
            </ScrollView>
          )
        }

        {/* Weekend Planner */}
        <SLabel text="🗓️ WEEKEND PLANNER"/>
        <View style={[st.plannerCard,S.xs]}>
          {/* Context strip */}
          <View style={st.plannerCtx}>
            <Text style={st.plannerCtxLabel}>CURRENT CONTEXT</Text>
            {[["⏰",signals.slot],["🌍",`Travel radius: ${signals.radius} miles`],["☀️","Sunny, 78°F"]].map(([e,t])=>(
              <View key={t} style={{flexDirection:"row",alignItems:"center",gap:8,marginBottom:4}}>
                <Text style={{fontSize:13}}>{e}</Text>
                <Text style={st.plannerCtxText}>{t}</Text>
              </View>
            ))}
          </View>
          {/* Controls */}
          <View style={{padding:13}}>
            <Text style={st.plannerLabel}>WHAT ARE YOU PLANNING?</Text>
            <View style={st.selectWrap}>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={{flexDirection:"row",gap:7}}>
                  {ACT_OPTS.map(o=>(
                    <TouchableOpacity key={o.val}
                      style={[st.actChip, actVal===o.val&&st.actChipSel]}
                      onPress={()=>{setActVal(o.val);setGenDone(false);}}>
                      <Text style={[st.actChipText, actVal===o.val&&{color:C.acc,fontWeight:"700"}]}>{o.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>
            </View>
            <View style={{flexDirection:"row",gap:8,marginTop:12}}>
              <TouchableOpacity style={[st.genBtn,S.sm,{flex:2}]} onPress={()=>setGenDone(true)}>
                <Text style={st.genBtnText}>Generate options</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[st.signalsBtn,{flex:1}]} onPress={()=>setShowSignals(true)}>
                <Text style={st.signalsBtnText}>Edit signals</Text>
              </TouchableOpacity>
            </View>

            {/* Generated options */}
            {genDone&&(
              <View style={{marginTop:14,gap:9}}>
                <Text style={st.sl}>AI SUGGESTIONS</Text>
                {opts.map((o,i)=>(
                  <View key={i} style={[st.optCard,S.xs]}>
                    <View style={{flexDirection:"row",alignItems:"flex-start",gap:10,marginBottom:8}}>
                      <View style={st.optIcon}><Text style={{fontSize:18}}>{o.icon}</Text></View>
                      <View style={{flex:1,minWidth:0}}>
                        <View style={{flexDirection:"row",alignItems:"center",justifyContent:"space-between",gap:6,marginBottom:3}}>
                          <Text style={st.optTitle}>{o.title}</Text>
                          <View style={[st.fitBadge,{backgroundColor:o.fit==="High"?C.greenS:C.amberS}]}>
                            <Text style={[st.fitText,{color:o.fit==="High"?C.green:C.amber}]}>{o.fit} fit</Text>
                          </View>
                        </View>
                        <Text style={st.optDesc}>{o.desc}</Text>
                        <View style={{flexDirection:"row",gap:10,marginTop:5}}>
                          <Text style={st.optMeta}>📍 {o.dist}</Text>
                          <Text style={st.optMeta}>⏱ {o.time}</Text>
                        </View>
                      </View>
                    </View>
                    <View style={{flexDirection:"row",gap:8,borderTopWidth:0.5,borderTopColor:C.bg2,paddingTop:9}}>
                      <TouchableOpacity style={st.addCalBtn}>
                        <Text style={st.addCalText}>Add to Calendar</Text>
                      </TouchableOpacity>
                      <TouchableOpacity style={st.moreBtn} onPress={()=>openMoreDetails(o)}>
                        <Ionicons name="chatbubble-outline" size={11} color={C.acc}/>
                        <Text style={st.moreBtnText}>More details</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))}
              </View>
            )}
          </View>
        </View>

        {/* Proactive planning */}
        {freeEvenings>0&&(
          <View style={[st.proactiveCard,S.xs]}>
            <View style={{flexDirection:"row",alignItems:"center",gap:7,marginBottom:7}}>
              <Ionicons name="sparkles" size={14} color={C.acc}/>
              <Text style={st.proactiveTitle}>AI Observation</Text>
            </View>
            <Text style={st.proactiveBody}>
              You have {freeEvenings} free evening{freeEvenings!==1?"s":""} this week.{" "}
              A good window to plan a family outing, catch a film, or schedule dinner.
            </Text>
            <View style={{flexDirection:"row",gap:8,marginTop:10}}>
              <TouchableOpacity style={st.genBtn} onPress={()=>router.push("/(tabs)/chat")}>
                <Text style={st.genBtnText}>🎬 Suggest Options</Text>
              </TouchableOpacity>
              <TouchableOpacity style={st.signalsBtn} onPress={()=>router.push("/(tabs)/chat")}>
                <Text style={st.signalsBtnText}>🍽 Dining Ideas</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* Events list */}
        <SLabel text="UPCOMING EVENTS"/>
        <View style={[st.evList,S.xs]}>
          {events.filter(e=>!isBirthday(e)).filter(e=>{
            const s=evStart(e); return s&&s>=new Date(new Date().setHours(0,0,0,0));
          }).slice(0,20).map((ev,i,arr)=>{
            const {border}=chipStyle(ev.summary||"");
            return (
              <TouchableOpacity key={ev.id||i}
                style={[st.evRow,i===arr.length-1&&{borderBottomWidth:0}]}
                onPress={()=>tapEvent(ev)}>
                <View style={[st.evAccent,{backgroundColor:border}]}/>
                <View style={{flex:1,gap:2}}>
                  <Text style={st.evTitle} numberOfLines={1}>{ev.summary||"Untitled"}</Text>
                  <Text style={st.evMeta}>
                    {evStart(ev)?.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"})}
                    {"  ·  "}{fmtTime(ev.start?.dateTime)}
                    {ev.location?`  ·  📍 ${ev.location}`:""}
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={13} color={C.ink3}/>
              </TouchableOpacity>
            );
          })}
          {events.filter(e=>!isBirthday(e)).length===0&&(
            <Text style={st.emptyText}>No upcoming events. Calendar is clear.</Text>
          )}
        </View>

        <View style={{height:32}}/>
      </ScrollView>

      {/* Edit Signals Modal */}
      <Modal visible={showSignals} animationType="slide" transparent>
        <View style={st.modalOverlay}>
          <View style={st.signalsSheet}>
            <View style={st.sheetHandle}/>
            <View style={{flexDirection:"row",alignItems:"center",marginBottom:18}}>
              <View style={{flex:1}}>
                <Text style={st.modalSub}>WEEKEND PLANNER</Text>
                <Text style={st.modalTitle}>Edit Planning Signals</Text>
              </View>
              <TouchableOpacity style={st.modalBack} onPress={()=>setShowSignals(false)}>
                <Ionicons name="close" size={18} color={C.ink2}/>
              </TouchableOpacity>
            </View>
            <ScrollView showsVerticalScrollIndicator={false}>
              {/* Time slot */}
              <Text style={st.fieldLabel}>PREFERRED TIME SLOT</Text>
              <View style={st.signalsPickerWrap}>
                {["Saturday 9:00 AM – 1:00 PM","Saturday 2:00 PM – 6:00 PM","Sunday 9:00 AM – 1:00 PM","Sunday 2:00 PM – 6:00 PM","Full Saturday","Full Sunday"].map(o=>(
                  <TouchableOpacity key={o}
                    style={[st.sigChip, signals.slot===o&&st.sigChipSel]}
                    onPress={()=>setSignals(s=>({...s,slot:o}))}>
                    <Text style={[st.sigChipText, signals.slot===o&&{color:C.acc,fontWeight:"700"}]}>{o}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              {/* Travel radius */}
              <Text style={[st.fieldLabel,{marginTop:14}]}>TRAVEL RADIUS</Text>
              <View style={st.signalsPickerWrap}>
                {[["10","Local only"],["20","Up to 20 mi"],["30","Day trip"],["50","Extended"],["100","Road trip"]].map(([v,l])=>(
                  <TouchableOpacity key={v}
                    style={[st.sigChip, signals.radius===v&&st.sigChipSel]}
                    onPress={()=>setSignals(s=>({...s,radius:v}))}>
                    <Text style={[st.sigChipText, signals.radius===v&&{color:C.acc,fontWeight:"700"}]}>{l} ({v} mi)</Text>
                  </TouchableOpacity>
                ))}
              </View>
              {/* Budget */}
              <Text style={[st.fieldLabel,{marginTop:14}]}>BUDGET RANGE</Text>
              <View style={st.signalsPickerWrap}>
                {["Free","Under $50","$50–$150","$150–$300","No limit"].map(o=>(
                  <TouchableOpacity key={o}
                    style={[st.sigChip, signals.budget===o&&st.sigChipSel]}
                    onPress={()=>setSignals(s=>({...s,budget:o}))}>
                    <Text style={[st.sigChipText, signals.budget===o&&{color:C.acc,fontWeight:"700"}]}>{o}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              {/* Energy */}
              <Text style={[st.fieldLabel,{marginTop:14}]}>ENERGY LEVEL</Text>
              <View style={st.signalsPickerWrap}>
                {["Relaxed","Moderate","Active & adventurous"].map(o=>(
                  <TouchableOpacity key={o}
                    style={[st.sigChip, signals.energy===o&&st.sigChipSel]}
                    onPress={()=>setSignals(s=>({...s,energy:o}))}>
                    <Text style={[st.sigChipText, signals.energy===o&&{color:C.acc,fontWeight:"700"}]}>{o}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              {/* Kid friendly */}
              <Text style={[st.fieldLabel,{marginTop:14}]}>KID-FRIENDLY</Text>
              <View style={st.signalsPickerWrap}>
                {["Yes — Drishti is coming","No — adults only"].map(o=>(
                  <TouchableOpacity key={o}
                    style={[st.sigChip, signals.kidFriendly===o&&st.sigChipSel]}
                    onPress={()=>setSignals(s=>({...s,kidFriendly:o}))}>
                    <Text style={[st.sigChipText, signals.kidFriendly===o&&{color:C.acc,fontWeight:"700"}]}>{o}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <TouchableOpacity style={[st.genBtn,{marginTop:18,marginBottom:8}]} onPress={()=>setShowSignals(false)}>
                <Text style={st.genBtnText}>Save Signals ✓</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Add event modal */}
      <Modal visible={showAdd} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={{flex:1,backgroundColor:C.bg}}>
          <View style={st.modalHeader}>
            <TouchableOpacity onPress={()=>setShowAdd(false)} style={st.modalBack}>
              <Ionicons name="chevron-down" size={20} color={C.acc}/>
            </TouchableOpacity>
            <View style={{flex:1}}>
              <Text style={st.modalSub}>NEW EVENT</Text>
              <Text style={st.modalTitle}>Add to Calendar</Text>
            </View>
          </View>
          <ScrollView contentContainerStyle={{padding:16,gap:14}}>
            {[["TITLE","e.g. Drishti Judo Class","default" as const],["DATE","","default" as const],["LOCATION (OPTIONAL)","e.g. EōS Fitness","default" as const]].map(([l,p,k])=>(
              <View key={l}>
                <Text style={st.fieldLabel}>{l}</Text>
                <TextInput placeholder={p} placeholderTextColor={C.ink3}
                  style={st.fieldInput} keyboardType={k}/>
              </View>
            ))}
            <View>
              <Text style={st.fieldLabel}>FAMILY MEMBER</Text>
              <View style={{flexDirection:"row",flexWrap:"wrap",gap:8,marginTop:6}}>
                {["All Family","Tushar","Sonam","Drishti"].map(m=>(
                  <TouchableOpacity key={m} style={st.memberPill}>
                    <Text style={st.memberPillText}>{m}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
            <View style={{flexDirection:"row",gap:8,marginTop:8}}>
              <TouchableOpacity style={[st.genBtn,S.sm,{flex:1}]} onPress={()=>setShowAdd(false)}>
                <Text style={st.genBtnText}>Add to Calendar</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[st.signalsBtn,{flex:1}]} onPress={()=>{setShowAdd(false);router.push("/(tabs)/chat");}}>
                <Text style={st.signalsBtnText}>Use Chat</Text>
              </TouchableOpacity>
            </View>
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe:   {flex:1,backgroundColor:C.bg},
  header: {
    flexDirection:"row",alignItems:"center",justifyContent:"space-between",
    paddingHorizontal:18,paddingVertical:13,
    backgroundColor:C.bgCard,borderBottomWidth:0.5,borderBottomColor:C.border2,
    shadowColor:"#6D28D9",shadowOffset:{width:0,height:1},shadowOpacity:0.06,shadowRadius:4,elevation:2,
  },
  headerSub:   {fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1},
  headerTitle: {fontSize:18,fontWeight:"800",color:C.ink,marginTop:1},
  memberBadge: {width:22,height:22,borderRadius:11,borderWidth:1.5,alignItems:"center",justifyContent:"center"},
  memberBadgeText:{fontSize:9,fontWeight:"800"},
  addBtn:      {width:32,height:32,borderRadius:10,backgroundColor:C.acc2,alignItems:"center",justifyContent:"center"},
  content:     {paddingTop:14,paddingBottom:24,gap:14},
  sl:          {fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1.2,marginBottom:8},
  // Bandwidth
  bwCard:      {flexDirection:"row",backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,overflow:"hidden"},
  bwBox:       {flex:1,paddingVertical:12,alignItems:"center"},
  bwVal:       {fontSize:17,fontWeight:"800"},
  bwLbl:       {fontSize:9,color:C.ink3,marginTop:2,fontWeight:"700"},
  // Conflict
  conflictCard:{backgroundColor:C.amberS,borderRadius:R.lg,borderWidth:0.5,borderColor:C.amberB,padding:13,gap:8},
  conflictTitle:{fontSize:12,fontWeight:"700",color:"#92400E"},
  conflictBody: {fontSize:13,color:C.ink2,lineHeight:18},
  reschedBtn:   {flex:1,paddingVertical:9,backgroundColor:C.amber,borderRadius:R.sm,alignItems:"center"},
  reschedText:  {fontSize:12,fontWeight:"700",color:"#fff"},
  ignoreBtn:    {paddingVertical:9,paddingHorizontal:14,borderRadius:R.sm,backgroundColor:C.bgCard,borderWidth:0.5,borderColor:C.amberB},
  ignoreText:   {fontSize:12,fontWeight:"600",color:C.ink2},
  // Heatmap
  heatmapRow:       {flexDirection:"row",gap:7,paddingBottom:4},
  heatmapCol:       {width:105,borderRadius:10,borderWidth:0.5,borderColor:C.border2,backgroundColor:C.bgCard,overflow:"hidden"},
  heatmapHeader:    {alignItems:"center",paddingVertical:7,backgroundColor:C.bg2},
  heatmapShort:     {fontSize:10,fontWeight:"700",color:C.ink2},
  heatmapNum:       {fontSize:17,fontWeight:"800",color:C.ink},
  heatmapBody:      {padding:5,gap:3,minHeight:48},
  heatmapEmpty:     {flex:1,backgroundColor:C.bg2,borderRadius:5,alignItems:"center",justifyContent:"center",padding:8,borderWidth:0.5,borderStyle:"dashed",borderColor:C.border},
  heatmapEmptyText: {fontSize:9,color:C.ink3,fontWeight:"600"},
  heatmapChip:      {borderRadius:4,padding:5,borderLeftWidth:2},
  heatmapChipTime:  {fontSize:9,fontWeight:"700",color:C.ink2},
  heatmapChipTitle: {fontSize:10,fontWeight:"700",color:C.ink,lineHeight:13,marginTop:1},
  // Planner
  plannerCard:  {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border,overflow:"hidden"},
  plannerCtx:   {backgroundColor:C.soft,padding:13,borderBottomWidth:0.5,borderBottomColor:C.border},
  plannerCtxLabel:{fontSize:10,fontWeight:"700",color:C.acc,letterSpacing:1,marginBottom:8},
  plannerCtxText: {fontSize:12,color:C.ink2},
  plannerLabel:   {fontSize:11,fontWeight:"700",color:C.ink3,marginBottom:9},
  selectWrap:     {marginBottom:4},
  actChip:        {paddingHorizontal:13,paddingVertical:8,borderRadius:R.full,borderWidth:0.5,borderColor:C.border2,backgroundColor:C.bg2},
  actChipSel:     {borderColor:C.acc,backgroundColor:C.soft},
  actChipText:    {fontSize:12,color:C.ink2,fontWeight:"600"},
  genBtn:         {backgroundColor:C.acc2,borderRadius:R.lg,paddingVertical:11,alignItems:"center",
                   shadowColor:"#6D28D9",shadowOffset:{width:0,height:2},shadowOpacity:0.18,shadowRadius:4,elevation:3},
  genBtnText:     {fontSize:13,fontWeight:"700",color:"#fff"},
  signalsBtn:     {backgroundColor:C.bgCard,borderRadius:R.lg,paddingVertical:11,alignItems:"center",borderWidth:0.5,borderColor:C.border2},
  signalsBtnText: {fontSize:13,fontWeight:"600",color:C.ink2},
  // Options
  optCard:        {backgroundColor:C.bg2,borderRadius:R.lg,borderWidth:0.5,borderColor:C.border2,overflow:"hidden",padding:11},
  optIcon:        {width:36,height:36,borderRadius:9,backgroundColor:C.soft,alignItems:"center",justifyContent:"center",flexShrink:0},
  optTitle:       {fontSize:13,fontWeight:"700",color:C.ink},
  optDesc:        {fontSize:12,color:C.ink3,lineHeight:17},
  optMeta:        {fontSize:11,color:C.ink3},
  fitBadge:       {borderRadius:R.full,paddingHorizontal:8,paddingVertical:2,flexShrink:0},
  fitText:        {fontSize:10,fontWeight:"700"},
  addCalBtn:      {flex:1,backgroundColor:C.acc2,borderRadius:R.sm,paddingVertical:8,alignItems:"center"},
  addCalText:     {fontSize:11,fontWeight:"700",color:"#fff"},
  moreBtn:        {flex:1,backgroundColor:C.soft,borderRadius:R.sm,paddingVertical:8,alignItems:"center",borderWidth:0.5,borderColor:C.border,flexDirection:"row",justifyContent:"center",gap:5},
  moreBtnText:    {fontSize:11,fontWeight:"700",color:C.acc},
  // Proactive
  proactiveCard:  {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border,padding:14},
  proactiveTitle: {fontSize:12,fontWeight:"700",color:C.acc,letterSpacing:0.3},
  proactiveBody:  {fontSize:13,color:C.ink2,lineHeight:19},
  // Events
  evList:         {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,overflow:"hidden"},
  evRow:          {flexDirection:"row",alignItems:"center",gap:11,paddingHorizontal:13,paddingVertical:12,borderBottomWidth:0.5,borderBottomColor:C.bg2},
  evAccent:       {width:3,height:34,borderRadius:2},
  evTitle:        {fontSize:13,fontWeight:"600",color:C.ink},
  evMeta:         {fontSize:11,color:C.ink3},
  emptyText:      {fontSize:13,color:C.ink3,textAlign:"center",padding:20},
  // Modal
  modalHeader:    {flexDirection:"row",alignItems:"center",gap:10,paddingHorizontal:16,paddingVertical:14,backgroundColor:C.bgCard,borderBottomWidth:0.5,borderBottomColor:C.border2},
  modalBack:      {width:32,height:32,borderRadius:R.sm,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},
  modalSub:       {fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1},
  modalTitle:     {fontSize:16,fontWeight:"800",color:C.ink,marginTop:1},
  fieldLabel:     {fontSize:11,fontWeight:"700",color:C.ink3,marginBottom:6},
  fieldInput:     {borderWidth:0.5,borderColor:C.border2,borderRadius:R.lg,paddingHorizontal:13,paddingVertical:11,fontSize:14,color:C.ink,backgroundColor:C.bgCard},
  memberPill:     {paddingHorizontal:14,paddingVertical:8,borderRadius:R.full,borderWidth:0.5,borderColor:C.border,backgroundColor:C.bgCard},
  memberPillText: {fontSize:13,color:C.ink2,fontWeight:"500"},
  modalOverlay:   {flex:1,backgroundColor:"rgba(0,0,0,0.45)",justifyContent:"flex-end",...(Platform.OS==="web"?{position:"fixed" as any,top:0,left:0,right:0,bottom:0,zIndex:999}:{})},
  signalsSheet:   {backgroundColor:C.bgCard,borderTopLeftRadius:22,borderTopRightRadius:22,padding:20,paddingBottom:Platform.OS==="ios"?36:24,maxHeight:"85%"},
  sheetHandle:    {width:40,height:4,borderRadius:2,backgroundColor:C.border2,alignSelf:"center",marginBottom:12},
  sigChip:        {paddingHorizontal:13,paddingVertical:8,borderRadius:R.full,borderWidth:0.5,borderColor:C.border2,backgroundColor:C.bg2,marginBottom:7,marginRight:7},
  sigChipSel:     {borderColor:C.acc,backgroundColor:C.soft},
  sigChipText:    {fontSize:13,color:C.ink2,fontWeight:"600"},
  signalsPickerWrap:{flexDirection:"row",flexWrap:"wrap"},
});
