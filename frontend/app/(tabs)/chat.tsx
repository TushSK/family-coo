// app/(tabs)/chat.tsx  —  Chat v4 — touchable option cards + direct Custom modal
import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  KeyboardAvoidingView, Platform, ActivityIndicator,
  StyleSheet, SafeAreaView, Animated, Modal,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "expo-router";
import { C, R, S, USER_ID, API_BASE } from "../constants/config";
import { apiPost } from "../hooks/useApi";
import { ChatContextStore } from "../context/ChatContextStore";

interface Message {
  id:string; role:"user"|"assistant"; content:string;
  type?:string; events?:any[]; options?:Option[];
}
interface BrainResponse { type:string; text:string; pre_prep:string; events:any[]; }
interface Option {
  key:string; title:string; time_window:string;
  duration_hours:number; notes:string;
}

// ── Parse OPTIONS_JSON from pre_prep ─────────────────────────────────────────
// Primary path: AI returns OPTIONS_JSON= in the pre_prep field.
function parseOptions(pre_prep: string): Option[] {
  try {
    const m = pre_prep?.match(/OPTIONS_JSON=(\[[\s\S]*?\])/);
    if (m) return JSON.parse(m[1]);
  } catch {}
  return [];
}

// ── Text-based fallback option parser ─────────────────────────────────────────
// Runs when pre_prep has no OPTIONS_JSON. Handles three formats:
//   Tier 1 — (A)/(B)/(C) blocks with When:/Notes: lines  ← most common AI output
//   Tier 2 — numbered list "1. **Title**" or "1) Title"
//   Tier 3 — bold headings "**Title**"
function parseOptionsFromText(text: string): Option[] {
  if (!text) return [];

  // ── Tier 1: split on (A)/(B)/(C)/(D) boundaries ──────────────────────────
  // Using split() instead of regex exec() so the full block content is
  // captured correctly even when (C) is the last option before "Reply exactly".
  const blockSplit = /\(([A-D])\)\s+/;
  const parts = text.split(blockSplit);
  // parts[0] = preamble, then alternating [key, content, key, content ...]
  if (parts.length >= 5) {  // at least 2 options = preamble + 2×(key+content)
    const opts: Option[] = [];
    for (let i = 1; i < parts.length - 1; i += 2) {
      const key     = parts[i].trim();
      const rawBlock = parts[i + 1] || "";
      // Strip trailing "Reply exactly" line and anything after it
      const block   = rawBlock.replace(/\nReply exactly[\s\S]*/i, "").trim();
      const lines   = block.split("\n").map((l: string) => l.trim()).filter(Boolean);
      if (!lines.length) continue;
      const title     = lines[0];
      const timeLine  = lines.find((l: string) => /^when\s*:/i.test(l)) || "";
      const noteLine  = lines.find((l: string) => /^notes?\s*:/i.test(l)) || "";
      opts.push({
        key,
        title,
        time_window:    timeLine ? timeLine.replace(/^when\s*:\s*/i, "").trim() : "",
        duration_hours: 1,
        notes:          noteLine ? noteLine.replace(/^notes?\s*:\s*/i, "").trim() : "",
      });
    }
    if (opts.length >= 2) return opts;
  }

  // ── Tier 2: numbered list "1. **Title**" or "1) Title" ───────────────────
  const numRe = /^(?:\d+[.)]\s+)(?:\*{1,2})?([^\n*]{3,80})(?:\*{1,2})?(?:\s*[-–—]\s*(.+))?$/gm;
  const keysT2 = ["A","B","C","D"];
  const opts2: Option[] = [];
  let m2: RegExpExecArray | null;
  let idx = 0;
  while ((m2 = numRe.exec(text)) !== null && idx < 4) {
    const title = (m2[1] || "").trim();
    if (/^(home|takeout|restaurant|tonight|option|dining)/i.test(title)) continue;
    opts2.push({ key:keysT2[idx]||String(idx+1), title, time_window:"", duration_hours:1, notes:(m2[2]||"").trim() });
    idx++;
  }
  if (opts2.length >= 2) return opts2;

  // ── Tier 3: bold headings "**Title**" ────────────────────────────────────
  const boldRe = /\*\*([^*\n]{5,60})\*\*/g;
  const keysT3 = ["A","B","C","D"];
  const opts3: Option[] = [];
  let m3: RegExpExecArray | null;
  let idx3 = 0;
  while ((m3 = boldRe.exec(text)) !== null && idx3 < 4) {
    const title = (m3[1] || "").trim();
    if (title.length >= 5) { opts3.push({ key:keysT3[idx3]||String(idx3+1), title, time_window:"", duration_hours:1, notes:"" }); idx3++; }
  }
  return opts3.length >= 2 ? opts3 : [];
}

