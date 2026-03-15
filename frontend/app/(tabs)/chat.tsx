// app/(tabs)/chat.tsx  —  Chat (v3 Lavender)
import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  KeyboardAvoidingView, Platform, ActivityIndicator,
  StyleSheet, SafeAreaView, Animated,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { C, R, S, USER_ID } from "../constants/config";
import { apiPost } from "../hooks/useApi";

interface Message {
  id:string; role:"user"|"assistant"; content:string; type?:string; events?:any[];
}
interface BrainResponse { type:string; text:string; pre_prep:string; events:any[]; }

const CHIPS = [
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

// ── Draft card ────────────────────────────────────────────────────────────────
function DraftCard({ event, onAdd, onDismiss }:{ event:any; onAdd:()=>void; onDismiss:()=>void }) {
  const [added, setAdded] = useState(false);
  const start = (event.start_time||"").replace("T"," ").slice(0,16);
  const end   = (event.end_time  ||"").replace("T"," ").slice(11,16);
  return (
    <View style={st.draftCard}>
      <View style={st.draftHeader}>
        <Ionicons name="calendar" size={13} color={C.acc}/>
        <Text style={st.draftLabel}>DRAFT EVENT</Text>
        <TouchableOpacity onPress={onDismiss} style={{marginLeft:"auto"}}>
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
function Bubble({ msg, onDismissEvent }:{
  msg:Message; onDismissEvent:(id:string,i:number)=>void;
}) {
  const isUser=msg.role==="user", isErr=msg.type==="error";
  return (
    <View style={[st.bubbleRow, isUser&&st.bubbleRowUser]}>
      {!isUser&&<View style={st.avatar}><Text style={{fontSize:14}}>🏠</Text></View>}
      <View style={{flex:1,alignItems:isUser?"flex-end":"flex-start",gap:6}}>
        <View style={[st.bubble,
          isUser?st.bubbleUser:st.bubbleAI,
          isErr&&st.bubbleErr,
        ]}>
          <MdText text={msg.content}
            style={[st.bubbleText,isUser&&{color:"#fff"},isErr&&{color:C.red}]}/>
        </View>
        {!isUser&&msg.events?.map((ev,i)=>(
          <DraftCard key={i} event={ev}
            onAdd={()=>{}}
            onDismiss={()=>onDismissEvent(msg.id,i)}/>
        ))}
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
  const listRef = useRef<FlatList>(null);

  const scrollToBottom = useCallback(()=>{
    setTimeout(()=>listRef.current?.scrollToEnd({animated:true}),80);
  },[]);

  const send = useCallback(async(text?:string)=>{
    const msg=(text??input).trim();
    if(!msg||loading) return;
    setShowChips(false);
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
      const asst:Message={
        id:(Date.now()+1).toString(), role:"assistant",
        content:res.text||"Something went wrong.",
        type:res.type, events:res.events,
      };
      setMessages(prev=>[...prev,asst]);
      setChatHistory(prev=>[...prev,{role:"assistant",content:res.text}]);
      if(res.type==="question"&&res.events?.length) setIdeaOptions(res.events);
      else if(res.type==="plan") setIdeaOptions([]);
      scrollToBottom();
    } catch(e:any) {
      setMessages(prev=>[...prev,{
        id:(Date.now()+1).toString(), role:"assistant",
        content:`Connection error: ${e.message}`,
        type:"error",
      }]);
    } finally { setLoading(false); }
  },[input,loading,chatHistory,ideaOptions]);

  const dismissEvent=(msgId:string,evIdx:number)=>{
    setMessages(prev=>prev.map(m=>m.id===msgId
      ? {...m,events:m.events?.filter((_,i)=>i!==evIdx)} : m));
  };

  const clearChat=()=>{
    setMessages([{id:"welcome2",role:"assistant",type:"chat",
      content:"Chat cleared. What would you like to plan?"}]);
    setChatHistory([]); setIdeaOptions([]); setShowChips(true);
  };

  const canSend = input.trim().length>0 && !loading;

  return (
    <SafeAreaView style={st.safe}>
      {/* Header */}
      <View style={st.header}>
        <View style={st.headerLeft}>
          <View style={st.onlineDot}/>
          <View>
            <Text style={st.headerTitle}>Family COO</Text>
            <Text style={st.headerSub}>AI Executive Assistant · Online</Text>
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
          renderItem={({item})=><Bubble msg={item} onDismissEvent={dismissEvent}/>}
          onContentSizeChange={scrollToBottom}
          showsVerticalScrollIndicator={false}
          ListFooterComponent={loading?<TypingDots/>:null}
          ListHeaderComponent={showChips?(
            <View style={st.chipsWrap}>
              <Text style={st.chipsLabel}>SUGGESTED</Text>
              <View style={st.chipsRow}>
                {CHIPS.map(c=>(
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
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe:    {flex:1,backgroundColor:C.bg},
  header:  {
    flexDirection:"row",alignItems:"center",justifyContent:"space-between",
    paddingHorizontal:18,paddingVertical:13,
    backgroundColor:C.bgCard,
    borderBottomWidth:0.5,borderBottomColor:C.border2,
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
  draftCard:   {
    maxWidth:"88%",backgroundColor:C.bgCard,
    borderRadius:R.lg,borderWidth:0.5,borderColor:C.border,
    padding:12,gap:5,
    shadowColor:"#6D28D9",shadowOffset:{width:0,height:2},shadowOpacity:0.07,shadowRadius:5,elevation:2,
  },
  draftHeader:     {flexDirection:"row",alignItems:"center",gap:6},
  draftLabel:      {fontSize:10,fontWeight:"700",color:C.acc,letterSpacing:1},
  draftTitle:      {fontSize:13,fontWeight:"700",color:C.ink},
  draftMeta:       {fontSize:12,color:C.ink2},
  draftBtn:        {flex:1,flexDirection:"row",alignItems:"center",justifyContent:"center",gap:5,
                    backgroundColor:C.acc2,borderRadius:R.sm,paddingVertical:8,marginTop:4},
  draftBtnText:    {fontSize:12,fontWeight:"700",color:"#fff"},
  draftDismissBtn: {paddingHorizontal:13,paddingVertical:8,borderRadius:R.sm,
                    backgroundColor:C.bg2,borderWidth:0.5,borderColor:C.border2,marginTop:4},
  draftDismissText:{fontSize:12,fontWeight:"600",color:C.ink3},
  inputBar:  {
    flexDirection:"row",alignItems:"flex-end",gap:9,
    paddingHorizontal:12,paddingVertical:10,
    borderTopWidth:0.5,borderTopColor:C.border2,
    backgroundColor:C.bgCard,
    shadowColor:"#6D28D9",shadowOffset:{width:0,height:-2},shadowOpacity:0.05,shadowRadius:4,elevation:2,
  },
  input:    {
    flex:1,backgroundColor:C.bg2,
    borderRadius:R.full,borderWidth:0.5,borderColor:C.border2,
    paddingHorizontal:15,paddingVertical:10,
    fontSize:14,color:C.ink,maxHeight:120,
  },
  sendBtn:  {
    width:42,height:42,borderRadius:21,
    backgroundColor:C.acc2,
    alignItems:"center",justifyContent:"center",
    shadowColor:"#6D28D9",shadowOffset:{width:0,height:2},shadowOpacity:0.2,shadowRadius:4,elevation:3,
  },
});
