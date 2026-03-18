// app/(tabs)/settings.tsx  —  Context Engine (v3) — live data from /api/insights
import React, { useEffect, useState } from "react";
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, SafeAreaView, ActivityIndicator, Platform, Dimensions, Linking } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { C, R, S, USER_ID, API_BASE } from "../constants/config";
import { useGet } from "../hooks/useApi";
import { getIdeas, syncFromRemote, Idea } from "../context/IdeasStore";
import { useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { ctxEngineInsight, ctxUpdateIdentity, ctxPreferenceDrill } from "../context/ChatContextStore";
import { useRouter } from "expo-router";

const MAX_W = 820;
const hp = () => Platform.OS==="web" ? Math.max(16,(Dimensions.get("window").width-MAX_W)/2) : 16;
type Confidence = "high"|"med"|"low";
type ViewMode = "engine"|"report"|"profile";

function SLabel({text}:{text:string}){ return <Text style={st.sl}>{text}</Text>; }

// Static (non-tappable) pill — used outside the identity card
function Pill({label,conf="high"}:{label:string;conf?:Confidence}){
  const bg=conf==="high"?C.greenS:conf==="med"?C.amberS:C.bg2;
  const color=conf==="high"?"#065F46":conf==="med"?"#92400E":C.ink2;
  const border=conf==="high"?C.greenB:conf==="med"?C.amberB:C.border;
  return <View style={[st.pill,{backgroundColor:bg,borderColor:border}]}><Text style={[st.pillText,{color}]}>{label}</Text></View>;
}

// Tappable pill — used inside the Household Identity card (fix #4)
// Tap → ctxPreferenceDrill → chat gives 3 ideas for that preference
function TappablePill({label,conf="high",onTap}:{label:string;conf?:Confidence;onTap:()=>void}){
  const bg=conf==="high"?C.greenS:conf==="med"?C.amberS:C.bg2;
  const color=conf==="high"?"#065F46":conf==="med"?"#92400E":C.ink2;
  const border=conf==="high"?C.greenB:conf==="med"?C.amberB:C.border;
  return (
    <TouchableOpacity
      style={[st.pill,{backgroundColor:bg,borderColor:border},st.pillTappable]}
      onPress={onTap}
      activeOpacity={0.65}
    >
      <Text style={[st.pillText,{color}]}>{label}</Text>
      <Ionicons name="chevron-forward" size={9} color={color} style={{marginLeft:2}}/>
    </TouchableOpacity>
  );
}

function insightColors(type:string){
  switch(type){case "win":return{bg:C.greenS,border:C.greenB,text:"#065F46"};case "watch":return{bg:C.amberS,border:C.amberB,text:"#92400E"};case "tip":return{bg:C.soft,border:C.border,text:C.acc};default:return{bg:C.bg2,border:C.border2,text:C.ink2};}
}

// ── AI Personality Summary — generated from live memory ──────────────────────
// Builds a short human-readable sentence describing this household's personality
// so the Identity card shows meaningful text instead of just a pile of pills.
function buildPersonalitySummary(memory:any, location:string): string {
  const cuisine: string[] = memory.cuisine || memory.food_preferences || [];
  const interests: string[] = memory.interests || memory.lifestyle_interests || [];
  const hobbies: string[] = memory.hobbies || memory.hobby_list || [];
  const fam: any[] = Array.isArray(memory.family_members||memory.family) ? (memory.family_members||memory.family) : [];

  const cuisineStr = cuisine.length
    ? cuisine.slice(0,2).join(" & ").toLowerCase()
    : "Indian home cooking";
  const interestStr = [...interests,...hobbies].slice(0,2)
    .join(" and ")
    .toLowerCase() || "Python/AI and sci-fi films";
  const famNote = fam.length > 0 ? `a family of ${fam.length}` : "a household";

  return (
    `${famNote.charAt(0).toUpperCase() + famNote.slice(1)} in ${location} ` +
    `that loves ${cuisineStr}. Interests span ${interestStr}. ` +
    `Active at EōS Fitness and keeps weekends family-centred. ` +
    `The AI uses this profile to personalise every suggestion.`
  );
}

// ── Profile freshness — count how many fields come from live API vs defaults ──
function memoryFieldCount(memory:any): number {
  let n = 0;
  if((memory.cuisine||memory.food_preferences||[]).length) n++;
  if((memory.interests||memory.lifestyle_interests||[]).length) n++;
  if((memory.hobbies||memory.hobby_list||[]).length) n++;
  if(memory.location||memory.home_city) n++;
  return n;
}

export default function EngineScreen() {
  const router = useRouter();
  const [view, setView] = useState<ViewMode>("engine");
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());
  const memRes = useGet<{memory:any;ideas:any[]}>(`/api/memory?user_id=${USER_ID}`);
  const insRes = useGet<{kpis:any;insights:any[]}>(`/api/insights?user_id=${USER_ID}`);
  useEffect(()=>{memRes.refetch();insRes.refetch();},[]);

  // Load ideas from shared AsyncStorage store — stays in sync with Missions tab
  const [localIdeas, setLocalIdeas] = React.useState<Idea[]>([]);
  useFocusEffect(useCallback(()=>{
    syncFromRemote().then(setLocalIdeas);
    memRes.refetch();
    insRes.refetch();
  },[]));

  const pendingIdeasCount = localIdeas.filter(i=>!i.converted).length;

  const memory=memRes.data?.memory||{};
  const ideas=memRes.data?.ideas||[];
  const kpis=insRes.data?.kpis||{};
  const insights=insRes.data?.insights||[];
  const location=memory.location||memory.home_city||"Tampa, FL";
  const fam=Array.isArray(memory.family_members||memory.family)?(memory.family_members||memory.family):[];
  const completionPct=kpis.completion_pct?Math.round(kpis.completion_pct):(kpis.completed_count&&kpis.total_feedback?Math.round(kpis.completed_count/kpis.total_feedback*100):97);
  const completedCount=kpis.completed_count||34;
  const totalCount=kpis.total_feedback||35;
  const pendingMissions=kpis.pending_missions||0;
  const aiInsight=insights.find((i:any)=>i.type==="tip")||insights.find((i:any)=>i.type==="watch")||null;

  // Streaks — live from insights where possible, else defaults
  const liveStreaks=insights.filter((i:any)=>i.type==="win"&&i.headline?.toLowerCase().includes("streak")).slice(0,3);
  const streaks=liveStreaks.length>=2?liveStreaks.map((i:any)=>({emoji:i.emoji||"🏆",title:i.headline?.replace(/streak.*$/i,"").trim()||i.headline,sub:i.detail||"",pct:85,color:C.green,bg:C.greenS})):[
    {emoji:"🏋️",title:"EōS Fitness",sub:"12 wk streak",pct:92,color:C.green,bg:C.greenS},
    {emoji:"🥋",title:"Judo — Drishti",sub:"8 wk streak",pct:85,color:C.acc,bg:C.soft},
    {emoji:"🛒",title:"Grocery Run",sub:"6 wk streak",pct:78,color:C.amber,bg:C.amberS},
  ];

  // Skipped — live from insights where possible, else defaults
  const liveSkipped=insights.filter((i:any)=>i.type==="watch"||(i.type==="tip"&&i.headline?.toLowerCase().includes("skip"))).slice(0,3);
  const skipped=liveSkipped.length>=2?liveSkipped.map((i:any)=>({emoji:i.emoji||"⚠️",title:i.headline?.split("·")[0]?.trim()||i.headline,count:i.detail?.match(/\d+/)?.[0]+"×"||"—",tip:i.detail||""})):[
    {emoji:"🎸",title:"Yousician",count:"8×",tip:"Try 15 min right after gym — pair it"},
    {emoji:"🏥",title:"Doctor visits",count:"5×",tip:"Set a fixed quarterly reminder"},
    {emoji:"🌳",title:"Family outings",count:"4×",tip:"Book venue ahead to remove friction"},
  ];

  const categories=kpis.by_category||[
    {label:"Physical fitness",pct:95,color:C.green,note:"Strong — protect this"},
    {label:"Family logistics",pct:88,color:C.acc,note:"Consistent and reliable"},
    {label:"Health & medical",pct:65,color:C.amber,note:"Needs attention"},
    {label:"Learning & leisure",pct:42,color:C.red,note:"Weakest — focus here"},
    {label:"Household errands",pct:91,color:C.green,note:"Very consistent"},
  ];
  const weakest=[...categories].sort((a:any,b:any)=>a.pct-b.pct)[0];
  // Build identity clusters from live memory — fall back to Profile Studio onboarding data
  function buildClusters(): Record<string,Array<{label:string;conf:Confidence}>> {
    const interests: string[] = memory.interests || memory.lifestyle_interests || [];
    const cuisine:   string[] = memory.cuisine    || memory.food_preferences   || [];
    const hobbies:   string[] = memory.hobbies    || memory.hobby_list         || [];
    const vehicles:  string[] = memory.vehicles   || [];
    const routines:  string[] = memory.routines   || [];

    // If memory is populated, use it
    const dietPills = [
      ...cuisine.slice(0,3).map(c=>({label:`🍽 ${c}`,conf:"high" as Confidence})),
      ...(cuisine.length===0?[
        {label:"🍲 Indian Cuisine",conf:"high" as Confidence},
        {label:"👨‍🍳 Home Cooking",conf:"high" as Confidence},
        {label:"🥡 Takeout Weekends",conf:"med" as Confidence},
      ]:[]),
    ].slice(0,4);

    const interestPills = [
      ...interests.slice(0,3).map(i=>({label:`✨ ${i}`,conf:"high" as Confidence})),
      ...hobbies.slice(0,2).map(h=>({label:`🎯 ${h}`,conf:"med" as Confidence})),
      ...(interests.length===0?[
        {label:"💻 Python / AI",conf:"high" as Confidence},
        {label:"🎬 Sci-Fi films",conf:"high" as Confidence},
        {label:"🎸 Yousician",conf:"med" as Confidence},
      ]:[]),
    ].slice(0,4);

    const logisticsPills = [
      ...vehicles.slice(0,1).map(v=>({label:`🚗 ${v}`,conf:"high" as Confidence})),
      ...routines.slice(0,2).map(r=>({label:`⏰ ${r}`,conf:"med" as Confidence})),
      {label:`🏋️ EōS Fitness`,conf:"high" as Confidence},
      {label:`📍 ${location}`,conf:"high" as Confidence},
    ].slice(0,4);

    return {
      "Diet & Dining":    dietPills,
      "Interests & Media":interestPills,
      "Logistics":        logisticsPills,
    };
  }
  const clusters = buildClusters();
  const loading=memRes.loading||insRes.loading;

  if(view==="engine") return (
    <SafeAreaView style={st.safe}>
      <View style={st.header}>
        <View><Text style={st.headerSub}>FAMILY COO · v2.0</Text><Text style={st.headerTitle}>Context Engine</Text></View>
        <TouchableOpacity onPress={()=>{memRes.refetch();insRes.refetch();}} style={st.refreshBtn}><Ionicons name="refresh-outline" size={16} color={C.ink2}/></TouchableOpacity>
      </View>
      <ScrollView contentContainerStyle={[st.content,{paddingHorizontal:hp()}]} showsVerticalScrollIndicator={false}>
        {loading&&<ActivityIndicator color={C.acc} style={{marginVertical:12}}/>}
        {/* Profile */}
        <View style={[st.profileCard,S.sm]}>
          <View style={st.avatarRing}><Text style={{fontSize:26}}>🏠</Text></View>
          <View style={{flex:1,gap:2}}><Text style={st.profileName}>Khandare Household</Text><Text style={st.profileEmail}>{USER_ID}</Text><Text style={st.profileLoc}>📍 {location}</Text></View>
          <View style={{gap:6,alignItems:"flex-end"}}>
            <View style={st.activeBadge}><View style={st.activeDot}/><Text style={st.activeText}>ACTIVE</Text></View>
            <TouchableOpacity style={st.profileStudioBtn} onPress={()=>setView("profile")}><Text style={st.profileStudioText}>Profile Studio ✏️</Text></TouchableOpacity>
          </View>
        </View>
        {/* Stats */}
        <View style={[st.statRow,S.xs]}>
          {[[String(pendingIdeasCount),"Ideas",C.acc],[String(fam.length||"—"),"Family",C.amber],[String(pendingMissions),"Pending",pendingMissions>0?C.red:C.green]].map(([v,l,c],i)=>(
            <View key={l} style={[st.statBox,i<2&&{borderRightWidth:0.5,borderRightColor:C.bg2}]}>
              <Text style={[st.statNum,{color:c as string}]}>{v}</Text><Text style={st.statLbl}>{l}</Text>
            </View>
          ))}
        </View>
        {/* Pattern Hero */}
        <View style={[st.patternHero,S.sm]}>
          <View style={{flexDirection:"row",alignItems:"center",gap:9,marginBottom:12}}>
            <View style={st.patternIconWrap}><Ionicons name="trending-up" size={14} color={C.acc}/></View>
            <View><Text style={st.patternLabel}>BEHAVIOURAL PATTERNS</Text><Text style={st.patternSubLabel}>Your last 30 days</Text></View>
          </View>
          <View style={st.ringRow}>
            <View style={st.ringOuter}><Text style={st.ringPct}>{completionPct}%</Text></View>
            <View style={{flex:1}}>
              <Text style={st.ringTitle}>Completion Rate</Text>
              <Text style={st.ringSubtitle}>{completedCount} of {totalCount} missions done</Text>
              {kpis.completion_pct&&<View style={st.ringBadge}><Text style={st.ringBadgeText}>Live ✓</Text></View>}
            </View>
          </View>
          <View style={{flexDirection:"row",gap:8,marginBottom:12}}>
            {[[String(kpis.completed_count||completedCount),"Completed",C.green],[String(kpis.skipped_count||"—"),"Skipped",C.red],[String(kpis.pending_missions||"—"),"Pending",C.acc]].map(([v,l,c])=>(
              <View key={l} style={st.miniStatBox}><Text style={[st.miniStatVal,{color:c as string}]}>{v}</Text><Text style={st.miniStatLbl}>{l}</Text></View>
            ))}
          </View>
          <TouchableOpacity style={st.viewReportBtn} onPress={()=>setView("report")}><Text style={st.viewReportText}>View full Pattern Report →</Text></TouchableOpacity>
        </View>
        {/* Live insights */}
        {insights.length>0&&(<>
          <SLabel text="✨ LIVE INSIGHTS FROM YOUR DATA"/>
          <View style={[st.card,S.xs,{gap:8}]}>
            {insights.slice(0,4).map((ins:any,i:number)=>{
              const {bg,border,text}=insightColors(ins.type);
              return <View key={i} style={[st.insightRow,{backgroundColor:bg,borderColor:border}]}><Text style={{fontSize:20,flexShrink:0}}>{ins.emoji}</Text><View style={{flex:1}}><Text style={[st.insightHead,{color:text}]}>{ins.headline}</Text><Text style={st.insightDetail}>{ins.detail}</Text></View></View>;
            })}
          </View>
        </>)}
        {/* Streaks */}
        <SLabel text="🔥 BEST STREAKS"/>
        <View style={[st.card,S.xs,{padding:0,overflow:"hidden"}]}>
          {streaks.map((h:any,i:number,a:any[])=>(
            <View key={h.title} style={[st.streakRow,i<a.length-1&&{borderBottomWidth:0.5,borderBottomColor:C.bg2}]}>
              <Text style={{fontSize:17}}>{h.emoji}</Text>
              <View style={{flex:1}}><Text style={st.streakTitle}>{h.title}</Text><Text style={st.streakSub}>{h.sub}</Text></View>
              <View style={[st.streakBadge,{backgroundColor:h.bg}]}><Text style={[st.streakPct,{color:h.color}]}>{h.pct}%</Text></View>
              <View style={{width:60,height:5,backgroundColor:C.bg2,borderRadius:3,overflow:"hidden",marginLeft:8}}><View style={{height:"100%",width:`${h.pct}%` as any,backgroundColor:h.color,borderRadius:3}}/></View>
            </View>
          ))}
        </View>
        {/* Skipped */}
        <SLabel text="⚠️ MOST SKIPPED"/>
        <View style={[st.card,S.xs,{padding:0,overflow:"hidden"}]}>
          {skipped.map((s:any,i:number,a:any[])=>(
            <View key={s.title} style={[st.skippedRow,i<a.length-1&&{borderBottomWidth:0.5,borderBottomColor:C.bg2}]}>
              <View style={st.skippedIcon}><Text style={{fontSize:15}}>{s.emoji}</Text></View>
              <View style={{flex:1}}>
                <View style={{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:4}}><Text style={st.skippedTitle}>{s.title}</Text><View style={st.skippedBadge}><Text style={st.skippedBadgeText}>{s.count}</Text></View></View>
                <View style={st.suggestionBox}><Text style={st.suggestionLabel}>SUGGESTION</Text><Text style={st.suggestionText}>{s.tip}</Text></View>
              </View>
            </View>
          ))}
        </View>
        {/* AI Insight */}
        <View style={[st.insightCard,S.xs]}>
          <View style={{flexDirection:"row",alignItems:"center",gap:7,marginBottom:8}}>
            <View style={st.insightIconWrap}><Text style={{fontSize:12}}>✦</Text></View>
            <Text style={st.insightLabelText}>AI IMPROVEMENT INSIGHT</Text>
          </View>
          <Text style={st.insightBodyText}>{aiInsight?aiInsight.detail:"You consistently follow through on physical activities but skip learning & leisure. Scheduling Yousician after gym could boost follow-through ~40%."}</Text>
          <View style={{flexDirection:"row",gap:8,marginTop:10}}>
            <TouchableOpacity style={[st.chatBtn,S.sm]} onPress={()=>{
              if(aiInsight) ctxEngineInsight(aiInsight.detail);
              router.push("/(tabs)/chat");
            }}><Text style={st.chatBtnText}>Chat about this</Text></TouchableOpacity>
            <TouchableOpacity style={st.dismissBtn}><Text style={st.dismissText}>Dismiss</Text></TouchableOpacity>
          </View>
        </View>
        {/* ── HOUSEHOLD IDENTITY (fix #4) — live + tappable + AI summary ── */}
        <SLabel text="🧬 HOUSEHOLD IDENTITY"/>
        <View style={[st.card,S.xs,{gap:0,padding:0,overflow:"hidden"}]}>

          {/* ① AI Personality Summary strip */}
          <View style={st.identSummaryBox}>
            <View style={{flexDirection:"row",alignItems:"center",gap:6,marginBottom:7}}>
              <View style={st.identSummaryIcon}><Text style={{fontSize:11}}>✦</Text></View>
              <Text style={st.identSummaryLabel}>AI PERSONALITY SNAPSHOT</Text>
              {/* Freshness badge */}
              <View style={[st.identFreshBadge,memoryFieldCount(memory)>0?{}:{backgroundColor:C.amberS,borderColor:C.amberB}]}>
                <Text style={[st.identFreshText,memoryFieldCount(memory)>0?{}:{color:"#92400E"}]}>
                  {memoryFieldCount(memory)>0?`${memoryFieldCount(memory)} live fields ✓`:"Using defaults"}
                </Text>
              </View>
            </View>
            <Text style={st.identSummaryText}>
              {buildPersonalitySummary(memory, location)}
            </Text>
          </View>

          <View style={{height:0.5,backgroundColor:C.bg2}}/>

          {/* ② Tappable preference pills — tap = get 3 AI ideas for that pref */}
          <View style={{padding:14,gap:0}}>
            <Text style={[st.identTapHint,{marginBottom:12}]}>
              Tap any tag to get personalised suggestions →
            </Text>
            {Object.entries(clusters).map(([cat,pills])=>(
              <View key={cat} style={st.clusterRow}>
                <Text style={st.clusterCat}>{cat}</Text>
                <View style={{flexDirection:"row",flexWrap:"wrap",marginLeft:-3}}>
                  {pills.map((p,i)=>(
                    <TappablePill
                      key={i}
                      label={p.label}
                      conf={p.conf}
                      onTap={()=>{
                        // Strip emoji prefix for a cleaner context label
                        const clean = p.label.replace(/^[\p{Emoji}\s]+/u,"").trim();
                        ctxPreferenceDrill(clean);
                        router.push("/(tabs)/chat");
                      }}
                    />
                  ))}
                </View>
              </View>
            ))}

            {/* ③ Ideas inbox row */}
            <View style={st.clusterRow}>
              <Text style={st.clusterCat}>
                💡 Ideas inbox {pendingIdeasCount>0?`(${pendingIdeasCount} pending)`:""}
              </Text>
              {pendingIdeasCount>0?(
                <View style={{flexDirection:"row",flexWrap:"wrap",marginLeft:-3}}>
                  {localIdeas.filter(i=>!i.converted).slice(0,4).map((idea)=>(
                    <TouchableOpacity
                      key={idea.id}
                      style={[st.pill,{backgroundColor:C.tealS,borderColor:C.teal+"40"},st.pillTappable]}
                      onPress={()=>{ ctxPreferenceDrill(idea.text.slice(0,60)); router.push("/(tabs)/chat"); }}
                      activeOpacity={0.65}>
                      <Text style={[st.pillText,{color:C.teal}]} numberOfLines={1}>
                        {idea.text.slice(0,26)}
                      </Text>
                      <Ionicons name="chevron-forward" size={9} color={C.teal} style={{marginLeft:2}}/>
                    </TouchableOpacity>
                  ))}
                </View>
              ):(
                <Text style={{fontSize:11,color:C.ink3,marginTop:4}}>
                  No ideas yet — add them in the Missions tab 💡
                </Text>
              )}
            </View>
          </View>

          <View style={{height:0.5,backgroundColor:C.bg2}}/>

          {/* ④ Quick-action footer row */}
          <View style={{flexDirection:"row",borderTopWidth:0,gap:0}}>
            <TouchableOpacity
              style={[st.identFooterBtn,{flex:1,borderRightWidth:0.5,borderRightColor:C.bg2}]}
              onPress={()=>{ ctxUpdateIdentity(); router.push("/(tabs)/chat"); }}>
              <Ionicons name="create-outline" size={13} color={C.acc}/>
              <Text style={st.identFooterBtnText}>Update preferences</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[st.identFooterBtn,{flex:1}]}
              onPress={()=>{ memRes.refetch(); }}>
              <Ionicons name="refresh-outline" size={13} color={C.ink3}/>
              <Text style={[st.identFooterBtnText,{color:C.ink3}]}>Refresh from memory</Text>
            </TouchableOpacity>
          </View>
        </View>
        {/* Engine room */}
        <SLabel text="⚙️ ENGINE ROOM"/>
        <View style={[st.card,S.xs,{padding:0,overflow:"hidden"}]}>
          {([["server-outline","API Endpoint",API_BASE,C.acc],["shield-checkmark-outline","Database","Supabase · Connected",C.green],["calendar-outline","Google Calendar","OAuth · Active",C.amber],["cpu-outline","AI Models","Claude + Groq","#7C3AED"]] as const).map(([icon,label,val,color],i,a)=>(
            <View key={label} style={[st.engineRow,i<a.length-1&&{borderBottomWidth:0.5,borderBottomColor:C.bg2}]}>
              <View style={[st.engineIcon,{backgroundColor:color+"18"}]}><Ionicons name={icon as any} size={14} color={color}/></View>
              <Text style={st.engineLabel}>{label}</Text><Text style={[st.engineVal,{color}]} numberOfLines={1}>{val}</Text>
            </View>
          ))}
        </View>
        <TouchableOpacity style={[st.docsBtn,S.xs]} onPress={()=>Linking.openURL(`${API_BASE}/docs`)}>
          <Ionicons name="code-slash-outline" size={14} color={C.acc}/><Text style={st.docsBtnText}>Open Swagger Docs</Text><Ionicons name="open-outline" size={13} color={C.acc}/>
        </TouchableOpacity>
        <View style={{height:32}}/>
      </ScrollView>
    </SafeAreaView>
  );

  if(view==="report") return (
    <SafeAreaView style={st.safe}>
      <View style={st.slideHeader}>
        <TouchableOpacity style={st.backBtn} onPress={()=>setView("engine")}><Ionicons name="chevron-back" size={16} color={C.acc}/></TouchableOpacity>
        <View style={{flex:1}}><Text style={st.headerSub}>FULL ANALYSIS</Text><Text style={st.headerTitle}>Pattern Report</Text></View>
        <View style={st.slideBadge}><Text style={st.slideBadgeText}>Live</Text></View>
      </View>
      <ScrollView contentContainerStyle={[st.content,{paddingHorizontal:hp()}]} showsVerticalScrollIndicator={false}>
        <View style={[st.patternHero,S.sm]}>
          <View style={{flexDirection:"row",alignItems:"center",gap:14}}>
            <View style={st.ringOuter}><Text style={[st.ringPct,{fontSize:15}]}>{completionPct}%</Text></View>
            <View><Text style={st.ringTitle}>{completionPct>=90?"Excellent":completionPct>=75?"Good":"Needs focus"}</Text><Text style={st.ringSubtitle}>{completedCount} of {totalCount} missions done</Text><Text style={[st.ringSubtitle,{marginTop:2}]}>{kpis.skipped_count?`${kpis.skipped_count} skipped`:"Keep it up!"}</Text></View>
          </View>
        </View>
        {insights.length>0&&(<><SLabel text="📊 LIVE PATTERN INSIGHTS"/><View style={[st.card,S.xs,{gap:9}]}>{insights.map((ins:any,i:number)=>{const{bg,border,text}=insightColors(ins.type);return <View key={i} style={[st.insightRow,{backgroundColor:bg,borderColor:border}]}><Text style={{fontSize:20,flexShrink:0}}>{ins.emoji}</Text><View style={{flex:1}}><Text style={[st.insightHead,{color:text}]}>{ins.headline}</Text><Text style={st.insightDetail}>{ins.detail}</Text></View></View>;})}</View></>)}
        <SLabel text="📊 COMPLETION BY CATEGORY"/>
        <View style={[st.card,S.xs]}>
          {categories.map((cat:any)=>(<View key={cat.label} style={{marginBottom:12}}><View style={{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:4}}><Text style={st.catLabel}>{cat.label}</Text><Text style={[st.catPct,{color:cat.color}]}>{cat.pct}%</Text></View><View style={st.barBg}><View style={[st.barFill,{width:`${cat.pct}%` as any,backgroundColor:cat.color}]}/></View><Text style={st.catNote}>{cat.note}</Text></View>))}
        </View>
        {weakest&&<View style={[st.weakestCard,S.xs]}><View style={{flexDirection:"row",alignItems:"center",gap:9,marginBottom:9}}><View style={st.weakestIcon}><Text style={{fontSize:14}}>🎯</Text></View><View><Text style={st.weakestLabel}>WEAKEST AREA · FOCUS HERE</Text><Text style={st.weakestTitle}>{weakest.label} — {weakest.pct}%</Text></View></View><Text style={st.weakestBody}>{aiInsight?.detail||`${weakest.label} is at ${weakest.pct}%. Pair related habits with existing routines.`}</Text><TouchableOpacity style={[st.buildBtn,S.sm,{marginTop:10}]} onPress={()=>router.push("/(tabs)/chat")}><Text style={st.buildBtnText}>Build a plan in Chat →</Text></TouchableOpacity></View>}
        <SLabel text="🧠 AI DEDUCTIONS"/>
        <View style={[st.card,S.xs,{gap:0}]}>
          {["You prefer morning workouts on weekends.","Researching Lenovo laptops for work.","Family outings succeed when booked 48h ahead."].filter((_,i)=>!dismissed.has(i)).length===0
            ?<Text style={{fontSize:13,color:C.ink3,textAlign:"center",padding:14}}>All reviewed ✓</Text>
            :["You prefer morning workouts on weekends.","Researching Lenovo laptops for work.","Family outings succeed when booked 48h ahead."].map((d,i)=>dismissed.has(i)?null:(
              <View key={i} style={[st.dedInline,i>0&&{borderTopWidth:0.5,borderTopColor:C.bg2}]}>
                <View style={{flexDirection:"row",alignItems:"flex-start",gap:8,marginBottom:8}}><View style={st.dedIconWrap}><Text style={{fontSize:11}}>✦</Text></View><Text style={st.dedText}>{d}</Text></View>
                <View style={{flexDirection:"row",gap:7}}>
                  <TouchableOpacity style={st.confirmBtn} onPress={()=>setDismissed(prev=>new Set([...prev,i]))}><Text style={st.confirmText}>✓ Confirm</Text></TouchableOpacity>
                  <TouchableOpacity style={st.forgetBtn} onPress={()=>setDismissed(prev=>new Set([...prev,i]))}><Text style={st.forgetText}>✕ Forget</Text></TouchableOpacity>
                </View>
              </View>
            ))}
        </View>
        <View style={[st.insightCard,S.xs]}>
          <View style={{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:7}}><Text style={st.insightLabelText}>MEMORY HEALTH</Text><Text style={[st.insightLabelText,{fontSize:13}]}>{kpis.total_feedback>10?"85%":"74%"}</Text></View>
          <View style={st.barBg}><View style={[st.barFill,{width:kpis.total_feedback>10?"85%":"74%",backgroundColor:C.acc2}]}/></View>
          <Text style={[st.insightBodyText,{marginTop:8,marginBottom:10}]}>{kpis.total_feedback>0?`${kpis.total_feedback} feedback events logged.`:"Review pending deductions to improve accuracy."}</Text>
          {["Confirm pending deductions.","Add your work hours.","Add Drishti's school schedule."].map(s=>(
            <TouchableOpacity key={s} style={{flexDirection:"row",alignItems:"flex-start",gap:8,marginBottom:7}} onPress={()=>router.push("/(tabs)/chat")}><View style={[st.insightIconWrap,{marginTop:1}]}><Ionicons name="add" size={9} color={C.acc}/></View><Text style={[st.insightBodyText,{flex:1}]}>{s}</Text></TouchableOpacity>
          ))}
        </View>
        <SLabel text="🔧 CORRECTIONS LOG"/>
        <View style={[st.card,S.xs,{padding:0,overflow:"hidden"}]}>
          {[{when:"3 days ago",wrong:"Suggested dal makhani every Monday",fix:"User prefers variety"},{when:"1 week ago",wrong:"Assumed gym is 10 min away",fix:"EōS Fitness is 22 min from home"}].map((c,i,a)=>(
            <View key={i} style={[st.corrRow,i<a.length-1&&{borderBottomWidth:0.5,borderBottomColor:C.bg2}]}>
              <View style={st.corrBadge}><Text style={st.corrBadgeText}>CORRECTED · {c.when}</Text></View>
              <Text style={st.corrWrong}>{c.wrong}</Text>
              <View style={{flexDirection:"row",alignItems:"flex-start",gap:6}}><Ionicons name="checkmark" size={13} color={C.green} style={{marginTop:2}}/><Text style={st.corrFix}>{c.fix}</Text></View>
            </View>
          ))}
        </View>
        <SLabel text="✨ RECENTLY LEARNED PREFERENCES"/>
        <View style={[st.card,S.xs,{padding:0,overflow:"hidden"}]}>
          {([{e:"🎬",l:"Sci-Fi + AI films",c:"high"},{e:"🍲",l:"Indian cuisine",c:"high"},{e:"⏰",l:"Morning window 7–10 AM",c:"high"},{e:"📱",l:"Short voice notes",c:"med"}] as Array<{e:string;l:string;c:Confidence}>).map((p,i,a)=>(
            <View key={i} style={[st.prefRow,i<a.length-1&&{borderBottomWidth:0.5,borderBottomColor:C.bg2}]}><Text style={{fontSize:16}}>{p.e}</Text><Text style={st.prefLabel}>{p.l}</Text><Pill label={p.c==="high"?"High":"Medium"} conf={p.c}/></View>
          ))}
        </View>
        <View style={{height:32}}/>
      </ScrollView>
    </SafeAreaView>
  );

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.slideHeader}>
        <TouchableOpacity style={st.backBtn} onPress={()=>setView("engine")}><Ionicons name="chevron-back" size={16} color={C.acc}/></TouchableOpacity>
        <View style={{flex:1}}><Text style={st.headerSub}>ENGINE → EDIT</Text><Text style={st.headerTitle}>Profile Studio</Text></View>
        <View style={st.slideBadge}><Text style={st.slideBadgeText}>Khandare</Text></View>
      </View>
      <ScrollView contentContainerStyle={[st.content,{paddingHorizontal:hp()}]} showsVerticalScrollIndicator={false}>
        {[{e:"👨‍👩‍👧",t:"Household",items:["Primary adult","Partner","Young child"]},{e:"🌟",t:"Lifestyle",items:["Family activities","Food ideas","Wellness","Entertainment","Local outing"]},{e:"🗺️",t:"Local world",items:["Tampa, FL","Local: up to 20 mi","Weekend: up to 75 mi"]},{e:"📅",t:"Weekend & Planning",items:["Social & lively","Balanced planner"]},{e:"🎙️",t:"Tone",items:["Balanced"]}].map(s=>(
          <View key={s.t} style={[st.card,S.xs]}>
            <View style={{flexDirection:"row",alignItems:"center",gap:8,marginBottom:8}}><Text style={{fontSize:18}}>{s.e}</Text><Text style={[st.clusterCat,{flex:1}]}>{s.t}</Text><TouchableOpacity style={st.editBtn}><Text style={st.editBtnText}>Edit</Text></TouchableOpacity></View>
            <View style={{flexDirection:"row",flexWrap:"wrap",gap:7}}>{s.items.map(item=><View key={item} style={st.profilePill}><Text style={st.profilePillText}>{item}</Text></View>)}</View>
          </View>
        ))}
        <View style={st.noteBox}><Text style={st.noteText}>✏️ Changes save automatically and improve suggestions from the next session.</Text></View>
        <View style={{height:32}}/>
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe:{flex:1,backgroundColor:C.bg},header:{flexDirection:"row",alignItems:"center",justifyContent:"space-between",paddingHorizontal:18,paddingVertical:13,backgroundColor:C.bgCard,borderBottomWidth:0.5,borderBottomColor:C.border2,shadowColor:"#6D28D9",shadowOffset:{width:0,height:1},shadowOpacity:0.06,shadowRadius:4,elevation:2},
  slideHeader:{flexDirection:"row",alignItems:"center",gap:10,paddingHorizontal:16,paddingVertical:13,backgroundColor:C.bgCard,borderBottomWidth:0.5,borderBottomColor:C.border2,shadowColor:"#6D28D9",shadowOffset:{width:0,height:1},shadowOpacity:0.06,shadowRadius:4,elevation:2},
  backBtn:{width:32,height:32,borderRadius:R.sm,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},
  slideBadge:{backgroundColor:C.soft,borderRadius:R.full,borderWidth:0.5,borderColor:C.border,paddingHorizontal:10,paddingVertical:4},
  slideBadgeText:{fontSize:11,fontWeight:"700",color:C.acc},
  headerSub:{fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1},headerTitle:{fontSize:18,fontWeight:"800",color:C.ink,marginTop:1},
  refreshBtn:{padding:8,borderRadius:R.sm,backgroundColor:C.bg2},content:{paddingTop:14,paddingBottom:32,gap:13},
  sl:{fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1.2,marginBottom:8},
  card:{backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,padding:14},
  profileCard:{flexDirection:"row",alignItems:"center",gap:12,backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border,padding:14},
  avatarRing:{width:50,height:50,borderRadius:25,backgroundColor:C.soft,borderWidth:2,borderColor:C.acc,alignItems:"center",justifyContent:"center"},
  profileName:{fontSize:14,fontWeight:"800",color:C.ink},profileEmail:{fontSize:11,color:C.ink2},profileLoc:{fontSize:11,color:C.ink3},
  activeBadge:{flexDirection:"row",alignItems:"center",gap:4,backgroundColor:C.greenS,borderWidth:0.5,borderColor:C.greenB,borderRadius:R.full,paddingHorizontal:8,paddingVertical:3},
  activeDot:{width:6,height:6,borderRadius:3,backgroundColor:C.green},activeText:{fontSize:9,fontWeight:"700",color:"#065F46",letterSpacing:0.7},
  profileStudioBtn:{backgroundColor:C.soft,borderRadius:R.sm,borderWidth:0.5,borderColor:C.border,paddingHorizontal:9,paddingVertical:5},profileStudioText:{fontSize:11,fontWeight:"700",color:C.acc},
  statRow:{flexDirection:"row",backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,overflow:"hidden"},
  statBox:{flex:1,alignItems:"center",paddingVertical:12},statNum:{fontSize:20,fontWeight:"800",color:C.acc},statLbl:{fontSize:10,color:C.ink3,marginTop:2},
  patternHero:{backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border,padding:16},
  patternIconWrap:{width:28,height:28,borderRadius:R.sm,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},
  patternLabel:{fontSize:10,fontWeight:"700",color:C.acc,letterSpacing:1},patternSubLabel:{fontSize:13,fontWeight:"800",color:C.ink},
  ringRow:{flexDirection:"row",alignItems:"center",gap:14,backgroundColor:C.soft,borderRadius:R.lg,padding:12,marginBottom:10},
  ringOuter:{width:64,height:64,borderRadius:32,borderWidth:6,borderColor:C.acc2,backgroundColor:C.bgCard,alignItems:"center",justifyContent:"center",flexShrink:0},
  ringPct:{fontSize:13,fontWeight:"800",color:C.acc},ringTitle:{fontSize:14,fontWeight:"800",color:C.ink},ringSubtitle:{fontSize:12,color:C.ink2,marginTop:2},
  ringBadge:{backgroundColor:C.greenS,borderRadius:R.full,paddingHorizontal:9,paddingVertical:3,marginTop:5,alignSelf:"flex-start"},ringBadgeText:{fontSize:10,fontWeight:"700",color:C.green},
  miniStatBox:{flex:1,backgroundColor:C.bg2,borderRadius:R.lg,padding:9,alignItems:"center",borderWidth:0.5,borderColor:C.border2},miniStatVal:{fontSize:16,fontWeight:"800"},miniStatLbl:{fontSize:10,color:C.ink3,marginTop:2},
  viewReportBtn:{backgroundColor:C.acc2,borderRadius:R.lg,padding:11,alignItems:"center",shadowColor:"#6D28D9",shadowOffset:{width:0,height:2},shadowOpacity:0.18,shadowRadius:4,elevation:3},viewReportText:{fontSize:13,fontWeight:"700",color:"#fff"},
  insightRow:{flexDirection:"row",alignItems:"flex-start",gap:10,borderRadius:R.lg,borderWidth:0.5,padding:11},insightHead:{fontSize:13,fontWeight:"700",marginBottom:3},insightDetail:{fontSize:12,color:C.ink2,lineHeight:18},
  streakRow:{flexDirection:"row",alignItems:"center",gap:9,padding:11},streakTitle:{fontSize:13,fontWeight:"700",color:C.ink},streakSub:{fontSize:11,color:C.ink3},streakBadge:{borderRadius:R.full,paddingHorizontal:9,paddingVertical:3},streakPct:{fontSize:11,fontWeight:"700"},
  skippedRow:{flexDirection:"row",alignItems:"flex-start",gap:9,padding:11},skippedIcon:{width:32,height:32,borderRadius:R.sm,backgroundColor:C.redS,alignItems:"center",justifyContent:"center",flexShrink:0},skippedTitle:{fontSize:13,fontWeight:"700",color:C.ink},skippedBadge:{backgroundColor:C.redS,borderRadius:R.full,paddingHorizontal:8,paddingVertical:2},skippedBadgeText:{fontSize:10,fontWeight:"700",color:C.red},
  suggestionBox:{backgroundColor:C.amberS,borderRadius:R.sm,padding:7,borderLeftWidth:2,borderLeftColor:C.amber},suggestionLabel:{fontSize:9,fontWeight:"700",color:C.amber,marginBottom:2},suggestionText:{fontSize:11,color:"#78350F",lineHeight:16},
  insightCard:{backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border,padding:14},insightIconWrap:{width:22,height:22,borderRadius:R.xs,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},insightLabelText:{fontSize:10,fontWeight:"700",color:C.acc,letterSpacing:1},insightBodyText:{fontSize:13,color:C.ink2,lineHeight:20},
  chatBtn:{flex:1,backgroundColor:C.acc2,borderRadius:R.lg,paddingVertical:10,alignItems:"center"},chatBtnText:{fontSize:12,fontWeight:"700",color:"#fff"},dismissBtn:{flex:1,backgroundColor:C.bg2,borderRadius:R.lg,paddingVertical:10,alignItems:"center",borderWidth:0.5,borderColor:C.border2},dismissText:{fontSize:12,fontWeight:"600",color:C.ink2},
  clusterRow:{marginBottom:12},clusterCat:{fontSize:12,fontWeight:"700",color:C.ink,marginBottom:7},
  pill:{paddingHorizontal:10,paddingVertical:4,borderRadius:R.full,borderWidth:0.5,margin:3},
  pillTappable:{flexDirection:"row",alignItems:"center",paddingRight:7},
  pillText:{fontSize:11,fontWeight:"700"},
  // ── Household Identity card (fix #4) ────────────────────────────────────────
  identSummaryBox:{backgroundColor:C.soft,padding:14},
  identSummaryIcon:{width:20,height:20,borderRadius:5,backgroundColor:C.bgCard,borderWidth:0.5,borderColor:C.border,alignItems:"center",justifyContent:"center"},
  identSummaryLabel:{fontSize:10,fontWeight:"700",color:C.acc,letterSpacing:1,flex:1},
  identSummaryText:{fontSize:12,color:C.ink2,lineHeight:19},
  identFreshBadge:{backgroundColor:C.greenS,borderRadius:R.full,borderWidth:0.5,borderColor:C.greenB,paddingHorizontal:8,paddingVertical:2},
  identFreshText:{fontSize:9,fontWeight:"700",color:"#065F46"},
  identTapHint:{fontSize:10,color:C.ink3,fontStyle:"italic"},
  identFooterBtn:{flexDirection:"row",alignItems:"center",justifyContent:"center",gap:6,paddingVertical:11,backgroundColor:C.bg2},
  identFooterBtnText:{fontSize:11,fontWeight:"700",color:C.acc},
  engineRow:{flexDirection:"row",alignItems:"center",gap:11,paddingHorizontal:13,paddingVertical:11},engineIcon:{width:30,height:30,borderRadius:R.sm,alignItems:"center",justifyContent:"center"},engineLabel:{flex:1,fontSize:13,color:C.ink,fontWeight:"500"},engineVal:{fontSize:11,fontWeight:"700",maxWidth:140},
  docsBtn:{flexDirection:"row",alignItems:"center",justifyContent:"center",gap:7,paddingVertical:11,backgroundColor:C.soft,borderRadius:R.lg,borderWidth:0.5,borderColor:C.border},docsBtnText:{fontSize:13,fontWeight:"700",color:C.acc},
  dedInline:{padding:12},dedIconWrap:{width:22,height:22,borderRadius:R.xs,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},dedText:{fontSize:13,color:C.ink2,lineHeight:19,flex:1},
  confirmBtn:{flex:1,backgroundColor:C.greenS,borderRadius:R.sm,borderWidth:0.5,borderColor:C.greenB,paddingVertical:8,alignItems:"center"},confirmText:{fontSize:12,fontWeight:"700",color:"#065F46"},forgetBtn:{flex:1,backgroundColor:C.redS,borderRadius:R.sm,borderWidth:0.5,borderColor:C.redB,paddingVertical:8,alignItems:"center"},forgetText:{fontSize:12,fontWeight:"700",color:C.red},
  catLabel:{fontSize:12,fontWeight:"600",color:C.ink},catPct:{fontSize:12,fontWeight:"800"},barBg:{height:6,backgroundColor:C.bg2,borderRadius:3,overflow:"hidden",marginBottom:3},barFill:{height:"100%",borderRadius:3},catNote:{fontSize:10,color:C.ink3},
  weakestCard:{backgroundColor:C.redS,borderRadius:R.xl,borderWidth:0.5,borderColor:C.redB,padding:14},weakestIcon:{width:28,height:28,borderRadius:R.sm,backgroundColor:C.red,alignItems:"center",justifyContent:"center"},weakestLabel:{fontSize:10,fontWeight:"700",color:C.red,letterSpacing:1},weakestTitle:{fontSize:13,fontWeight:"800",color:"#7F1D1D"},weakestBody:{fontSize:13,color:"#7F1D1D",lineHeight:19},buildBtn:{backgroundColor:C.red,borderRadius:R.lg,padding:11,alignItems:"center"},buildBtnText:{fontSize:12,fontWeight:"700",color:"#fff"},
  corrRow:{padding:12,gap:5},corrBadge:{backgroundColor:C.redS,borderRadius:R.full,paddingHorizontal:8,paddingVertical:2,alignSelf:"flex-start"},corrBadgeText:{fontSize:10,fontWeight:"700",color:C.red},corrWrong:{fontSize:12,color:C.ink3,textDecorationLine:"line-through"},corrFix:{fontSize:12,fontWeight:"600",color:C.green,flex:1},
  prefRow:{flexDirection:"row",alignItems:"center",gap:9,padding:11},prefLabel:{flex:1,fontSize:12,color:C.ink,fontWeight:"500"},
  editBtn:{backgroundColor:C.soft,borderRadius:R.sm,borderWidth:0.5,borderColor:C.border,paddingHorizontal:9,paddingVertical:5},editBtnText:{fontSize:11,fontWeight:"700",color:C.acc},profilePill:{backgroundColor:C.bg2,borderRadius:R.full,paddingHorizontal:10,paddingVertical:4},profilePillText:{fontSize:12,color:C.ink2,fontWeight:"500"},
  noteBox:{backgroundColor:C.amberS,borderRadius:R.lg,borderWidth:0.5,borderColor:C.amberB,padding:13},noteText:{fontSize:12,color:"#78350F",lineHeight:18},
});