// ── Add event to calendar ─────────────────────────────────────────────────────
async function addEventToCalendar(event: any): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/calendar/add`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({
        user_id:     USER_ID,
        title:       event.title      || event.summary || "New Event",
        start_time:  event.start_time || event.start?.dateTime || event.start?.date,
        end_time:    event.end_time   || event.end?.dateTime   || event.end?.date,
        location:    event.location   || "",
        description: event.description|| "",
      }),
    });
    return res.ok;
  } catch { return false; }
}

const DEFAULT_CHIPS = [
  "Plan this weekend 🎉","What's on today? 📅",
  "Add family outing 🌳","Suggest dinner idea 🍽️","Review my missions ✅",
];

// ── Markdown renderer ─────────────────────────────────────────────────────────
function MdText({ text, style }: { text:string; style?:any }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <Text style={style}>
      {parts.map((p,i) =>
        p.startsWith("**")&&p.endsWith("**")
          ? <Text key={i} style={{fontWeight:"700"}}>{p.slice(2,-2)}</Text>
          : <Text key={i}>{p}</Text>
      )}
    </Text>
  );
}

// ── Draft event card ──────────────────────────────────────────────────────────
function DraftCard({ event, onAdd, onDismiss }:{ event:any; onAdd:()=>void; onDismiss:()=>void }) {
  const [added, setAdded] = useState(false);
  const start = (event.start_time||"").replace("T"," ").slice(0,16);
  const end   = (event.end_time  ||"").replace("T"," ").slice(11,16);
  return (
    <View style={st.draftCard}>
      <View style={st.draftHeader}>
        <Ionicons name="calendar" size={13} color={C.acc}/>
        <Text style={st.draftLabel}>DRAFT EVENT</Text>
        <TouchableOpacity onPress={onDismiss} style={{marginLeft:"auto" as any}}>
          <Ionicons name="close" size={16} color={C.ink3}/>
        </TouchableOpacity>
      </View>
      <Text style={st.draftTitle}>{event.title}</Text>
      {start?<Text style={st.draftMeta}>📅 {start}{end?` – ${end}`:""}</Text>:null}
      {event.location?<Text style={st.draftMeta}>📍 {event.location}</Text>:null}
      <View style={{flexDirection:"row",gap:8}}>
        <TouchableOpacity style={[st.draftBtn, added&&{backgroundColor:C.green}]}
          onPress={()=>{setAdded(true);onAdd();}} disabled={added}>
          <Ionicons name={added?"checkmark-circle":"add-circle-outline"} size={13} color="#fff"/>
          <Text style={st.draftBtnText}>{added?"Added ✓":"Add to Calendar"}</Text>
        </TouchableOpacity>
        {!added&&(
          <TouchableOpacity style={st.draftDismissBtn} onPress={onDismiss}>
            <Text style={st.draftDismissText}>Dismiss</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

// ── Option card (A / B / C / Custom) — fully touchable cards ─────────────────
// Fix #3: The entire card is now a TouchableOpacity.
//   • A / B / C cards  → full-card tap = "Add to Calendar"
//   • Custom card       → full-card tap = immediately opens modal (no chat loop)
function OptionCard({ opt, onSelect, onCustom }:{
  opt:Option; onSelect:(opt:Option)=>void; onCustom?:()=>void;
}) {
  const isCustom = opt.key === "custom";
  const [added, setAdded] = useState(false);

  function handlePress() {
    if (isCustom) {
      onCustom?.();   // directly opens the modal
    } else if (!added) {
      setAdded(true);
      onSelect(opt);
    }
  }

  return (
    <TouchableOpacity
      style={[
        st.optCard,
        isCustom && st.optCardCustom,
        added     && st.optCardAdded,
      ]}
      onPress={handlePress}
      activeOpacity={0.72}
    >
      {/* Card header row */}
      <View style={st.optHeader}>
        <View style={[st.optKey, isCustom && st.optKeyCustom]}>
          <Text style={[st.optKeyText, isCustom && st.optKeyTextCustom]}>
            {opt.key}
          </Text>
        </View>
        <Text style={[st.optTitle, isCustom && st.optTitleCustom]} numberOfLines={2}>
          {opt.title}
        </Text>
        {/* Chevron / tick — right side cue */}
        {added ? (
          <Ionicons name="checkmark-circle" size={18} color={C.green}/>
        ) : isCustom ? (
          <Ionicons name="create-outline"   size={16} color={C.amber}/>
        ) : (
          <Ionicons name="chevron-forward"  size={14} color={C.ink3}/>
        )}
      </View>

      {/* Meta row */}
      {opt.time_window ? (
        <Text style={[st.optMeta, isCustom && {color:C.amber}]}>⏰ {opt.time_window}</Text>
      ) : null}
      {opt.notes ? (
        <Text style={st.optNotes}>{opt.notes}</Text>
      ) : null}

      {/* Bottom action hint */}
      <View style={[st.optFooter, isCustom && st.optFooterCustom, added && st.optFooterAdded]}>
        {added ? (
          <>
            <Ionicons name="checkmark-circle-outline" size={13} color={C.green}/>
            <Text style={[st.optFooterText, {color:C.green}]}>Added to Calendar ✓</Text>
          </>
        ) : isCustom ? (
          <>
            <Ionicons name="create-outline" size={13} color={C.amber}/>
            <Text style={[st.optFooterText, {color:C.amber}]}>Tap to enter your own details →</Text>
          </>
        ) : (
          <>
            <Ionicons name="calendar-outline" size={13} color="#fff"/>
            <Text style={st.optFooterText}>Tap to Add to Calendar</Text>
          </>
        )}
      </View>
    </TouchableOpacity>
  );
}

// ── Typing dots ───────────────────────────────────────────────────────────────
function TypingDots() {
  const dots = [useRef(new Animated.Value(0)).current,
                useRef(new Animated.Value(0)).current,
                useRef(new Animated.Value(0)).current];
  useEffect(()=>{
    dots.forEach((d,i)=>
      Animated.loop(Animated.sequence([
        Animated.delay(i*180),
        Animated.timing(d,{toValue:1,duration:280,useNativeDriver:true}),
        Animated.timing(d,{toValue:0,duration:280,useNativeDriver:true}),
        Animated.delay(500),
      ])).start()
    );
  },[]);
  return (
    <View style={st.bubbleRow}>
      <View style={st.avatar}><Text style={{fontSize:14}}>🏠</Text></View>
      <View style={[st.bubble,st.bubbleAI]}>
        <View style={{flexDirection:"row",gap:5,alignItems:"center"}}>
          {dots.map((d,i)=>(
            <Animated.View key={i} style={{width:6,height:6,borderRadius:3,backgroundColor:C.ink3,opacity:d}}/>
          ))}
        </View>
      </View>
    </View>
  );
}

// ── Bubble ────────────────────────────────────────────────────────────────────
function Bubble({ msg, onDismissEvent, onSelectOption, onCustomOption }:{
  msg:Message;
  onDismissEvent:(id:string,i:number)=>void;
  onSelectOption:(opt:Option)=>void;
  onCustomOption:()=>void;
}) {
  const isUser=msg.role==="user", isErr=msg.type==="error";
  return (
    <View style={[st.bubbleRow, isUser&&st.bubbleRowUser]}>
      {!isUser&&<View style={st.avatar}><Text style={{fontSize:14}}>🏠</Text></View>}
      <View style={{flex:1,alignItems:isUser?"flex-end":"flex-start",gap:6}}>
        <View style={[st.bubble,isUser?st.bubbleUser:st.bubbleAI,isErr&&st.bubbleErr]}>
          <MdText text={msg.content}
            style={[st.bubbleText,isUser&&{color:"#fff"},isErr&&{color:C.red}]}/>
        </View>
        {/* Draft event cards */}
        {!isUser&&msg.events?.map((ev,i)=>(
          <DraftCard key={i} event={ev}
            onAdd={async()=>{ await addEventToCalendar(ev); }}
            onDismiss={()=>onDismissEvent(msg.id,i)}/>
        ))}
        {/* Option A / B / C / Custom — rendered as touchable cards */}
        {!isUser&&msg.options&&msg.options.length>0&&(
          <View style={{gap:7,width:"100%"}}>
            {msg.options.map(opt=>(
              <OptionCard key={opt.key} opt={opt}
                onSelect={onSelectOption}
                onCustom={onCustomOption}/>
            ))}
          </View>
        )}
      </View>
    </View>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function ChatScreen() {
  const [messages, setMessages] = useState<Message[]>([{
    id:"welcome", role:"assistant", type:"chat",
    content:"Hi! I'm your Family COO 👋\n\nI can help you plan outings, manage your calendar, and keep your family on track. What would you like to do today?",
  }]);
  const [input,       setInput]       = useState("");
  const [loading,     setLoading]     = useState(false);
  const [chatHistory, setChatHistory] = useState<any[]>([]);
  const [ideaOptions, setIdeaOptions] = useState<any[]>([]);
  const [showChips,   setShowChips]   = useState(true);
  const [ctxLabel,    setCtxLabel]    = useState<string|null>(null);

  // Custom option modal state
  const [showCustom,  setShowCustom]  = useState(false);
  const [customAct,   setCustomAct]   = useState("");
  const [customTime,  setCustomTime]  = useState("");
  const [customLoc,   setCustomLoc]   = useState("");

  const listRef = useRef<FlatList>(null);
  const scrollToBottom = useCallback(()=>{
    setTimeout(()=>listRef.current?.scrollToEnd({animated:true}),80);
  },[]);

  // ── On focus: consume any pending context and auto-send silently ────────────
  useFocusEffect(
    useCallback(()=>{
      const ctx = ChatContextStore.consume();
      if(ctx){
        setCtxLabel(ctx.label);
        sendSilent(ctx.prompt);
      }
    },[])
  );

  const sendSilent = useCallback(async(prompt: string)=>{
    if(loading) return;
    setShowChips(false);
    setLoading(true);
    scrollToBottom();
    try {
      const res = await apiPost<BrainResponse>("/api/chat",{
        user_id: USER_ID, message: prompt,
        chat_history: chatHistory, idea_options: ideaOptions,
        current_location: "Tampa, FL",
      });
      // Primary: OPTIONS_JSON in pre_prep. Fallback: parse prose (A/B/C, numbered, bold).
      // NOTE: must check .length — [] is truthy in JS, so || would short-circuit wrongly.
      const _primary1 = parseOptions(res.pre_prep || "");
      const options = _primary1.length > 0 ? _primary1 : parseOptionsFromText(res.text || "");
      const customOpt: Option = {
        key:"custom", title:"Something else — enter my own details",
        time_window:"", duration_hours:0, notes:"",
      };
      const asst:Message = {
        id: Date.now().toString(), role:"assistant",
        content: res.text||"Something went wrong.",
        type: res.type, events: res.events,
        options: options.length > 0 ? [...options, customOpt] : undefined,
      };
      setMessages(prev=>[...prev, asst]);
      setChatHistory(prev=>[...prev,{role:"user",content:prompt},{role:"assistant",content:res.text}]);
      if(res.type==="question"&&res.events?.length) setIdeaOptions(res.events);
      scrollToBottom();
    } catch(e:any) {
      setMessages(prev=>[...prev,{
        id:(Date.now()+1).toString(), role:"assistant",
        content:`Connection error: ${e.message}`, type:"error",
      }]);
    } finally { setLoading(false); }
  },[loading, chatHistory, ideaOptions]);

  const send = useCallback(async(text?:string)=>{
    const msg=(text??input).trim();
    if(!msg||loading) return;
    setShowChips(false);
    setCtxLabel(null);
    const userMsg:Message={id:Date.now().toString(),role:"user",content:msg};
    setMessages(prev=>[...prev,userMsg]);
    setChatHistory(prev=>[...prev,{role:"user",content:msg}]);
    setInput(""); setLoading(true); scrollToBottom();
    try {
      const res=await apiPost<BrainResponse>("/api/chat",{
        user_id:USER_ID, message:msg,
        chat_history:chatHistory, idea_options:ideaOptions,
        current_location:"Tampa, FL",
      });
      // Primary: OPTIONS_JSON in pre_prep. Fallback: parse prose (A/B/C, numbered, bold).
      // NOTE: must check .length — [] is truthy in JS, so || would short-circuit wrongly.
      const _primary2 = parseOptions(res.pre_prep||"");
      const options = _primary2.length > 0 ? _primary2 : parseOptionsFromText(res.text||"");
      const customOpt:Option={
        key:"custom", title:"Something else — enter my own details",
        time_window:"", duration_hours:0, notes:"",
      };
      const asst:Message={
        id:(Date.now()+1).toString(), role:"assistant",
        content:res.text||"Something went wrong.",
        type:res.type, events:res.events,
        options:options.length>0?[...options,customOpt]:undefined,
      };
      setMessages(prev=>[...prev,asst]);
      setChatHistory(prev=>[...prev,{role:"assistant",content:res.text}]);
      if(res.type==="question"&&res.events?.length) setIdeaOptions(res.events);
      scrollToBottom();
    } catch(e:any) {
      setMessages(prev=>[...prev,{
        id:(Date.now()+1).toString(), role:"assistant",
        content:`Connection error: ${e.message}`, type:"error",
      }]);
    } finally { setLoading(false); }
  },[input,loading,chatHistory,ideaOptions]);

  const dismissEvent=(msgId:string,evIdx:number)=>{
    setMessages(prev=>prev.map(m=>m.id===msgId
      ? {...m,events:m.events?.filter((_,i)=>i!==evIdx)} : m));
  };

  const handleSelectOption=(opt:Option)=>{
    const now = new Date();
    const event = {
      title:      opt.title,
      start_time: opt.time_window || now.toISOString(),
      end_time:   new Date(now.getTime()+(opt.duration_hours||1)*3600000).toISOString(),
      notes:      opt.notes,
    };
    addEventToCalendar(event);
  };

  // ── Custom modal submit — sends to chat as a normal user message ──────────
  const submitCustom=()=>{
    if(!customAct.trim()) return;
    setShowCustom(false);
    const msg=`Schedule a custom event: ${customAct}${customTime?` on ${customTime}`:""}${customLoc?` at ${customLoc}`:""}. Add it to my calendar.`;
    setCustomAct(""); setCustomTime(""); setCustomLoc("");
    send(msg);
  };

  const clearChat=()=>{
    setMessages([{id:"welcome2",role:"assistant",type:"chat",
      content:"Chat cleared. What would you like to plan?"}]);
    setChatHistory([]); setIdeaOptions([]); setShowChips(true); setCtxLabel(null);
  };

  const canSend = input.trim().length>0 && !loading;
  const chips = DEFAULT_CHIPS;

  return (
    <SafeAreaView style={st.safe}>
      {/* Header */}
      <View style={st.header}>
        <View style={st.headerLeft}>
          <View style={st.onlineDot}/>
          <View>
            <Text style={st.headerTitle}>Family COO</Text>
            <Text style={st.headerSub}>
              {ctxLabel ? `✦ ${ctxLabel}` : "AI Executive Assistant · Online"}
            </Text>
          </View>
        </View>
        <TouchableOpacity onPress={clearChat} style={st.clearBtn}>
          <Ionicons name="refresh-outline" size={16} color={C.ink2}/>
        </TouchableOpacity>
      </View>

      <KeyboardAvoidingView style={{flex:1}}
        behavior={Platform.OS==="ios"?"padding":"height"}
        keyboardVerticalOffset={Platform.OS==="ios"?0:24}>

        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={m=>m.id}
          contentContainerStyle={st.listContent}
          renderItem={({item})=>(
            <Bubble msg={item}
              onDismissEvent={dismissEvent}
              onSelectOption={handleSelectOption}
              onCustomOption={()=>{
                // Fix #3: directly open modal — no chat-loop round trip
                setShowCustom(true);
              }}/>
          )}
          onContentSizeChange={scrollToBottom}
          showsVerticalScrollIndicator={false}
          ListFooterComponent={loading?<TypingDots/>:null}
          ListHeaderComponent={showChips?(
            <View style={st.chipsWrap}>
              <Text style={st.chipsLabel}>SUGGESTED</Text>
              <View style={st.chipsRow}>
                {chips.map(c=>(
                  <TouchableOpacity key={c} style={st.chip} onPress={()=>send(c)}>
                    <Text style={st.chipText}>{c}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ):null}
        />

        {/* Input bar */}
        <View style={st.inputBar}>
          <TextInput
            style={st.input}
            value={input}
            onChangeText={setInput}
            placeholder="Plan something, ask anything…"
            placeholderTextColor={C.ink3}
            multiline maxLength={500}
            onSubmitEditing={()=>send()}
            returnKeyType="send" blurOnSubmit={false}
          />
          <TouchableOpacity
            onPress={()=>send()} disabled={!canSend}
            style={[st.sendBtn, !canSend&&{backgroundColor:C.border}]}>
            {loading
              ? <ActivityIndicator size="small" color="#fff"/>
              : <Ionicons name="send" size={15} color="#fff"/>
            }
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>

      {/* ── Custom Event Modal — pops directly, no chat loop ──────────────── */}
      <Modal visible={showCustom} animationType="slide" transparent>
        <View style={st.modalOverlay}>
          <View style={st.modalSheet}>
            <View style={st.sheetHandle}/>

            {/* Header */}
            <View style={st.modalHeaderRow}>
              <View style={st.modalIconWrap}>
                <Ionicons name="create-outline" size={18} color={C.amber}/>
              </View>
              <View style={{flex:1}}>
                <Text style={st.modalTitle}>Custom Event</Text>
                <Text style={st.modalSub}>Fill in your details — no back-and-forth needed</Text>
              </View>
              <TouchableOpacity onPress={()=>setShowCustom(false)} style={st.modalClose}>
                <Ionicons name="close" size={18} color={C.ink3}/>
              </TouchableOpacity>
            </View>

            {/* Fields */}
            <Text style={st.fieldLabel}>ACTIVITY *</Text>
            <TextInput
              style={[st.fieldInput, !customAct.trim() && st.fieldInputEmpty]}
              value={customAct}
              onChangeText={setCustomAct}
              placeholder="e.g. Judo class for Drishti"
              placeholderTextColor={C.ink3}
              autoFocus
            />

            <Text style={[st.fieldLabel,{marginTop:12}]}>DATE & TIME</Text>
            <TextInput
              style={st.fieldInput}
              value={customTime}
              onChangeText={setCustomTime}
              placeholder="e.g. Tomorrow at 5:30 PM"
              placeholderTextColor={C.ink3}
            />

            <Text style={[st.fieldLabel,{marginTop:12}]}>LOCATION (OPTIONAL)</Text>
            <TextInput
              style={st.fieldInput}
              value={customLoc}
              onChangeText={setCustomLoc}
              placeholder="e.g. Tampa Judo Academy"
              placeholderTextColor={C.ink3}
            />

            {/* Preview chip — shows what will be sent */}
            {customAct.trim().length > 0 && (
              <View style={st.previewBox}>
                <Text style={st.previewLabel}>WILL SCHEDULE:</Text>
                <Text style={st.previewText}>
                  📌 {customAct.trim()}
                  {customTime ? `  ·  ⏰ ${customTime}` : ""}
                  {customLoc  ? `  ·  📍 ${customLoc}`  : ""}
                </Text>
              </View>
            )}

            {/* Actions */}
            <View style={{flexDirection:"row",gap:10,marginTop:12}}>
              <TouchableOpacity
                style={[st.scheduleBtn, !customAct.trim() && st.scheduleBtnDisabled]}
                onPress={submitCustom}
                disabled={!customAct.trim()}>
                <Ionicons name="calendar-outline" size={16} color="#fff"/>
                <Text style={st.scheduleBtnText}>Schedule it →</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={st.cancelBtn}
                onPress={()=>setShowCustom(false)}>
                <Text style={st.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe:    {flex:1,backgroundColor:C.bg},
  header:  {
    flexDirection:"row",alignItems:"center",justifyContent:"space-between",
    paddingHorizontal:18,paddingVertical:13,
    backgroundColor:C.bgCard,borderBottomWidth:0.5,borderBottomColor:C.border2,
    shadowColor:"#6D28D9",shadowOffset:{width:0,height:1},shadowOpacity:0.06,shadowRadius:4,elevation:2,
  },
  headerLeft:  {flexDirection:"row",alignItems:"center",gap:10},
  headerTitle: {fontSize:15,fontWeight:"800",color:C.ink},
  headerSub:   {fontSize:10,color:C.ink3,marginTop:1},
  onlineDot:   {width:9,height:9,borderRadius:5,backgroundColor:C.green,
                shadowColor:C.green,shadowOffset:{width:0,height:0},shadowOpacity:0.5,shadowRadius:4},
  clearBtn:    {padding:8,borderRadius:R.sm,backgroundColor:C.bg2},
  listContent: {paddingHorizontal:14,paddingTop:12,paddingBottom:8},
  chipsWrap:   {paddingBottom:14,gap:7},
  chipsLabel:  {fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1,paddingLeft:2},
  chipsRow:    {flexDirection:"row",flexWrap:"wrap",gap:7},
  chip:        {paddingHorizontal:13,paddingVertical:7,backgroundColor:C.bgCard,borderRadius:R.full,borderWidth:0.5,borderColor:C.border},
  chipText:    {fontSize:12,color:C.acc,fontWeight:"600"},
  bubbleRow:   {flexDirection:"row",alignItems:"flex-end",marginBottom:13,gap:8},
  bubbleRowUser:{flexDirection:"row-reverse"},
  avatar:      {width:30,height:30,borderRadius:15,backgroundColor:C.soft,borderWidth:0.5,borderColor:C.border,alignItems:"center",justifyContent:"center"},
  bubble:      {maxWidth:"80%",paddingHorizontal:13,paddingVertical:10,borderRadius:R.xl},
  bubbleUser:  {backgroundColor:C.acc2},
  bubbleAI:    {backgroundColor:C.bgCard,borderWidth:0.5,borderColor:C.border2,
                shadowColor:"#6D28D9",shadowOffset:{width:0,height:1},shadowOpacity:0.05,shadowRadius:3,elevation:1},
  bubbleErr:   {backgroundColor:C.redS,borderColor:C.redB,borderWidth:0.5},
  bubbleText:  {fontSize:14,color:C.ink,lineHeight:21},
  // Draft card
  draftCard:   {maxWidth:"88%",backgroundColor:C.bgCard,borderRadius:R.lg,borderWidth:0.5,borderColor:C.border,padding:12,gap:5,
                shadowColor:"#6D28D9",shadowOffset:{width:0,height:2},shadowOpacity:0.07,shadowRadius:5,elevation:2},
  draftHeader: {flexDirection:"row",alignItems:"center",gap:6},
  draftLabel:  {fontSize:10,fontWeight:"700",color:C.acc,letterSpacing:1},
  draftTitle:  {fontSize:13,fontWeight:"700",color:C.ink},
  draftMeta:   {fontSize:12,color:C.ink2},
  draftBtn:    {flex:1,flexDirection:"row",alignItems:"center",justifyContent:"center",gap:5,
                backgroundColor:C.acc2,borderRadius:R.sm,paddingVertical:8,marginTop:4},
  draftBtnText:{fontSize:12,fontWeight:"700",color:"#fff"},
  draftDismissBtn:{paddingHorizontal:13,paddingVertical:8,borderRadius:R.sm,
                   backgroundColor:C.bg2,borderWidth:0.5,borderColor:C.border2,marginTop:4},
  draftDismissText:{fontSize:12,fontWeight:"600",color:C.ink3},

  // ── Option cards — fully touchable ──────────────────────────────────────────
  optCard:     {
    backgroundColor:C.bgCard,borderRadius:R.xl,borderWidth:0.5,borderColor:C.border2,
    padding:14,gap:6,overflow:"hidden",
    shadowColor:"#6D28D9",shadowOffset:{width:0,height:2},shadowOpacity:0.07,shadowRadius:5,elevation:2,
  },
  optCardCustom:{
    backgroundColor:C.amberS,borderColor:C.amberB,
  },
  optCardAdded:{
    opacity:0.65,
  },
  optHeader:   {flexDirection:"row",alignItems:"center",gap:9},
  optKey:      {width:30,height:30,borderRadius:8,backgroundColor:C.soft,borderWidth:0.5,borderColor:C.border,alignItems:"center",justifyContent:"center",flexShrink:0},
  optKeyCustom:{backgroundColor:"#FEF3C7",borderColor:C.amberB},
  optKeyText:  {fontSize:13,fontWeight:"800",color:C.acc},
  optKeyTextCustom:{color:C.amber},
  optTitle:    {flex:1,fontSize:13,fontWeight:"700",color:C.ink,lineHeight:18},
  optTitleCustom:{color:"#78350F"},
  optMeta:     {fontSize:11,color:C.ink3},
  optNotes:    {fontSize:12,color:C.ink2,lineHeight:17},
  // Footer strip at bottom of each card
  optFooter:   {
    flexDirection:"row",alignItems:"center",gap:6,
    backgroundColor:C.acc2,borderRadius:R.lg,
    paddingVertical:9,paddingHorizontal:12,marginTop:4,
  },
  optFooterCustom:{backgroundColor:"transparent",borderWidth:0.5,borderColor:C.amberB},
  optFooterAdded: {backgroundColor:C.greenS,borderWidth:0.5,borderColor:C.greenB},
  optFooterText:  {fontSize:12,fontWeight:"700",color:"#fff"},

  // Input
  inputBar:  {flexDirection:"row",alignItems:"flex-end",gap:9,paddingHorizontal:12,paddingVertical:10,
              borderTopWidth:0.5,borderTopColor:C.border2,backgroundColor:C.bgCard,
              shadowColor:"#6D28D9",shadowOffset:{width:0,height:-2},shadowOpacity:0.05,shadowRadius:4,elevation:2},
  input:    {flex:1,backgroundColor:C.bg2,borderRadius:R.full,borderWidth:0.5,borderColor:C.border2,
             paddingHorizontal:15,paddingVertical:10,fontSize:14,color:C.ink,maxHeight:120},
  sendBtn:  {width:42,height:42,borderRadius:21,backgroundColor:C.acc2,alignItems:"center",justifyContent:"center",
             shadowColor:"#6D28D9",shadowOffset:{width:0,height:2},shadowOpacity:0.2,shadowRadius:4,elevation:3},

  // Custom modal
  modalOverlay:{flex:1,backgroundColor:"rgba(0,0,0,0.5)",justifyContent:"flex-end",
               ...(Platform.OS==="web"?{position:"fixed" as any,top:0,left:0,right:0,bottom:0,zIndex:999}:{})},
  modalSheet:  {backgroundColor:C.bgCard,borderTopLeftRadius:24,borderTopRightRadius:24,
                padding:20,paddingBottom:Platform.OS==="ios"?40:28,gap:10},
  sheetHandle: {width:44,height:4,borderRadius:2,backgroundColor:C.border2,alignSelf:"center",marginBottom:6},
  modalHeaderRow:{flexDirection:"row",alignItems:"center",gap:11,marginBottom:4},
  modalIconWrap: {width:38,height:38,borderRadius:10,backgroundColor:C.amberS,borderWidth:0.5,borderColor:C.amberB,alignItems:"center",justifyContent:"center"},
  modalTitle:  {fontSize:17,fontWeight:"800",color:C.ink},
  modalSub:    {fontSize:11,color:C.ink2,marginTop:1},
  modalClose:  {width:32,height:32,borderRadius:R.sm,backgroundColor:C.bg2,alignItems:"center",justifyContent:"center"},
  fieldLabel:  {fontSize:10,fontWeight:"700",color:C.ink3,letterSpacing:1.2,marginBottom:6},
  fieldInput:  {borderWidth:0.5,borderColor:C.border2,borderRadius:R.lg,
                paddingHorizontal:13,paddingVertical:11,fontSize:14,color:C.ink,backgroundColor:C.bg},
  fieldInputEmpty:{borderColor:C.border2},
  // Preview box
  previewBox:  {backgroundColor:C.soft,borderRadius:R.lg,borderWidth:0.5,borderColor:C.border,
                padding:11,marginTop:4},
  previewLabel:{fontSize:9,fontWeight:"700",color:C.acc,letterSpacing:1,marginBottom:3},
  previewText: {fontSize:12,color:C.ink,lineHeight:18},
  // Buttons
  scheduleBtn: {flex:2,flexDirection:"row",alignItems:"center",justifyContent:"center",gap:8,
                backgroundColor:C.acc2,borderRadius:R.lg,paddingVertical:13,
                shadowColor:"#6D28D9",shadowOffset:{width:0,height:2},shadowOpacity:0.2,shadowRadius:5,elevation:3},
  scheduleBtnDisabled:{backgroundColor:C.border,shadowOpacity:0},
  scheduleBtnText:{fontSize:14,fontWeight:"800",color:"#fff"},
  cancelBtn:   {flex:1,alignItems:"center",justifyContent:"center",borderRadius:R.lg,
                backgroundColor:C.bg2,borderWidth:0.5,borderColor:C.border2},
  cancelBtnText:{fontSize:13,fontWeight:"600",color:C.ink2},
});
