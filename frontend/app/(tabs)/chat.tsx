// app/(tabs)/chat.tsx  — Family COO Chat (Hero Screen)
import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  KeyboardAvoidingView, Platform, ActivityIndicator,
  StyleSheet, SafeAreaView, Animated, Dimensions,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { C, R, USER_ID } from "../constants/config";
import { apiPost } from "../hooks/useApi";

// ── Types ─────────────────────────────────────────────────────────────────────
interface Message {
  id:      string;
  role:    "user" | "assistant";
  content: string;
  type?:   string;
  events?: any[];
}

interface BrainResponse {
  type:     string;
  text:     string;
  pre_prep: string;
  events:   any[];
}

// ── Suggestion chips shown on first load ──────────────────────────────────────
const CHIPS = [
  "Plan this weekend",
  "What's on today?",
  "Add family outing",
  "Suggest a dinner idea",
  "Review my missions",
];

// ── Draft event card ──────────────────────────────────────────────────────────
function DraftCard({ event, onAdd }: { event: any; onAdd: () => void }) {
  const [added, setAdded] = useState(false);
  const start = (event.start_time || "").replace("T", " ").slice(0, 16);
  const end   = (event.end_time   || "").replace("T", " ").slice(11, 16);
  return (
    <View style={st.draftCard}>
      <View style={st.draftHeader}>
        <Ionicons name="calendar" size={13} color={C.indigo} />
        <Text style={st.draftLabel}>DRAFT EVENT</Text>
      </View>
      <Text style={st.draftTitle}>{event.title}</Text>
      {start ? <Text style={st.draftMeta}>📅 {start}{end ? ` – ${end}` : ""}</Text> : null}
      {event.location ? <Text style={st.draftMeta}>📍 {event.location}</Text> : null}
      <TouchableOpacity
        style={[st.draftBtn, added && st.draftBtnDone]}
        onPress={() => { setAdded(true); onAdd(); }}
        disabled={added}
      >
        <Ionicons name={added ? "checkmark-circle" : "add-circle-outline"} size={14} color="#fff" />
        <Text style={st.draftBtnText}>{added ? "Added to Calendar" : "Add to Calendar"}</Text>
      </TouchableOpacity>
    </View>
  );
}

