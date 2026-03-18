// app/(tabs)/missions.tsx  —  Missions (v3 Lavender)
import React, { useEffect, useState, useCallback } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, ActivityIndicator,
  StyleSheet, SafeAreaView, RefreshControl, Platform, Dimensions, TextInput,
  Modal,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "expo-router";
import { useRouter } from "expo-router";
import { C, R, S, USER_ID } from "../constants/config";
import { getIdeas, addIdea, convertIdea, removeIdea, syncFromRemote, Idea } from "../context/IdeasStore";
import { ctxMissionCreate, ctxMissionInsight } from "../context/ChatContextStore";
import { useGet, apiPost } from "../hooks/useApi";

const MAX_W = 820;
const hp = () => Platform.OS==="web" ? Math.max(16,(Dimensions.get("window").width-MAX_W)/2) : 16;

type FilterTab = "pending"|"reviewed"|"all";

interface Mission {
  id:string; title:string;
  status:"pending"|"reviewed";
  end_time:string|null;
  snoozed_until?:string|null;
}

function isPast(iso:string|null):boolean { return iso ? new Date(iso).getTime() < Date.now() : false; }
function fmtRel(iso:string|null):string {
  if (!iso) return "";
  try {
    const diff = new Date(iso).getTime()-Date.now();
    const days = Math.round(diff/86400000);
    if(days===0)return "Today"; if(days===1)return "Tomorrow"; if(days===-1)return "Yesterday";
    if(days<0)return `${Math.abs(days)}d ago`; return `In ${days}d`;
  } catch { return iso.slice(0,10); }
}

const HABIT_SUGGESTIONS = [
  {emoji:"🏋️",title:"Gym session",       desc:"EōS Fitness — M/W/F",          bg:C.redS,  border:C.red},
  {emoji:"🛒",title:"Weekly grocery",    desc:"Patel Brothers essentials",      bg:C.greenS,border:C.green},
  {emoji:"🎸",title:"Yousician",         desc:"30 min daily builds skill fast", bg:C.amberS,border:C.amber},
  {emoji:"👨‍👧",title:"Family outing",    desc:"Plan something this weekend",    bg:C.soft,  border:C.acc},
  {emoji:"💊",title:"Health check-in",   desc:"Schedule next doctor visit",     bg:C.redS,  border:C.red},
];

// ── Idea grouping ─────────────────────────────────────────────────────────────
// Dynamic keyword-based classifier. Order matters — first match wins.
// Only groups that actually have ideas are rendered (no empty headers).
const IDEA_GROUPS: Array<{emoji:string; label:string; keywords:string[]}> = [
  {emoji:"🌿", label:"Outdoors & Nature",  keywords:["hike","hiking","kayak","park","river","trail","nature","beach","camp","outdoor","spring break","waterfall","lake","forest"]},
  {emoji:"🎭", label:"Culture & Outings",  keywords:["cultural","culture","market","event","festival","museum","temple","attraction","ybor","outing","show","exhibit","fair"]},
  {emoji:"🎯", label:"Learning & Skills",  keywords:["learn","lesson","guitar","piano","casio","library","prompt","skill","course","class","study","read","book","practice","workshop"]},
  {emoji:"🏃", label:"Fitness & Sport",    keywords:["cricket","gym","sport","fitness","swim","run","yoga","workout","play","judo","volleyball","tennis","cycling","bike"]},
  {emoji:"👨‍👩‍👧", label:"Family",          keywords:["spouse","family","kids","child","daughter","drishti","together","sonam","date","dinner","movie"]},
  {emoji:"💼", label:"Work & Projects",    keywords:["build","create","project","tool","app","work","code","develop","design","automate","launch"]},
];

function classifyIdea(text: string): {emoji:string; label:string} {
  const lower = text.toLowerCase();
  for (const g of IDEA_GROUPS) {
    if (g.keywords.some(kw => lower.includes(kw))) {
      return {emoji: g.emoji, label: g.label};
    }
  }
  return {emoji:"💡", label:"Other"};
}

