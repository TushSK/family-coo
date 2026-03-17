// app/(tabs)/missions.tsx  —  Missions (v3 Lavender)
import React, { useEffect, useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, ActivityIndicator,
  StyleSheet, SafeAreaView, RefreshControl, Platform, Dimensions, TextInput,
  Modal,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { C, R, S, USER_ID } from "../constants/config";
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
  const [localIdeas, setLocalIdeas] = useState<string[]>([]);

  const res = useGet<{missions:Mission[]}>(`/api/missions?user_id=${USER_ID}&status=${filter}`);
  useEffect(()=>{ res.refetch(); },[filter]);
  const onRefresh=async()=>{ setRefreshing(true); res.refetch(); setRefreshing(false); };

  const missions=res.data?.missions||[];
  const overdue =missions.filter(m=>m.status==="pending"&&isPast(m.end_time));
  const onTime  =missions.filter(m=>m.status==="pending"&&!isPast(m.end_time));
  const reviewed=missions.filter(m=>m.status==="reviewed");

  const handleComplete=async(id:string)=>{
    try { await apiPost(`/api/missions/${id}/complete`,{}); res.refetch(); } catch {}
  };
  const handleSnooze=(id:string)=>{
    const mission = missions.find(m=>m.id===id);
    setFeedbackNote("");
    setFeedbackReason("");
    setFeedback({missionId:id, title:mission?.title||"this mission"});
  };

  const submitFeedback=async()=>{
    if(!feedback) return;
    const until=new Date(Date.now()+86400000).toISOString();
    try {
      await apiPost(`/api/missions/${feedback.missionId}/snooze`,{
        snoozed_until:until,
        feedback_note:feedbackNote,
        reason:feedbackReason,
      });
      // Also log feedback
      await apiPost("/api/feedback",{
        user_id: USER_ID,
        mission_id: feedback.missionId,
        feedback_type:"skipped",
        reason: feedbackReason,
        note: feedbackNote,
      });
      res.refetch();
    } catch {}
    setFeedback(null);
  };

  function addIdea(){
    if(!ideaDraft.trim()) return;
    setLocalIdeas(prev=>[ideaDraft.trim(),...prev]);
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
          {localIdeas.length>0&&(
            <View style={st.ideasBadge}>
              <Text style={st.ideasBadgeText}>{localIdeas.length} saved</Text>
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
              onSubmitEditing={addIdea}
              returnKeyType="done"
            />
            <TouchableOpacity
              style={[st.captureBtn,!ideaDraft.trim()&&{opacity:0.4}]}
              onPress={addIdea} disabled={!ideaDraft.trim()}>
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

        {/* Ideas list */}
        {localIdeas.length>0&&(
          <View style={[st.ideasList,S.xs]}>
            {localIdeas.map((idea,i)=>(
              <View key={i} style={[st.ideaRow,i===localIdeas.length-1&&{borderBottomWidth:0}]}>
                <View style={st.ideaIcon}><Ionicons name="bulb-outline" size={13} color={C.acc}/></View>
                <Text style={st.ideaText}>{idea}</Text>
                <TouchableOpacity style={st.convertBtn}
                  onPress={()=>setLocalIdeas(prev=>prev.filter((_,j)=>j!==i))}>
                  <Text style={st.convertText}>→ Mission</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={()=>setLocalIdeas(prev=>prev.filter((_,j)=>j!==i))}>
                  <Ionicons name="close" size={14} color={C.ink3}/>
                </TouchableOpacity>
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
        <TouchableOpacity style={[st.chatCta,S.md]} onPress={()=>router.push("/(tabs)/chat")}>
          <Ionicons name="chatbubble-outline" size={17} color="#fff"/>
          <Text style={st.chatCtaText}>Create a mission via Chat</Text>
          <Ionicons name="arrow-forward" size={14} color="#fff"/>
        </TouchableOpacity>

        <View style={{height:32}}/>
      </ScrollView>

      {/* Feedback Modal — shown when snooze/skip is tapped */}
      <Modal visible={!!feedback} animationType="slide" transparent>
        <View style={fm.overlay}>
          <View style={fm.sheet}>
            <View style={fm.handle}/>
            <View style={fm.headerRow}>
              <View style={{flex:1}}>
                <Text style={fm.title}>Why are you skipping this?</Text>
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
                  style={[fm.chip, feedbackReason===r&&fm.chipSel]}
                  onPress={()=>setFeedbackReason(r)}>
                  <Text style={[fm.chipText, feedbackReason===r&&{color:C.acc,fontWeight:"700"}]}>{r}</Text>
                </TouchableOpacity>
              ))}
            </View>
            {/* Optional note */}
            <Text style={fm.label}>ADDITIONAL NOTE (OPTIONAL)</Text>
            <TextInput
              style={fm.noteInput}
              value={feedbackNote}
              onChangeText={setFeedbackNote}
              placeholder="Any context for the AI..."
              placeholderTextColor={C.ink3}
              multiline maxLength={200}
            />
            {/* Actions */}
            <View style={{flexDirection:"row",gap:10}}>
              <TouchableOpacity style={[fm.snoozeBtn, !feedbackReason&&{opacity:0.4}]}
                disabled={!feedbackReason}
                onPress={submitFeedback}>
                <Ionicons name="alarm-outline" size={14} color="#fff"/>
                <Text style={fm.snoozeBtnText}>Snooze 1 day + Save</Text>
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
  snoozeBtnText:{fontSize:13,fontWeight:"700",color:"#fff"},
  skipBtn:    {flex:1,alignItems:"center",justifyContent:"center",backgroundColor:C.bg2,borderRadius:R.lg,paddingVertical:13,borderWidth:0.5,borderColor:C.border2},
  skipBtnText:{fontSize:13,fontWeight:"600",color:C.ink2},
});