// ── Typing dots ───────────────────────────────────────────────────────────────
function TypingDots() {
  const dots = [useRef(new Animated.Value(0)).current,
                useRef(new Animated.Value(0)).current,
                useRef(new Animated.Value(0)).current];
  useEffect(() => {
    dots.forEach((d, i) =>
      Animated.loop(Animated.sequence([
        Animated.delay(i * 180),
        Animated.timing(d, { toValue:1, duration:280, useNativeDriver:true }),
        Animated.timing(d, { toValue:0, duration:280, useNativeDriver:true }),
        Animated.delay(500),
      ])).start()
    );
  }, []);
  return (
    <View style={st.bubbleRow}>
      <View style={st.avatar}><Text style={{ fontSize:15 }}>🏠</Text></View>
      <View style={[st.bubble, st.bubbleAI]}>
        <View style={{ flexDirection:"row", gap:5, alignItems:"center" }}>
          {dots.map((d, i) => (
            <Animated.View key={i} style={{ width:7, height:7, borderRadius:4,
              backgroundColor:C.inkMuted, opacity:d }} />
          ))}
        </View>
      </View>
    </View>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────
function Bubble({ msg, onAddEvent }: { msg: Message; onAddEvent: (ev:any) => void }) {
  const isUser = msg.role === "user";
  const isErr  = msg.type  === "error";

  return (
    <View style={[st.bubbleRow, isUser && st.bubbleRowUser]}>
      {!isUser && <View style={st.avatar}><Text style={{ fontSize:15 }}>🏠</Text></View>}

      <View style={{ flex:1, alignItems: isUser ? "flex-end" : "flex-start", gap:6 }}>
        <View style={[
          st.bubble,
          isUser ? st.bubbleUser : st.bubbleAI,
          isErr  && st.bubbleErr,
        ]}>
          <Text style={[st.bubbleText, isUser && { color:"#fff" }, isErr && { color:C.red }]}>
            {msg.content}
          </Text>
        </View>

        {!isUser && msg.events?.map((ev, i) => (
          <DraftCard key={i} event={ev} onAdd={() => onAddEvent(ev)} />
        ))}
      </View>
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────
export default function ChatScreen() {
  const [messages, setMessages] = useState<Message[]>([{
    id: "welcome", role: "assistant", type: "chat",
    content: "Hi! I'm your Family COO 👋\n\nI can help you plan outings, manage your calendar, and keep your family on track. What would you like to do today?",
  }]);
  const [input,       setInput]       = useState("");
  const [loading,     setLoading]     = useState(false);
  const [chatHistory, setChatHistory] = useState<any[]>([]);
  const [ideaOptions, setIdeaOptions] = useState<any[]>([]);
  const [showChips,   setShowChips]   = useState(true);
  const listRef = useRef<FlatList>(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => listRef.current?.scrollToEnd({ animated:true }), 80);
  }, []);

  const send = useCallback(async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;

    setShowChips(false);
    const userMsg: Message = { id: Date.now().toString(), role:"user", content:msg };
    setMessages(prev => [...prev, userMsg]);
    setChatHistory(prev => [...prev, { role:"user", content:msg }]);
    setInput("");
    setLoading(true);
    scrollToBottom();

    try {
      const res = await apiPost<BrainResponse>("/api/chat", {
        user_id:          USER_ID,
        message:          msg,
        chat_history:     chatHistory,
        idea_options:     ideaOptions,
        current_location: "Tampa, FL",
      });

      const asst: Message = {
        id:      (Date.now()+1).toString(),
        role:    "assistant",
        content: res.text || "Something went wrong.",
        type:    res.type,
        events:  res.events,
      };
      setMessages(prev => [...prev, asst]);
      setChatHistory(prev => [...prev, { role:"assistant", content:res.text }]);
      if (res.type === "question" && res.events?.length) setIdeaOptions(res.events);
      else if (res.type === "plan") setIdeaOptions([]);
      scrollToBottom();
    } catch (e: any) {
      setMessages(prev => [...prev, {
        id:      (Date.now()+1).toString(),
        role:    "assistant",
        content: `Connection error: ${e.message}. Make sure the backend is running on port 8000.`,
        type:    "error",
      }]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, chatHistory, ideaOptions]);

  const clearChat = () => {
    setMessages([{ id:"welcome2", role:"assistant", type:"chat",
      content:"Chat cleared. What would you like to plan?" }]);
    setChatHistory([]); setIdeaOptions([]); setShowChips(true);
  };

  return (
    <SafeAreaView style={st.safe}>
      {/* Header */}
      <View style={st.header}>
        <View style={st.headerLeft}>
          <View style={st.onlineDot} />
          <View>
            <Text style={st.headerTitle}>Family COO</Text>
            <Text style={st.headerSub}>AI Executive Assistant  ·  Online</Text>
          </View>
        </View>
        <TouchableOpacity onPress={clearChat} style={st.clearBtn}>
          <Ionicons name="refresh-outline" size={16} color={C.inkSub} />
        </TouchableOpacity>
      </View>

      <KeyboardAvoidingView style={{ flex:1 }}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 24}>

        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={m => m.id}
          contentContainerStyle={st.listContent}
          renderItem={({ item }) => (
            <Bubble msg={item} onAddEvent={() => {}} />
          )}
          onContentSizeChange={scrollToBottom}
          showsVerticalScrollIndicator={false}
          ListFooterComponent={loading ? <TypingDots /> : null}
          ListHeaderComponent={
            showChips ? (
              <View style={st.chipsWrap}>
                <Text style={st.chipsLabel}>SUGGESTED</Text>
                <View style={st.chipsRow}>
                  {CHIPS.map(chip => (
                    <TouchableOpacity key={chip} style={st.chip} onPress={() => send(chip)}>
                      <Text style={st.chipText}>{chip}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            ) : null
          }
        />

        {/* Input bar */}
        <View style={st.inputBar}>
          <TextInput
            style={st.input}
            value={input}
            onChangeText={setInput}
            placeholder="Plan something, ask anything…"
            placeholderTextColor={C.inkMuted}
            multiline
            maxLength={500}
            onSubmitEditing={() => send()}
            returnKeyType="send"
            blurOnSubmit={false}
          />
          <TouchableOpacity
            onPress={() => send()}
            disabled={!input.trim() || loading}
            style={[st.sendBtn, (!input.trim() || loading) && { opacity:0.4 }]}
          >
            {loading
              ? <ActivityIndicator size="small" color="#fff" />
              : <Ionicons name="send" size={16} color="#fff" />
            }
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
const st = StyleSheet.create({
  safe: { flex:1, backgroundColor:C.bg },

  header: {
    flexDirection:"row", alignItems:"center", justifyContent:"space-between",
    paddingHorizontal:20, paddingVertical:13,
    borderBottomWidth:1, borderBottomColor:C.border,
    shadowColor:"#0F172A", shadowOffset:{width:0,height:1}, shadowOpacity:0.06, shadowRadius:4, elevation:2,
  },
  headerLeft:  { flexDirection:"row", alignItems:"center", gap:10 },
  headerTitle: { fontSize:16, fontWeight:"800", color:C.ink },
  headerSub:   { fontSize:11, color:C.inkSub, marginTop:1 },
  onlineDot:   { width:10, height:10, borderRadius:5, backgroundColor:C.green,
                 shadowColor:C.green, shadowOffset:{width:0,height:0}, shadowOpacity:0.6, shadowRadius:4 },
  clearBtn:    { padding:8, borderRadius:R.sm, backgroundColor:C.bgInput },

  listContent: { paddingHorizontal:14, paddingTop:12, paddingBottom:8, gap:0 },

  chipsWrap: { paddingBottom:16, gap:8 },
  chipsLabel:{ fontSize:10, fontWeight:"800", color:C.inkMuted, letterSpacing:1, paddingLeft:4 },
  chipsRow:  { flexDirection:"row", flexWrap:"wrap", gap:8 },
  chip: {
    paddingHorizontal:14, paddingVertical:8,
    backgroundColor:C.bgCard, borderRadius:R.full,
    borderWidth:1, borderColor:C.indigoBorder,
  },
  chipText: { fontSize:13, color:C.indigo, fontWeight:"600" },

  bubbleRow:     { flexDirection:"row", alignItems:"flex-end", marginBottom:14, gap:8 },
  bubbleRowUser: { flexDirection:"row-reverse" },

  avatar: {
    width:32, height:32, borderRadius:16,
    alignItems:"center", justifyContent:"center",
    borderWidth:1, borderColor:C.indigoBorder,
  },

  bubble: {
    maxWidth:"80%", paddingHorizontal:14, paddingVertical:10,
    borderRadius:R.lg,
  },
  bubbleUser: { backgroundColor:C.indigo },
  bubbleAI:   { backgroundColor:C.bgCard, borderWidth:1, borderColor:C.border },
  bubbleErr:  { backgroundColor:C.redSoft, borderColor:C.redBorder, borderWidth:1 },
  bubbleText: { fontSize:15, color:C.ink, lineHeight:22 },

  draftCard: {
    maxWidth:"85%",
    borderRadius:R.md, borderWidth:1, borderColor:C.indigoBorder,
    padding:13, gap:5,
    shadowColor:"#0F172A", shadowOffset:{width:0,height:2}, shadowOpacity:0.06, shadowRadius:6, elevation:2,
  },
  draftHeader:  { flexDirection:"row", alignItems:"center", gap:6 },
  draftLabel:   { fontSize:10, fontWeight:"800", color:C.indigo, letterSpacing:1 },
  draftTitle:   { fontSize:14, fontWeight:"700", color:C.ink },
  draftMeta:    { fontSize:12, color:C.inkSub },
  draftBtn:     { flexDirection:"row", alignItems:"center", justifyContent:"center", gap:6,
                  marginTop:8, backgroundColor:C.indigo, borderRadius:R.sm, paddingVertical:9 },
  draftBtnDone: { backgroundColor:C.green },
  draftBtnText: { fontSize:12, fontWeight:"700", color:"#fff" },

  inputBar: {
    flexDirection:"row", alignItems:"flex-end", gap:10,
    paddingHorizontal:12, paddingVertical:10,
    borderTopWidth:1, borderTopColor:C.border,
  },
  input: {
    flex:1, backgroundColor:C.bgInput,
    borderRadius:R.xl, borderWidth:1, borderColor:C.border,
    paddingHorizontal:16, paddingVertical:10,
    fontSize:15, color:C.ink, maxHeight:120,
  },
  sendBtn: {
    width:44, height:44, borderRadius:22,
    alignItems:"center", justifyContent:"center",
  },

  // referenced in config
});