// Returns only groups that have at least one idea (pending or converted)
function groupIdeas(ideas: Idea[]): Array<{emoji:string; label:string; ideas:Idea[]}> {
  const map = new Map<string, {emoji:string; label:string; ideas:Idea[]}>();
  for (const idea of ideas) {
    const {emoji, label} = classifyIdea(idea.text);
    const key = label;
    if (!map.has(key)) map.set(key, {emoji, label, ideas:[]});
    map.get(key)!.ideas.push(idea);
  }
  // Maintain IDEA_GROUPS order, then append "Other" at end
  const ordered: Array<{emoji:string; label:string; ideas:Idea[]}> = [];
  for (const g of IDEA_GROUPS) {
    if (map.has(g.label)) ordered.push(map.get(g.label)!);
  }
  if (map.has("Other")) ordered.push(map.get("Other")!);
  return ordered;
}

const PRODUCTIVITY_TIPS = [
  {icon:"bulb-outline"     as const, color:C.amber,  tip:"Batch similar errands — saves 40% of driving time."},
  {icon:"time-outline"     as const, color:C.acc,    tip:"Best time to plan next week is Sunday evening."},
  {icon:"trending-up-outline"as const,color:C.green, tip:"Tracking completion rate boosts follow-through by 25%."},
  {icon:"heart-outline"    as const, color:C.red,    tip:"Family dinner 3× per week correlates with stronger bonds."},
];

