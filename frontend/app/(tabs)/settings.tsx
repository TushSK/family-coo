// app/(tabs)/settings.tsx  —  Context Engine (v3 Lavender)
import React, { useEffect, useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  SafeAreaView, ActivityIndicator, Platform, Dimensions, Linking,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { C, R, S, USER_ID, API_BASE } from "../constants/config";
import { useGet } from "../hooks/useApi";
import { useRouter } from "expo-router";

const MAX_W = 820;
const hp = () => Platform.OS==="web" ? Math.max(16,(Dimensions.get("window").width-MAX_W)/2) : 16;

type Confidence = "high"|"med"|"low";
type View_ = "engine"|"report"|"profile";

function SLabel({text}:{text:string}){ return <Text style={st.sl}>{text}</Text>; }

function Pill({label,conf="high"}:{label:string;conf?:Confidence}){
  const bg    = conf==="high"?C.greenS :conf==="med"?C.amberS :C.bg2;
  const color = conf==="high"?"#065F46":conf==="med"?"#92400E":C.ink2;
  const border= conf==="high"?C.greenB :conf==="med"?C.amberB :C.border;
  return (
    <View style={[st.pill,{backgroundColor:bg,borderColor:border}]}>
      <Text style={[st.pillText,{color}]}>{label}</Text>
    </View>
  );
}

function DeductionCard({text,onConfirm,onForget}:{text:string;onConfirm:()=>void;onForget:()=>void}){
  return (
    <View style={[st.dedCard,S.xs]}>
      <View style={{flexDirection:"row",alignItems:"center",gap:6,marginBottom:8}}>
        <View style={st.dedIconWrap}><Ionicons name="hardware-chip-outline" size={12} color={C.acc}/></View>
        <Text style={st.dedLabel}>AI DEDUCTION</Text>
      </View>
      <Text style={st.dedText}>{text}</Text>
      <View style={{flexDirection:"row",gap:8,marginTop:8}}>
        <TouchableOpacity style={st.confirmBtn} onPress={onConfirm}>
          <Text style={st.confirmText}>✓ Confirm</Text>
        </TouchableOpacity>
        <TouchableOpacity style={st.forgetBtn} onPress={onForget}>
          <Text style={st.forgetText}>✕ Forget</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

export default function EngineScreen() {
  const router = useRouter();
  const [view, setView] = useState<View_>("engine");
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());
  const [deductions, setDeductions] = useState([
    "You prefer morning workouts on weekends over evenings.",
    "You are researching Lenovo laptops for work.",
    "Family outings succeed when booked 48h in advance.",
  ]);
  const corrections = [
    {when:"3 days ago", wrong:"Suggested dal makhani every Monday", fix:"User prefers variety — not the same dish weekly"},
    {when:"1 week ago", wrong:"Assumed gym is 10 min away",         fix:"EōS Fitness is 22 min from home"},
  ];
  const prefs = [
    {e:"🎬",l:"Sci-Fi + AI films",            c:"high"  as Confidence},
    {e:"🍲",l:"Indian cuisine — home cooked",  c:"high"  as Confidence},
    {e:"⏰",l:"Morning window 7–10 AM",        c:"high"  as Confidence},
    {e:"📱",l:"Prefers short voice notes",     c:"med"   as Confidence},
  ];

  const { data, loading, refetch } = useGet<{memory:any;ideas:any[]}>(`/api/memory?user_id=${USER_ID}`);
  useEffect(()=>{ refetch(); },[]);

  const memory = data?.memory||{};
  const ideas  = data?.ideas ||[];
  const location= memory.location||memory.home_city||"Tampa, FL";
  const fam     = Array.isArray(memory.family_members||memory.family)?(memory.family_members||memory.family):[];

  const clusters:{[key:string]:Array<{label:string;conf:Confidence}>} = {
    "Diet & Dining":       [{label:"🍲 Indian Cuisine",conf:"high"},{label:"👨‍🍳 Home Cooking",conf:"high"},{label:"🥡 Takeout Weekends",conf:"med"}],
    "Media & Interests":   [{label:"💻 Python / AI",  conf:"high"},{label:"🎬 Hollywood Sci-Fi", conf:"high"},{label:"📺 Hindi Series",  conf:"med"}],
    "Logistics & Routine": [{label:"🚗 Kia Seltos",   conf:"high"},{label:"🏋️ EōS Fitness",     conf:"high"},{label:"🎸 Yousician",    conf:"med"}],
  };

  // ── ENGINE (main view) ──────────────────────────────────────────────────────
  if (view === "engine") return (
    <SafeAreaView style={st.safe}>
      <View style={st.header}>
        <View>
          <Text style={st.headerSub}>FAMILY COO · v2.0</Text>
          <Text style={st.headerTitle}>Context Engine</Text>
        </View>
        <TouchableOpacity onPress={refetch} style={st.refreshBtn}>
          <Ionicons name="refresh-outline" size={16} color={C.ink2}/>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={[st.content,{paddingHorizontal:hp()}]}
        showsVerticalScrollIndicator={false}
      >
        {/* Profile card */}
        <View style={[st.profileCard,S.sm]}>
          <View style={st.avatarRing}><Text style={{fontSize:26}}>🏠</Text></View>
          <View style={{flex:1,gap:2}}>
            <Text style={st.profileName}>Khandare Household</Text>
            <Text style={st.profileEmail}>{USER_ID}</Text>
            <Text style={st.profileLoc}>📍 {location}</Text>
          </View>
          <View style={st.row}>
            <View style={st.activeBadge}>
              <View style={st.activeDot}/><Text style={st.activeText}>ACTIVE</Text>
            </View>
            <TouchableOpacity style={st.profileStudioBtn} onPress={()=>setView("profile")}>
              <Text style={st.profileStudioText}>Profile Studio ✏️</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Stat strip */}
        {!loading&&(
          <View style={[st.statRow,S.xs]}>
            {[[String(ideas.length),"Ideas"],[String(fam.length||"—"),"Family"],[String(Object.keys(memory).length||"—"),"Mem. Keys"]].map(([v,l],i)=>(
              <View key={l} style={[st.statBox,i<2&&{borderRightWidth:0.5,borderRightColor:C.bg2}]}>
                <Text style={st.statNum}>{v}</Text>
                <Text style={st.statLbl}>{l}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Pattern insights HERO */}
        <View style={[st.patternHero,S.sm]}>
          <View style={{flexDirection:"row",alignItems:"center",gap:9,marginBottom:12}}>
            <View style={st.patternIconWrap}><Ionicons name="trending-up" size={14} color={C.acc}/></View>
            <View>
              <Text style={st.patternLabel}>BEHAVIOURAL PATTERNS</Text>
              <Text style={st.patternSubLabel}>Your last 30 days</Text>
            </View>
          </View>
          {/* Completion ring */}
          <View style={st.ringRow}>
            <View style={st.ringWrap}>
              {/* SVG ring simulation with border */}
              <View style={st.ringOuter}>
                <Text style={st.ringPct}>97%</Text>
              </View>
            </View>
            <View style={{flex:1}}>
              <Text style={st.ringTitle}>Completion Rate</Text>
              <Text style={st.ringSubtitle}>34 of 35 missions done</Text>
              <View style={st.ringBadge}><Text style={st.ringBadgeText}>↑ 12% vs last month</Text></View>
            </View>
          </View>
          {/* Mini stats */}
          <View style={{flexDirection:"row",gap:8,marginBottom:12}}>
            {[["12wk","Gym streak",C.green],["8×","Skipped",C.red],["#1","Top habit",C.acc]].map(([v,l,c])=>(
              <View key={l} style={st.miniStatBox}>
                <Text style={[st.miniStatVal,{color:c as string}]}>{v}</Text>
                <Text style={st.miniStatLbl}>{l}</Text>
              </View>
            ))}
          </View>
          <TouchableOpacity style={st.viewReportBtn} onPress={()=>setView("report")}>
            <Text style={st.viewReportText}>View full Pattern Report →</Text>
          </TouchableOpacity>
        </View>

        {/* Best streaks */}
        <SLabel text="🔥 BEST STREAKS"/>
        <View style={[st.card,S.xs,{padding:0,overflow:"hidden"}]}>
          {[["🏋️","EōS Fitness","12 wk streak",92,C.green,C.greenS],
            ["🥋","Judo — Drishti","8 wk streak",85,C.acc,C.soft],
            ["🛒","Grocery Run","6 wk streak",78,C.amber,C.amberS]].map(([e,h,s,p,c,bg],i,a)=>(
            <View key={h as string} style={[st.streakRow,i<a.length-1&&{borderBottomWidth:0.5,borderBottomColor:C.bg2}]}>
              <Text style={{fontSize:17}}>{e}</Text>
              <View style={{flex:1}}>
                <Text style={st.streakTitle}>{h}</Text>
                <Text style={st.streakSub}>{s}</Text>
              </View>
              <View style={[st.streakBadge,{backgroundColor:bg as string}]}>
                <Text style={[st.streakPct,{color:c as string}]}>{p}%</Text>
              </View>
              <View style={{width:60,height:5,backgroundColor:C.bg2,borderRadius:3,overflow:"hidden",marginLeft:8}}>
                <View style={{height:"100%",width:`${p}%` as any,backgroundColor:c as string,borderRadius:3}}/>
              </View>
            </View>
          ))}
        </View>

        {/* Most skipped */}
        <SLabel text="⚠️ MOST SKIPPED"/>
        <View style={[st.card,S.xs,{padding:0,overflow:"hidden"}]}>
          {[["🎸","Yousician","8×","Try 15 min right after gym — pair it"],
            ["🏥","Doctor visits","5×","Set a fixed quarterly reminder"],
            ["🌳","Family outings","4×","Book venue ahead to remove friction"]].map(([e,h,n,tip],i,a)=>(
            <View key={h as string} style={[st.skippedRow,i<a.length-1&&{borderBottomWidth:0.5,borderBottomColor:C.bg2}]}>
              <View style={st.skippedIcon}><Text style={{fontSize:15}}>{e}</Text></View>
              <View style={{flex:1}}>
                <View style={{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:4}}>
                  <Text style={st.skippedTitle}>{h}</Text>
                  <View style={st.skippedBadge}><Text style={st.skippedBadgeText}>{n}</Text></View>
                </View>
                <View style={st.suggestionBox}>
                  <Text style={st.suggestionLabel}>SUGGESTION</Text>
                  <Text style={st.suggestionText}>{tip}</Text>
                </View>
              </View>
            </View>
          ))}
        </View>

        {/* AI Insight */}
        <View style={[st.insightCard,S.xs]}>
          <View style={{flexDirection:"row",alignItems:"center",gap:7,marginBottom:8}}>
            <View style={st.insightIconWrap}><Text style={{fontSize:12}}>✦</Text></View>
            <Text style={st.insightLabel}>AI IMPROVEMENT INSIGHT</Text>
          </View>
          <Text style={st.insightText}>
            You consistently follow through on <Text style={{fontWeight:"700"}}>physical activities</Text> but skip{" "}
            <Text style={{fontWeight:"700"}}>learning & leisure</Text>. Scheduling Yousician after gym could boost follow-through ~40%.
          </Text>
          <View style={{flexDirection:"row",gap:8,marginTop:10}}>
            <TouchableOpacity style={[st.chatBtn,S.sm]} onPress={()=>router.push("/(tabs)/chat")}>
              <Text style={st.chatBtnText}>Chat about this</Text>
            </TouchableOpacity>
            <TouchableOpacity style={st.dismissBtn}>
              <Text style={st.dismissText}>Dismiss</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Identity clusters */}
        <SLabel text="🧬 HOUSEHOLD IDENTITY"/>
        <View style={[st.card,S.xs]}>
          {Object.entries(clusters).map(([cat,pills])=>(
            <View key={cat} style={st.clusterRow}>
              <Text style={st.clusterCat}>{cat}</Text>
              <View style={{flexDirection:"row",flexWrap:"wrap",marginLeft:-3}}>
                {pills.map((p,i)=><Pill key={i} label={p.label} conf={p.conf}/>)}
              </View>
            </View>
          ))}
        </View>

        {/* Engine room */}
        <SLabel text="⚙️ ENGINE ROOM"/>
        <View style={[st.card,S.xs,{padding:0,overflow:"hidden"}]}>
          {[["server-outline","API Endpoint",  API_BASE,       C.acc  ],
            ["shield-checkmark-outline","Database","Supabase · Connected",C.green],
            ["calendar-outline","Google Calendar","OAuth · Active",    C.amber],
            ["cpu-outline","AI Models",      "Claude + Groq",   "#7C3AED"]].map(([icon,label,val,color],i,a)=>(
            <View key={label as string} style={[st.engineRow,i<a.length-1&&{borderBottomWidth:0.5,borderBottomColor:C.bg2}]}>
              <View style={[st.engineIcon,{backgroundColor:(color as string)+"18"}]}>
                <Ionicons name={icon as any} size={14} color={color as string}/>
              </View>
              <Text style={st.engineLabel}>{label}</Text>
              <Text style={[st.engineVal,{color:color as string}]} numberOfLines={1}>{val}</Text>
            </View>
          ))}
        </View>
        <TouchableOpacity style={[st.docsBtn,S.xs]} onPress={()=>Linking.openURL(`${API_BASE}/docs`)}>
          <Ionicons name="code-slash-outline" size={14} color={C.acc}/>
          <Text style={st.docsBtnText}>Open Swagger Docs</Text>
          <Ionicons name="open-outline" size={13} color={C.acc}/>
        </TouchableOpacity>

        <View style={{height:32}}/>
      </ScrollView>
    </SafeAreaView>
  );

  // ── PATTERN REPORT ─────────────────────────────────────────────────────────
  if (view === "report") return (
    <SafeAreaView style={st.safe}>
      <View style={st.slideHeader}>
        <TouchableOpacity style={st.backBtn} onPress={()=>setView("engine")}>
          <Ionicons name="chevron-back" size={16} color={C.acc}/>
        </TouchableOpacity>
        <View style={{flex:1}}>
          <Text style={st.headerSub}>FULL ANALYSIS</Text>
          <Text style={st.headerTitle}>Pattern Report</Text>
        </View>
        <View style={[st.slideBadge]}><Text style={st.slideBadgeText}>Mar 2026</Text></View>
      </View>
      <ScrollView contentContainerStyle={[st.content,{paddingHorizontal:hp()}]} showsVerticalScrollIndicator={false}>

        {/* Overall score */}
        <View style={[st.patternHero,S.sm]}>
          <View style={{flexDirection:"row",alignItems:"center",gap:14}}>
            <View style={st.ringWrap}>
              <View style={[st.ringOuter,{width:70,height:70,borderRadius:35}]}>
                <Text style={[st.ringPct,{fontSize:15}]}>97%</Text>
              </View>
            </View>
            <View>
              <Text style={st.ringTitle}>Excellent execution</Text>
              <Text style={st.ringSubtitle}>34 of 35 missions completed</Text>
              <Text style={[st.ringSubtitle,{marginTop:2}]}>↑ 12% vs last month</Text>
            </View>
          </View>
        </View>

        {/* Category breakdown */}
        <SLabel text="📊 COMPLETION BY CATEGORY"/>
        <View style={[st.card,S.xs]}>
          {[["Physical fitness",95,C.green,"Strong — protect this"],
            ["Family logistics",88,C.acc,"Consistent and reliable"],
            ["Health & medical",65,C.amber,"Needs attention"],
            ["Learning & leisure",42,C.red,"Weakest — focus here"],
            ["Household errands",91,C.green,"Very consistent"]].map(([cat,pct,c,note])=>(
            <View key={cat as string} style={{marginBottom:12}}>
              <View style={{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:4}}>
                <Text style={st.catLabel}>{cat}</Text>
                <Text style={[st.catPct,{color:c as string}]}>{pct}%</Text>
              </View>
              <View style={st.barBg}>
                <View style={[st.barFill,{width:`${pct}%` as any,backgroundColor:c as string}]}/>
              </View>
              <Text style={st.catNote}>{note}</Text>
            </View>
          ))}
        </View>

        {/* Weakest area */}
        <View style={[st.weakestCard,S.xs]}>
          <View style={{flexDirection:"row",alignItems:"center",gap:9,marginBottom:9}}>
            <View style={st.weakestIcon}><Text style={{fontSize:14}}>🎯</Text></View>
            <View>
              <Text style={st.weakestLabel}>WEAKEST AREA · FOCUS HERE</Text>
              <Text style={st.weakestTitle}>Learning & Leisure — 42%</Text>
            </View>
          </View>
          <Text style={st.weakestBody}>Yousician practice has been skipped 8× this month. Pair it with an existing habit to build momentum.</Text>
          <View style={{gap:6,marginTop:10}}>
            {["🎸 Add Yousician as 15-min post-gym cool-down",
              "📅 Block Tue & Thu evenings as learning windows",
              "🎬 Schedule one film night per weekend"].map(s=>(
              <View key={s} style={st.weakestTip}>
                <Text style={{fontSize:13,flexShrink:0}}>{s.split(" ")[0]}</Text>
                <Text style={st.weakestTipText}>{s.split(" ").slice(1).join(" ")}</Text>
              </View>
            ))}
          </View>
          <TouchableOpacity style={[st.buildBtn,S.sm,{marginTop:10}]} onPress={()=>router.push("/(tabs)/chat")}>
            <Text style={st.buildBtnText}>Build a learning plan in Chat →</Text>
          </TouchableOpacity>
        </View>

        {/* Deductions */}
        <SLabel text="🧠 AI DEDUCTIONS — CONFIRM OR FORGET"/>
        <View style={[st.card,S.xs,{gap:0}]}>
          {deductions.filter((_,i)=>!dismissed.has(i)).length===0
            ? <Text style={{fontSize:13,color:C.ink3,textAlign:"center",padding:14}}>All deductions reviewed ✓</Text>
            : deductions.map((d,i)=>dismissed.has(i)?null:(
              <View key={i} style={[st.dedInline,i>0&&{borderTopWidth:0.5,borderTopColor:C.bg2}]}>
                <View style={{flexDirection:"row",alignItems:"flex-start",gap:8,marginBottom:8}}>
                  <View style={st.dedIconWrap}><Text style={{fontSize:11}}>✦</Text></View>
                  <Text style={st.dedText}>{d}</Text>
                </View>
                <View style={{flexDirection:"row",gap:7}}>
                  <TouchableOpacity style={st.confirmBtn}
                    onPress={()=>setDismissed(prev=>new Set([...prev,i]))}>
                    <Text style={st.confirmText}>✓ Confirm</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={st.forgetBtn}
                    onPress={()=>setDismissed(prev=>new Set([...prev,i]))}>
                    <Text style={st.forgetText}>✕ Forget</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))
          }
        </View>

        {/* Memory health */}
        <View style={[st.insightCard,S.xs]}>
          <View style={{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:7}}>
            <Text style={st.insightLabel}>MEMORY HEALTH</Text>
            <Text style={[st.insightLabel,{fontSize:13}]}>74%</Text>
          </View>
          <View style={st.barBg}>
            <View style={[st.barFill,{width:"74%",backgroundColor:C.acc2}]}/>
          </View>
          <Text style={[st.insightText,{marginTop:8,marginBottom:10}]}>
            2 unconfirmed deductions limiting accuracy. Review them above.
          </Text>
          {["Confirm pending deductions to improve calendar accuracy.",
            "Add work hours so the AI avoids scheduling conflicts.",
            "Tell the AI about Drishti's school schedule."].map(s=>(
            <TouchableOpacity key={s} style={{flexDirection:"row",alignItems:"flex-start",gap:8,marginBottom:7}} onPress={()=>router.push("/(tabs)/chat")}>
              <View style={[st.insightIconWrap,{marginTop:1}]}><Ionicons name="add" size={9} color={C.acc}/></View>
              <Text style={[st.insightText,{flex:1}]}>{s}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Corrections log */}
        <SLabel text="🔧 CORRECTIONS LOG"/>
        <View style={[st.card,S.xs,{padding:0,overflow:"hidden"}]}>
          {corrections.map((c,i,a)=>(
            <View key={i} style={[st.corrRow,i<a.length-1&&{borderBottomWidth:0.5,borderBottomColor:C.bg2}]}>
              <View style={st.corrBadge}><Text style={st.corrBadgeText}>CORRECTED · {c.when}</Text></View>
              <Text style={st.corrWrong}>{c.wrong}</Text>
              <View style={{flexDirection:"row",alignItems:"flex-start",gap:6}}>
                <Ionicons name="checkmark" size={13} color={C.green} style={{marginTop:2}}/>
                <Text style={st.corrFix}>{c.fix}</Text>
              </View>
            </View>
          ))}
        </View>

        {/* Learned prefs */}
        <SLabel text="✨ RECENTLY LEARNED PREFERENCES"/>
        <View style={[st.card,S.xs,{padding:0,overflow:"hidden"}]}>
          {prefs.map((p,i,a)=>(
            <View key={i} style={[st.prefRow,i<a.length-1&&{borderBottomWidth:0.5,borderBottomColor:C.bg2}]}>
              <Text style={{fontSize:16}}>{p.e}</Text>
              <Text style={st.prefLabel}>{p.l}</Text>
              <Pill label={p.c==="high"?"High":"Medium"} conf={p.c}/>
            </View>
          ))}
        </View>

        <View style={{height:32}}/>
      </ScrollView>
    </SafeAreaView>
  );

  // ── PROFILE STUDIO ─────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={st.safe}>
      <View style={st.slideHeader}>
        <TouchableOpacity style={st.backBtn} onPress={()=>setView("engine")}>
          <Ionicons name="chevron-back" size={16} color={C.acc}/>
        </TouchableOpacity>
        <View style={{flex:1}}>
          <Text style={st.headerSub}>ENGINE → EDIT</Text>
          <Text style={st.headerTitle}>Profile Studio</Text>
        </View>
        <View style={st.slideBadge}><Text style={st.slideBadgeText}>Khandare</Text></View>
      </View>
      <ScrollView contentContainerStyle={[st.content,{paddingHorizontal:hp()}]} showsVerticalScrollIndicator={false}>

        {[{e:"👨‍👩‍👧",t:"Household",     items:["Primary adult","Partner","Young child"]},
          {e:"🌟",t:"Lifestyle",      items:["Family activities","Food ideas","Wellness","Entertainment","Local outing"]},
          {e:"🗺️",t:"Local world",    items:["Tampa, FL","Local: up to 20 mi","Weekend: up to 75 mi"]},
          {e:"📅",t:"Weekend & Planning",items:["Social & lively","Balanced planner"]},
          {e:"🎙️",t:"Assistant Tone", items:["Balanced"]},
        ].map(s=>(
          <View key={s.t} style={[st.card,S.xs]}>
            <View style={{flexDirection:"row",alignItems:"center",gap:8,marginBottom:8}}>
              <Text style={{fontSize:18}}>{s.e}</Text>
              <Text style={[st.clusterCat,{flex:1}]}>{s.t}</Text>
              <TouchableOpacity style={st.editBtn}>
                <Text style={st.editBtnText}>Edit</Text>
              </TouchableOpacity>
            </View>
            <View style={{flexDirection:"row",flexWrap:"wrap",gap:7}}>
              {s.items.map(item=>(
                <View key={item} style={st.profilePill}>
                  <Text style={st.profilePillText}>{item}</Text>
                </View>
              ))}
            </View>
          </View>
        ))}

        <View style={[st.noteBox]}>
          <Text style={st.noteText}>✏️ Changes save automatically and improve suggestions from the next session.</Text>
        </View>

        <View style={{height:32}}/>
      </ScrollView>
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
  slideHeader:{
    flexDirection:"row",alignItems:"center",gap:10,
    paddingHorizontal:16,paddingVertical:13,
    backgroundColor:C.bgCard,borderBottomWidth:0.5,borderBottomColor:C.border2,
    shadowColor:"#6D28D9",shadowOffset:{width:0,height:1},shadowOpacity:0.06,shadowRadius:4,elevation:2,
  },
  backBtn:     {width:32,height:32,borderRadius:R.sm,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},
  slideBadge:  {backgroundColor:C.soft,borderRadius:R.full,borderWidth:0.5,borderColor:C.border,paddingHorizontal:10,paddingVertical:4},
  slideBadgeText:{fontSize:11,fontWeight:"700",color:C.acc},
  headerSub:   {fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1},
  headerTitle: {fontSize:18,fontWeight:"800",color:C.ink,marginTop:1},
  refreshBtn:  {padding:8,borderRadius:R.sm,backgroundColor:C.bg2},
  content:     {paddingTop:14,paddingBottom:32,gap:13},
  sl:          {fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1.2,marginBottom:8},
  card:        {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,padding:14},
  // Profile
  profileCard: {flexDirection:"row",alignItems:"center",gap:12,backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border,padding:14},
  avatarRing:  {width:50,height:50,borderRadius:25,backgroundColor:C.soft,borderWidth:2,borderColor:C.acc,alignItems:"center",justifyContent:"center"},
  profileName: {fontSize:14,fontWeight:"800",color:C.ink},
  profileEmail:{fontSize:11,color:C.ink2},
  profileLoc:  {fontSize:11,color:C.ink3},
  row:         {gap:6,alignItems:"flex-end"},
  activeBadge: {flexDirection:"row",alignItems:"center",gap:4,backgroundColor:C.greenS,borderWidth:0.5,borderColor:C.greenB,borderRadius:R.full,paddingHorizontal:8,paddingVertical:3},
  activeDot:   {width:6,height:6,borderRadius:3,backgroundColor:C.green},
  activeText:  {fontSize:9,fontWeight:"700",color:"#065F46",letterSpacing:0.7},
  profileStudioBtn:{backgroundColor:C.soft,borderRadius:R.sm,borderWidth:0.5,borderColor:C.border,paddingHorizontal:9,paddingVertical:5},
  profileStudioText:{fontSize:11,fontWeight:"700",color:C.acc},
  // Stats
  statRow:     {flexDirection:"row",backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,overflow:"hidden"},
  statBox:     {flex:1,alignItems:"center",paddingVertical:12},
  statNum:     {fontSize:20,fontWeight:"800",color:C.acc},
  statLbl:     {fontSize:10,color:C.ink3,marginTop:2},
  // Pattern hero
  patternHero: {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border,padding:16},
  patternIconWrap:{width:28,height:28,borderRadius:R.sm,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},
  patternLabel:{fontSize:10,fontWeight:"700",color:C.acc,letterSpacing:1},
  patternSubLabel:{fontSize:13,fontWeight:"800",color:C.ink},
  ringRow:     {flexDirection:"row",alignItems:"center",gap:14,backgroundColor:C.soft,borderRadius:R.lg,padding:12,marginBottom:10},
  ringWrap:    {flexShrink:0},
  ringOuter:   {width:58,height:58,borderRadius:29,borderWidth:6,borderColor:C.acc2,backgroundColor:C.bgCard,alignItems:"center",justifyContent:"center"},
  ringPct:     {fontSize:13,fontWeight:"800",color:C.acc},
  ringTitle:   {fontSize:14,fontWeight:"800",color:C.ink},
  ringSubtitle:{fontSize:12,color:C.ink2,marginTop:2},
  ringBadge:   {backgroundColor:C.greenS,borderRadius:R.full,paddingHorizontal:9,paddingVertical:3,marginTop:5,alignSelf:"flex-start"},
  ringBadgeText:{fontSize:10,fontWeight:"700",color:C.green},
  miniStatBox: {flex:1,backgroundColor:C.bg2,borderRadius:R.lg,padding:9,alignItems:"center",borderWidth:0.5,borderColor:C.border2},
  miniStatVal: {fontSize:16,fontWeight:"800"},
  miniStatLbl: {fontSize:10,color:C.ink3,marginTop:2},
  viewReportBtn:{backgroundColor:C.acc2,borderRadius:R.lg,padding:11,alignItems:"center",shadowColor:"#6D28D9",shadowOffset:{width:0,height:2},shadowOpacity:0.18,shadowRadius:4,elevation:3},
  viewReportText:{fontSize:13,fontWeight:"700",color:"#fff"},
  // Streaks
  streakRow:   {flexDirection:"row",alignItems:"center",gap:9,padding:11},
  streakTitle: {fontSize:13,fontWeight:"700",color:C.ink},
  streakSub:   {fontSize:11,color:C.ink3},
  streakBadge: {borderRadius:R.full,paddingHorizontal:9,paddingVertical:3},
  streakPct:   {fontSize:11,fontWeight:"700"},
  // Skipped
  skippedRow:  {flexDirection:"row",alignItems:"flex-start",gap:9,padding:11},
  skippedIcon: {width:32,height:32,borderRadius:R.sm,backgroundColor:C.redS,alignItems:"center",justifyContent:"center",flexShrink:0},
  skippedTitle:{fontSize:13,fontWeight:"700",color:C.ink},
  skippedBadge:{backgroundColor:C.redS,borderRadius:R.full,paddingHorizontal:8,paddingVertical:2},
  skippedBadgeText:{fontSize:10,fontWeight:"700",color:C.red},
  suggestionBox:{backgroundColor:C.amberS,borderRadius:R.sm,padding:7,borderLeftWidth:2,borderLeftColor:C.amber},
  suggestionLabel:{fontSize:9,fontWeight:"700",color:C.amber,marginBottom:2},
  suggestionText: {fontSize:11,color:"#78350F",lineHeight:16},
  // AI Insight
  insightCard: {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border,padding:14},
  insightIconWrap:{width:22,height:22,borderRadius:R.xs,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},
  insightLabel:{fontSize:10,fontWeight:"700",color:C.acc,letterSpacing:1},
  insightText: {fontSize:13,color:C.ink2,lineHeight:20},
  chatBtn:     {flex:1,backgroundColor:C.acc2,borderRadius:R.lg,paddingVertical:10,alignItems:"center"},
  chatBtnText: {fontSize:12,fontWeight:"700",color:"#fff"},
  dismissBtn:  {flex:1,backgroundColor:C.bg2,borderRadius:R.lg,paddingVertical:10,alignItems:"center",borderWidth:0.5,borderColor:C.border2},
  dismissText: {fontSize:12,fontWeight:"600",color:C.ink2},
  // Identity
  clusterRow:  {marginBottom:12},
  clusterCat:  {fontSize:12,fontWeight:"700",color:C.ink,marginBottom:7},
  pill:        {paddingHorizontal:10,paddingVertical:4,borderRadius:R.full,borderWidth:0.5,margin:3},
  pillText:    {fontSize:11,fontWeight:"700"},
  // Engine room
  engineRow:   {flexDirection:"row",alignItems:"center",gap:11,paddingHorizontal:13,paddingVertical:11},
  engineIcon:  {width:30,height:30,borderRadius:R.sm,alignItems:"center",justifyContent:"center"},
  engineLabel: {flex:1,fontSize:13,color:C.ink,fontWeight:"500"},
  engineVal:   {fontSize:11,fontWeight:"700",maxWidth:140},
  docsBtn:     {flexDirection:"row",alignItems:"center",justifyContent:"center",gap:7,paddingVertical:11,backgroundColor:C.soft,borderRadius:R.lg,borderWidth:0.5,borderColor:C.border},
  docsBtnText: {fontSize:13,fontWeight:"700",color:C.acc},
  // Deductions
  dedCard:     {backgroundColor:C.bgCard,borderRadius:R.lg,borderWidth:0.5,borderColor:C.border2,padding:13,marginBottom:10},
  dedIconWrap: {width:22,height:22,borderRadius:R.xs,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},
  dedLabel:    {fontSize:10,fontWeight:"700",color:C.acc,letterSpacing:1},
  dedText:     {fontSize:13,color:C.ink2,lineHeight:19},
  dedInline:   {padding:12},
  confirmBtn:  {flex:1,backgroundColor:C.greenS,borderRadius:R.sm,borderWidth:0.5,borderColor:C.greenB,paddingVertical:8,alignItems:"center"},
  confirmText: {fontSize:12,fontWeight:"700",color:"#065F46"},
  forgetBtn:   {flex:1,backgroundColor:C.redS,borderRadius:R.sm,borderWidth:0.5,borderColor:C.redB,paddingVertical:8,alignItems:"center"},
  forgetText:  {fontSize:12,fontWeight:"700",color:C.red},
  // Pattern report
  catLabel:    {fontSize:12,fontWeight:"600",color:C.ink},
  catPct:      {fontSize:12,fontWeight:"800"},
  barBg:       {height:6,backgroundColor:C.bg2,borderRadius:3,overflow:"hidden",marginBottom:3},
  barFill:     {height:"100%",borderRadius:3},
  catNote:     {fontSize:10,color:C.ink3},
  weakestCard: {backgroundColor:C.redS,borderRadius:R.xl,borderWidth:0.5,borderColor:C.redB,padding:14},
  weakestIcon: {width:28,height:28,borderRadius:R.sm,backgroundColor:C.red,alignItems:"center",justifyContent:"center"},
  weakestLabel:{fontSize:10,fontWeight:"700",color:C.red,letterSpacing:1},
  weakestTitle:{fontSize:13,fontWeight:"800",color:"#7F1D1D"},
  weakestBody: {fontSize:13,color:"#7F1D1D",lineHeight:19},
  weakestTip:  {flexDirection:"row",alignItems:"flex-start",gap:8,backgroundColor:"rgba(255,255,255,0.55)",borderRadius:R.sm,padding:8},
  weakestTipText:{fontSize:12,color:"#7F1D1D",flex:1,lineHeight:18},
  buildBtn:    {backgroundColor:C.red,borderRadius:R.lg,padding:11,alignItems:"center"},
  buildBtnText:{fontSize:12,fontWeight:"700",color:"#fff"},
  corrRow:     {padding:12,gap:5},
  corrBadge:   {backgroundColor:C.redS,borderRadius:R.full,paddingHorizontal:8,paddingVertical:2,alignSelf:"flex-start"},
  corrBadgeText:{fontSize:10,fontWeight:"700",color:C.red},
  corrWrong:   {fontSize:12,color:C.ink3,textDecorationLine:"line-through"},
  corrFix:     {fontSize:12,fontWeight:"600",color:C.green,flex:1},
  prefRow:     {flexDirection:"row",alignItems:"center",gap:9,padding:11},
  prefLabel:   {flex:1,fontSize:12,color:C.ink,fontWeight:"500"},
  // Profile studio
  editBtn:     {backgroundColor:C.soft,borderRadius:R.sm,borderWidth:0.5,borderColor:C.border,paddingHorizontal:9,paddingVertical:5},
  editBtnText: {fontSize:11,fontWeight:"700",color:C.acc},
  profilePill: {backgroundColor:C.bg2,borderRadius:R.full,paddingHorizontal:10,paddingVertical:4},
  profilePillText:{fontSize:12,color:C.ink2,fontWeight:"500"},
  noteBox:     {backgroundColor:C.amberS,borderRadius:R.lg,borderWidth:0.5,borderColor:C.amberB,padding:13},
  noteText:    {fontSize:12,color:"#78350F",lineHeight:18},
});