function MissionCard({ mission, onComplete, onSnooze }:{
  mission:Mission; onComplete:(id:string)=>void; onSnooze:(id:string)=>void;
}) {
  const past=isPast(mission.end_time), pending=mission.status==="pending";
  const isOverdue=past&&pending;
  return (
    <View style={[mc.card, isOverdue&&mc.overdue, !pending&&mc.done, S.xs]}>
      <View style={[mc.accent,{backgroundColor:!pending?C.green:isOverdue?C.red:C.acc}]}/>
      <View style={mc.icon}>
        <Ionicons name={!pending?"checkmark-circle":isOverdue?"alert-circle":"ellipse-outline"} size={20}
          color={!pending?C.green:isOverdue?C.red:C.acc}/>
      </View>
      <View style={mc.body}>
        <Text style={[mc.title,!pending&&mc.titleDone]} numberOfLines={2}>{mission.title}</Text>
        {mission.end_time&&(
          <View style={mc.metaRow}>
            <Ionicons name="time-outline" size={10} color={isOverdue?C.red:C.ink3}/>
            <Text style={[mc.meta,isOverdue&&{color:C.red,fontWeight:"700"}]}>{fmtRel(mission.end_time)}</Text>
            {isOverdue&&<View style={mc.overdueBadge}><Text style={mc.overdueText}>OVERDUE</Text></View>}
          </View>
        )}
      </View>
      {pending&&(
        <View style={mc.actions}>
          <TouchableOpacity style={mc.completeBtn} onPress={()=>onComplete(mission.id)}>
            <Ionicons name="checkmark" size={13} color="#fff"/>
          </TouchableOpacity>
          <TouchableOpacity style={mc.snoozeBtn} onPress={()=>onSnooze(mission.id)}>
            <Ionicons name="alarm-outline" size={13} color={C.ink2}/>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const mc = StyleSheet.create({
  card:        {flexDirection:"row",alignItems:"center",backgroundColor:C.bgCard,borderRadius:R.lg,borderWidth:0.5,borderColor:C.border2,marginBottom:8,overflow:"hidden"},
  overdue:     {borderColor:C.redB,backgroundColor:C.redS},
  done:        {opacity:0.55},
  accent:      {width:3,alignSelf:"stretch"},
  icon:        {padding:11},
  body:        {flex:1,paddingVertical:11,paddingRight:8,gap:4},
  title:       {fontSize:13,fontWeight:"600",color:C.ink},
  titleDone:   {textDecorationLine:"line-through",color:C.ink3},
  metaRow:     {flexDirection:"row",alignItems:"center",gap:5},
  meta:        {fontSize:11,color:C.ink3},
  overdueBadge:{paddingHorizontal:6,paddingVertical:1,backgroundColor:C.redB,borderRadius:R.full},
  overdueText: {fontSize:9,fontWeight:"700",color:C.red,letterSpacing:0.5},
  actions:     {flexDirection:"row",gap:6,paddingRight:11},
  completeBtn: {width:30,height:30,borderRadius:15,backgroundColor:C.green,alignItems:"center",justifyContent:"center"},
  snoozeBtn:   {width:30,height:30,borderRadius:15,backgroundColor:C.bg2,borderWidth:0.5,borderColor:C.border2,alignItems:"center",justifyContent:"center"},
});

export default function MissionsScreen() {
  const router = useRouter();
  const [filter,     setFilter]     = useState<FilterTab>("pending");
  const [refreshing, setRefreshing] = useState(false);
  const [showAll,    setShowAll]    = useState(false);
  const [ideaDraft,  setIdeaDraft]  = useState("");
  const [feedback,   setFeedback]   = useState<{missionId:string;title:string}|null>(null);
  const [feedbackNote, setFeedbackNote] = useState("");
  const [feedbackReason, setFeedbackReason] = useState("");
  const [localIdeas, setLocalIdeas] = useState<Idea[]>([]);

  useFocusEffect(useCallback(()=>{
    syncFromRemote().then(setLocalIdeas);
    res.refetch();
    resAll.refetch();
  },[]));

  // Filtered list — drives the visible mission cards
  const res      = useGet<{missions:Mission[]}>(`/api/missions?user_id=${USER_ID}&status=${filter}`);
  // All missions — drives the stats strip (always accurate regardless of filter)
  const resAll   = useGet<{missions:Mission[]}>(`/api/missions?user_id=${USER_ID}&status=all`);
  useEffect(()=>{ res.refetch(); },[filter]);
  const onRefresh=async()=>{ setRefreshing(true); res.refetch(); setRefreshing(false); };

  const missions    = res.data?.missions    || [];   // filtered — for cards
  const allMissions = resAll.data?.missions || [];   // all — for stats
  const overdue  = allMissions.filter(m=>m.status==="pending"&&isPast(m.end_time));
  const onTime   = allMissions.filter(m=>m.status==="pending"&&!isPast(m.end_time));
  const reviewed = allMissions.filter(m=>m.status==="reviewed");

  const handleComplete=async(id:string)=>{
    try { await apiPost(`/api/missions/${id}/complete`,{}); res.refetch(); resAll.refetch(); } catch {}
  };

  const handleSnooze=(id:string)=>{
    const mission = missions.find(m=>m.id===id);
    setFeedbackNote("");
    setFeedbackReason("");
    setFeedback({missionId:id, title:mission?.title||"this mission"});
  };

  const submitFeedback=async()=>{
    if(!feedback) return;
    const isAlreadyDone = feedbackReason === "Already done";

    try {
      if (isAlreadyDone) {
        // ── "Already done" → mark complete + log positive feedback to memory
        await apiPost(`/api/missions/${feedback.missionId}/complete`, {});
        await apiPost("/api/feedback", {
          user_id:       USER_ID,
          mission:       feedback.title,
          feedback:      feedbackNote || "Already completed",
          rating:        "thumbs_up",   // positive signal for memory
          feedback_type: "completed",
          reason:        feedbackReason,
          note:          feedbackNote,
        });
      } else {
        // ── Any other reason → snooze 1 day + log skip feedback
        const until = new Date(Date.now() + 86400000).toISOString();
        await apiPost(`/api/missions/${feedback.missionId}/snooze`, {
          snoozed_until: until,
          feedback_note: feedbackNote,
          reason:        feedbackReason,
        });
        await apiPost("/api/feedback", {
          user_id:       USER_ID,
          mission:       feedback.title,
          feedback:      feedbackNote || feedbackReason,
          rating:        "thumbs_down",
          feedback_type: "skipped",
          reason:        feedbackReason,
          note:          feedbackNote,
        });
      }
      res.refetch();
      resAll.refetch();
    } catch {}
    setFeedback(null);
  };

  function handleAddIdea(){
    if(!ideaDraft.trim()) return;
    addIdea(ideaDraft.trim()).then(setLocalIdeas);
    setIdeaDraft("");
  }

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.header}>
        <View>
          <Text style={st.headerSub}>COMMAND CENTER</Text>
          <Text style={st.headerTitle}>Missions</Text>
        </View>
        <TouchableOpacity style={[st.addBtn,S.sm]} onPress={()=>router.push("/(tabs)/chat")}>
          <Ionicons name="add" size={18} color="#fff"/>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={[st.content,{paddingHorizontal:hp()}]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.acc}/>}
        showsVerticalScrollIndicator={false}
      >
        {/* Stats */}
        <View style={[st.statsRow,S.xs]}>
          {[[String(onTime.length),"On Track",C.acc],[String(overdue.length),"Overdue",overdue.length>0?C.red:C.green],[String(reviewed.length),"Completed",C.green]].map(([v,l,c],i)=>(
            <View key={l} style={[st.statBox,i<2&&{borderRightWidth:0.5,borderRightColor:C.bg2}]}>
              <Text style={[st.statNum,{color:c as string}]}>{v}</Text>
              <Text style={st.statLbl}>{l}</Text>
            </View>
          ))}
        </View>

        {/* Overdue alert */}
        {overdue.length>0&&(
          <View style={st.overdueAlert}>
            <Ionicons name="alert-circle" size={15} color={C.red}/>
            <Text style={st.overdueAlertText}>{overdue.length} mission{overdue.length!==1?"s":""} past due — complete or reschedule.</Text>
          </View>
        )}

        {/* Filter tabs */}
        <View style={st.filterRow}>
          {(["pending","reviewed","all"] as FilterTab[]).map(f=>(
            <TouchableOpacity key={f} onPress={()=>setFilter(f)}
              style={[st.filterTab,filter===f&&st.filterTabActive]}>
              <Text style={[st.filterText,filter===f&&st.filterTextActive]}>
                {f==="pending"?"Active":f==="reviewed"?"Done":"All"}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Mission list */}
        {res.loading
          ? <ActivityIndicator color={C.acc} style={{marginVertical:24}}/>
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
            ) : (
              <View>
                {missions.slice(0, showAll ? missions.length : 10).map(m=>(
                  <MissionCard key={m.id} mission={m} onComplete={handleComplete} onSnooze={handleSnooze}/>
                ))}
                {missions.length>10&&(
                  <TouchableOpacity style={st.showMoreBtn} onPress={()=>setShowAll(!showAll)}>
                    <Text style={st.showMoreText}>
                      {showAll ? "Show less ↑" : `Show ${missions.length-10} more ↓`}
                    </Text>
                  </TouchableOpacity>
                )}
              </View>
            )
        }

        {/* Ideas inbox */}
        <View style={st.ideasHeader}>
          <Text style={st.sl}>💡 IDEAS INBOX</Text>
          {localIdeas.filter(i=>!i.converted).length>0&&(
            <View style={st.ideasBadge}>
              <Text style={st.ideasBadgeText}>{localIdeas.filter(i=>!i.converted).length} pending</Text>
            </View>
          )}
        </View>

        {/* Capture input */}
        <View style={[st.captureCard,S.xs]}>
          <View style={st.captureRow}>
            <TextInput
              style={st.captureInput}
              value={ideaDraft}
              onChangeText={setIdeaDraft}
              placeholder="Drop an idea here…"
              placeholderTextColor={C.ink3}
              onSubmitEditing={handleAddIdea}
              returnKeyType="done"
            />
            <TouchableOpacity
              style={[st.captureBtn,!ideaDraft.trim()&&{opacity:0.4}]}
              onPress={handleAddIdea} disabled={!ideaDraft.trim()}>
              <Ionicons name="add" size={14} color="#fff"/>
            </TouchableOpacity>
          </View>
          <TouchableOpacity style={st.voiceRow} onPress={()=>router.push("/(tabs)/chat")}>
            <View style={st.voiceIcon}>
              <Ionicons name="chatbubble-outline" size={12} color={C.acc}/>
            </View>
            <Text style={st.voiceText}>Or capture via voice in Chat →</Text>
          </TouchableOpacity>
        </View>

        {/* Ideas list — grouped by category */}
        {localIdeas.length>0&&(
          <View style={{gap:10}}>
            {groupIdeas(localIdeas).map(group=>(
              <View key={group.label} style={[st.ideasList,S.xs]}>
                {/* Group header */}
                <View style={st.ideaGroupHeader}>
                  <Text style={st.ideaGroupEmoji}>{group.emoji}</Text>
                  <Text style={st.ideaGroupLabel}>{group.label}</Text>
                  <View style={st.ideaGroupCount}>
                    <Text style={st.ideaGroupCountText}>
                      {group.ideas.filter(i=>!i.converted).length} pending
                    </Text>
                  </View>
                </View>
                {/* Ideas in group */}
                {group.ideas.map((idea,i)=>(
                  <View key={idea.id||String(i)}
                    style={[st.ideaRow, i===group.ideas.length-1&&{borderBottomWidth:0}, idea.converted&&{opacity:0.45}]}>
                    <View style={st.ideaIcon}>
                      <Ionicons name={idea.converted?"checkmark":"bulb-outline"} size={13}
                        color={idea.converted?C.green:C.acc}/>
                    </View>
                    <Text style={[st.ideaText,idea.converted&&{textDecorationLine:"line-through",color:C.ink3}]}>
                      {idea.text}
                    </Text>
                    {!idea.converted&&<>
                      <TouchableOpacity style={st.convertBtn}
                        onPress={()=>convertIdea(idea.id).then(setLocalIdeas)}>
                        <Text style={st.convertText}>→ Mission</Text>
                      </TouchableOpacity>
                      <TouchableOpacity onPress={()=>removeIdea(idea.id).then(setLocalIdeas)}>
                        <Ionicons name="close" size={14} color={C.ink3}/>
                      </TouchableOpacity>
                    </>}
                  </View>
                ))}
              </View>
            ))}
          </View>
        )}


        {/* Habit suggestions */}
        <Text style={st.sl}>💡 SUGGESTED HABITS FOR YOUR FAMILY</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={{flexDirection:"row",gap:9,paddingBottom:4}}>
            {HABIT_SUGGESTIONS.map((h,i)=>(
              <TouchableOpacity key={i}
                style={[st.habitCard,{backgroundColor:h.bg,borderColor:h.border+"60"}]}
                onPress={()=>router.push("/(tabs)/chat")}>
                <Text style={{fontSize:24,marginBottom:6}}>{h.emoji}</Text>
                <Text style={st.habitTitle}>{h.title}</Text>
                <Text style={st.habitDesc}>{h.desc}</Text>
                <View style={[st.habitAddBtn,{borderColor:h.border+"60"}]}>
                  <Text style={st.habitAddText}>+ Add Mission</Text>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>

        {/* Productivity tips */}
        <Text style={st.sl}>🧠 PRODUCTIVITY INSIGHTS</Text>
        <View style={[st.tipsCard,S.xs]}>
          {PRODUCTIVITY_TIPS.map((t,i)=>(
            <View key={i} style={[st.tipRow,i===PRODUCTIVITY_TIPS.length-1&&{borderBottomWidth:0}]}>
              <View style={[st.tipIcon,{backgroundColor:t.color+"18"}]}>
                <Ionicons name={t.icon} size={14} color={t.color}/>
              </View>
              <Text style={st.tipText}>{t.tip}</Text>
            </View>
          ))}
        </View>

        {/* Chat CTA */}
        <TouchableOpacity style={[st.chatCta,S.md]} onPress={()=>{
          ctxMissionCreate(onTime.length, overdue.length);
          router.push("/(tabs)/chat");
        }}>
          <Ionicons name="chatbubble-outline" size={17} color="#fff"/>
          <Text style={st.chatCtaText}>Create a mission via Chat</Text>
          <Ionicons name="arrow-forward" size={14} color="#fff"/>
        </TouchableOpacity>

        <View style={{height:32}}/>
      </ScrollView>

      {/* Feedback Modal — action adapts to selected reason */}
      <Modal visible={!!feedback} animationType="slide" transparent>
        <View style={fm.overlay}>
          <View style={fm.sheet}>
            <View style={fm.handle}/>
            <View style={fm.headerRow}>
              <View style={{flex:1}}>
                <Text style={fm.title}>
                  {feedbackReason==="Already done"
                    ? "Mark as completed ✓"
                    : "Why are you skipping this?"}
                </Text>
                <Text style={fm.sub} numberOfLines={2}>{feedback?.title}</Text>
              </View>
              <TouchableOpacity style={fm.closeBtn} onPress={()=>setFeedback(null)}>
                <Ionicons name="close" size={18} color={C.ink2}/>
              </TouchableOpacity>
            </View>
            {/* Reason chips */}
            <Text style={fm.label}>SELECT A REASON</Text>
            <View style={fm.chipRow}>
              {["Not relevant anymore","No time today","Will do later","Already done","Too difficult"].map(r=>(
                <TouchableOpacity key={r}
                  style={[fm.chip, feedbackReason===r&&fm.chipSel,
                    r==="Already done"&&feedbackReason===r&&{backgroundColor:C.greenS,borderColor:C.greenB}
                  ]}
                  onPress={()=>setFeedbackReason(r)}>
                  <Text style={[fm.chipText, feedbackReason===r&&{color:C.acc,fontWeight:"700"},
                    r==="Already done"&&feedbackReason===r&&{color:C.green}
                  ]}>
                    {r==="Already done" ? "✓ Already done" : r}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Context note — label adapts to reason */}
            <Text style={fm.label}>
              {feedbackReason==="Already done"
                ? "ADD A NOTE (OPTIONAL)"
                : "ADDITIONAL NOTE (OPTIONAL)"}
            </Text>
            <TextInput
              style={fm.noteInput}
              value={feedbackNote}
              onChangeText={setFeedbackNote}
              placeholder={
                feedbackReason==="Already done"
                  ? "When did you complete it? Any notes…"
                  : "Any context for the AI..."
              }
              placeholderTextColor={C.ink3}
              multiline maxLength={200}
            />

            {/* Info banner for "Already done" */}
            {feedbackReason==="Already done"&&(
              <View style={fm.doneBanner}>
                <Ionicons name="checkmark-circle-outline" size={14} color={C.green}/>
                <Text style={fm.doneBannerText}>
                  This will mark the mission complete and update your AI memory — not snooze it.
                </Text>
              </View>
            )}

            {/* Actions */}
            <View style={{flexDirection:"row",gap:10}}>
              <TouchableOpacity
                style={[
                  feedbackReason==="Already done" ? fm.doneBtn : fm.snoozeBtn,
                  !feedbackReason&&{opacity:0.4}
                ]}
                disabled={!feedbackReason}
                onPress={submitFeedback}>
                <Ionicons
                  name={feedbackReason==="Already done" ? "checkmark-circle-outline" : "alarm-outline"}
                  size={14} color="#fff"/>
                <Text style={fm.snoozeBtnText}>
                  {feedbackReason==="Already done" ? "Mark Complete + Save" : "Snooze 1 day + Save"}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity style={fm.skipBtn} onPress={()=>setFeedback(null)}>
                <Text style={fm.skipBtnText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
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
  addBtn:      {width:34,height:34,borderRadius:12,backgroundColor:C.acc2,alignItems:"center",justifyContent:"center"},
  content:     {paddingTop:14,paddingBottom:24,gap:13},
  sl:          {fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1.2,marginBottom:8},
  statsRow:    {flexDirection:"row",backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,overflow:"hidden"},
  statBox:     {flex:1,alignItems:"center",paddingVertical:13},
  statNum:     {fontSize:21,fontWeight:"800"},
  statLbl:     {fontSize:10,color:C.ink3,marginTop:3},
  overdueAlert:{flexDirection:"row",alignItems:"center",gap:8,backgroundColor:C.redS,borderRadius:R.lg,borderWidth:0.5,borderColor:C.redB,padding:11},
  overdueAlertText:{flex:1,fontSize:12,color:C.red,fontWeight:"600"},
  filterRow:   {flexDirection:"row",backgroundColor:C.bg2,borderRadius:R.lg,padding:3,gap:3},
  filterTab:   {flex:1,paddingVertical:8,borderRadius:R.md,alignItems:"center"},
  filterTabActive:{backgroundColor:C.bgCard,shadowColor:"#6D28D9",shadowOffset:{width:0,height:1},shadowOpacity:0.08,shadowRadius:3,elevation:2},
  filterText:  {fontSize:12,fontWeight:"600",color:C.ink2},
  filterTextActive:{color:C.acc,fontWeight:"700"},
  emptyWrap:   {alignItems:"center",paddingVertical:28,gap:8},
  emptyEmoji:  {fontSize:38},
  emptyTitle:  {fontSize:15,fontWeight:"700",color:C.ink},
  emptySub:    {fontSize:12,color:C.ink2,textAlign:"center"},
  emptyBtn:    {marginTop:6,paddingHorizontal:22,paddingVertical:10,backgroundColor:C.acc2,borderRadius:R.full},
  emptyBtnText:{fontSize:13,fontWeight:"700",color:"#fff"},
  showMoreBtn: {alignItems:"center",paddingVertical:11,backgroundColor:C.bgCard,borderRadius:R.lg,borderWidth:0.5,borderColor:C.border2,marginBottom:4},
  showMoreText:{fontSize:13,fontWeight:"700",color:C.acc},
  ideasHeader: {flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:8},
  ideasBadge:  {backgroundColor:C.amberS,borderRadius:R.full,paddingHorizontal:9,paddingVertical:3,borderWidth:0.5,borderColor:C.amberB},
  ideasBadgeText:{fontSize:10,fontWeight:"700",color:C.amber},
  captureCard: {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border,overflow:"hidden"},
  captureRow:  {flexDirection:"row",alignItems:"center",gap:8,padding:10,borderBottomWidth:0.5,borderBottomColor:C.bg2},
  captureInput:{flex:1,fontSize:13,color:C.ink,paddingVertical:4},
  captureBtn:  {width:28,height:28,borderRadius:8,backgroundColor:C.acc2,alignItems:"center",justifyContent:"center"},
  voiceRow:    {flexDirection:"row",alignItems:"center",gap:8,padding:10,cursor:"pointer"} as any,
  voiceIcon:   {width:26,height:26,borderRadius:7,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},
  voiceText:   {fontSize:12,color:C.acc,fontWeight:"600"},
  ideasList:   {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,overflow:"hidden"},
  ideaGroupHeader:{flexDirection:"row",alignItems:"center",gap:7,paddingHorizontal:12,paddingVertical:9,backgroundColor:C.bg2,borderBottomWidth:0.5,borderBottomColor:C.border2},
  ideaGroupEmoji: {fontSize:13},
  ideaGroupLabel: {flex:1,fontSize:11,fontWeight:"700",color:C.ink,letterSpacing:0.3},
  ideaGroupCount: {backgroundColor:C.soft,borderRadius:R.full,paddingHorizontal:8,paddingVertical:2,borderWidth:0.5,borderColor:C.border},
  ideaGroupCountText:{fontSize:9,fontWeight:"700",color:C.acc},
  ideaRow:     {flexDirection:"row",alignItems:"center",gap:9,padding:11,borderBottomWidth:0.5,borderBottomColor:C.bg2},
  ideaIcon:    {width:26,height:26,borderRadius:7,backgroundColor:C.soft,alignItems:"center",justifyContent:"center"},
  ideaText:    {flex:1,fontSize:13,color:C.ink2,lineHeight:18},
  convertBtn:  {backgroundColor:C.acc2,borderRadius:R.sm,paddingHorizontal:9,paddingVertical:5},
  convertText: {fontSize:10,fontWeight:"700",color:"#fff"},
  habitCard:   {width:148,borderRadius:R.xl,borderWidth:0.5,padding:13,gap:4},
  habitTitle:  {fontSize:12,fontWeight:"700",color:C.ink},
  habitDesc:   {fontSize:10,color:C.ink3,lineHeight:15},
  habitAddBtn: {flexDirection:"row",alignItems:"center",justifyContent:"center",marginTop:6,paddingVertical:5,paddingHorizontal:8,borderRadius:R.full,borderWidth:0.5,backgroundColor:C.bgCard},
  habitAddText:{fontSize:10,fontWeight:"700",color:C.acc},
  tipsCard:    {backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,overflow:"hidden"},
  tipRow:      {flexDirection:"row",alignItems:"flex-start",gap:11,padding:12,borderBottomWidth:0.5,borderBottomColor:C.bg2},
  tipIcon:     {width:28,height:28,borderRadius:R.sm,alignItems:"center",justifyContent:"center",flexShrink:0},
  tipText:     {flex:1,fontSize:12,color:C.ink2,lineHeight:18},
  chatCta:     {flexDirection:"row",alignItems:"center",justifyContent:"center",gap:9,backgroundColor:C.acc2,borderRadius:R.xl,padding:14},
  chatCtaText: {fontSize:14,fontWeight:"700",color:"#fff"},
});

const fm = StyleSheet.create({
  overlay:    {flex:1,backgroundColor:"rgba(0,0,0,0.45)",justifyContent:"flex-end",...(Platform.OS==="web"?{position:"fixed" as any,top:0,left:0,right:0,bottom:0,zIndex:999}:{})},
  sheet:      {backgroundColor:C.bgCard,borderTopLeftRadius:20,borderTopRightRadius:20,padding:20,paddingBottom:Platform.OS==="ios"?36:24,gap:14},
  handle:     {width:40,height:4,borderRadius:2,backgroundColor:C.border2,alignSelf:"center",marginBottom:6},
  headerRow:  {flexDirection:"row",alignItems:"flex-start",gap:12},
  title:      {fontSize:17,fontWeight:"800",color:C.ink},
  sub:        {fontSize:12,color:C.ink2,marginTop:3,lineHeight:17},
  closeBtn:   {width:32,height:32,borderRadius:16,backgroundColor:C.bg2,alignItems:"center",justifyContent:"center"},
  label:      {fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1.2},
  chipRow:    {flexDirection:"row",flexWrap:"wrap",gap:8},
  chip:       {paddingHorizontal:13,paddingVertical:8,borderRadius:R.full,borderWidth:0.5,borderColor:C.border2,backgroundColor:C.bg2},
  chipSel:    {borderColor:C.acc,backgroundColor:C.soft},
  chipText:   {fontSize:12,color:C.ink2,fontWeight:"600"},
  noteInput:  {borderWidth:0.5,borderColor:C.border2,borderRadius:R.lg,padding:12,fontSize:13,color:C.ink,backgroundColor:C.bg,minHeight:80,textAlignVertical:"top"},
  snoozeBtn:  {flex:2,flexDirection:"row",alignItems:"center",justifyContent:"center",gap:7,backgroundColor:C.acc2,borderRadius:R.lg,paddingVertical:13,shadowColor:"#6D28D9",shadowOffset:{width:0,height:2},shadowOpacity:0.18,shadowRadius:4,elevation:3},
  doneBtn:    {flex:2,flexDirection:"row",alignItems:"center",justifyContent:"center",gap:7,backgroundColor:C.green,borderRadius:R.lg,paddingVertical:13,shadowColor:C.green,shadowOffset:{width:0,height:2},shadowOpacity:0.25,shadowRadius:4,elevation:3},
  snoozeBtnText:{fontSize:13,fontWeight:"700",color:"#fff"},
  skipBtn:    {flex:1,alignItems:"center",justifyContent:"center",backgroundColor:C.bg2,borderRadius:R.lg,paddingVertical:13,borderWidth:0.5,borderColor:C.border2},
  skipBtnText:{fontSize:13,fontWeight:"600",color:C.ink2},
  doneBanner: {flexDirection:"row",alignItems:"flex-start",gap:8,backgroundColor:C.greenS,borderRadius:R.lg,borderWidth:0.5,borderColor:C.greenB,padding:10},
  doneBannerText:{flex:1,fontSize:12,color:"#065F46",lineHeight:17},
});
