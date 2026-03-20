// app/(auth)/pin.tsx
// Dual-mode PIN screen:
//   Mode "setup"  → first login, user sets their own 4-digit PIN (or skips)
//   Mode "enter"  → returning user, enters the PIN they set previously
//
// PIN is personal to each user — stored in AsyncStorage, never shared.
// Skipping PIN is fine — user just logs in with email each time instead.

import React, { useState, useEffect, useRef } from "react";
import {
  View, Text, TouchableOpacity, StyleSheet,
  SafeAreaView, Animated,
} from "react-native";
import { C, R, S, STORAGE_KEYS } from "../constants/config";
import { useAuth } from "../context/AuthContext";
import AsyncStorage from "@react-native-async-storage/async-storage";

const KEYS = [1,2,3,4,5,6,7,8,9,null,0,"⌫"] as const;

export default function PINScreen() {
  const { auth, markPin, markPinSet, markPinSkip } = useAuth();
  const isSetup = auth === "pin_setup";

  const [pin,     setPin]     = useState<string[]>([]);
  const [confirm, setConfirm] = useState<string[]>([]); // used in setup mode
  const [stage,   setStage]   = useState<"enter"|"confirm">("enter"); // setup has 2 stages
  const [error,   setError]   = useState("");
  const shake = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (isSetup) {
      // Setup mode: collect PIN then confirm
      if (stage === "enter"   && pin.length === 4) { setConfirm([]); setStage("confirm"); setPin([]); }
      if (stage === "confirm" && pin.length === 4)  handleConfirm();
    } else {
      // Enter mode: verify against stored PIN
      if (pin.length === 4) handleVerify();
    }
  }, [pin]);

  function doShake(msg: string) {
    setError(msg);
    setPin([]);
    Animated.sequence([
      Animated.timing(shake, { toValue:10,  duration:50, useNativeDriver:true }),
      Animated.timing(shake, { toValue:-10, duration:50, useNativeDriver:true }),
      Animated.timing(shake, { toValue:10,  duration:50, useNativeDriver:true }),
      Animated.timing(shake, { toValue:0,   duration:50, useNativeDriver:true }),
    ]).start();
  }

  async function handleConfirm() {
    if (pin.join("") !== confirm.join("")) {
      setStage("enter");
      setConfirm([]);
      doShake("PINs didn't match — try again");
      return;
    }
    await markPinSet(pin.join(""));
  }

  async function handleVerify() {
    const stored = await AsyncStorage.getItem(STORAGE_KEYS.userPin);
    if (pin.join("") === stored) {
      await markPin();
    } else {
      doShake("Incorrect PIN — try again");
    }
  }

  function tapKey(k: typeof KEYS[number]) {
    setError("");
    if (k === "⌫")                         setPin(prev => prev.slice(0,-1));
    else if (k !== null && pin.length < 4)  setPin(prev => [...prev, String(k)]);
  }

  // ── Labels based on mode + stage ─────────────────────────────────────────
  const title = isSetup
    ? (stage === "enter" ? "Set your PIN" : "Confirm your PIN")
    : "Enter your PIN";

  const subtitle = isSetup
    ? (stage === "enter"
        ? "Choose a 4-digit PIN for quick access"
        : "Enter the same PIN again to confirm")
    : "Enter your 4-digit PIN to continue";

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.gradTop}/>
      <View style={st.center}>

        <View style={[st.iconWrap, S.sm]}>
          <Text style={{ fontSize:28 }}>{isSetup ? "🔑" : "🔐"}</Text>
        </View>

        <Text style={st.title}>{title}</Text>
        <Text style={st.sub}>{subtitle}</Text>

        <Animated.View style={[st.dots, { transform:[{ translateX:shake }] }]}>
          {[0,1,2,3].map(i => (
            <View key={i} style={[st.dot, i < pin.length && st.dotFilled]}/>
          ))}
        </Animated.View>

        <Text style={st.error}>{error}</Text>

        <View style={st.keypad}>
          {KEYS.map((k, i) => (
            k === null
              ? <View key={i} style={st.keyEmpty}/>
              : (
                <TouchableOpacity key={i} style={[st.key, S.xs]}
                  onPress={() => tapKey(k)} activeOpacity={0.7}>
                  <Text style={st.keyText}>{k}</Text>
                </TouchableOpacity>
              )
          ))}
        </View>

        {/* Skip — only shown in setup mode */}
        {isSetup && (
          <TouchableOpacity style={st.skipBtn} onPress={markPinSkip}>
            <Text style={st.skipText}>Skip — I'll log in with email instead</Text>
          </TouchableOpacity>
        )}

        {/* Stage indicator for setup */}
        {isSetup && (
          <View style={st.stageRow}>
            <View style={[st.stageDot, stage === "enter"   && st.stageDotActive]}/>
            <View style={[st.stageDot, stage === "confirm" && st.stageDotActive]}/>
          </View>
        )}

      </View>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe:          { flex:1, backgroundColor:C.bg },
  gradTop:       { position:"absolute", top:0, left:0, right:0, height:260, backgroundColor:C.soft, opacity:0.5, borderBottomLeftRadius:80, borderBottomRightRadius:80 },
  center:        { flex:1, alignItems:"center", paddingHorizontal:28, paddingTop:56 },
  iconWrap:      { width:62, height:62, borderRadius:18, backgroundColor:C.soft, borderWidth:0.5, borderColor:C.border, alignItems:"center", justifyContent:"center", marginBottom:16 },
  title:         { fontSize:22, fontWeight:"800", color:C.ink, marginBottom:6 },
  sub:           { fontSize:13, color:C.ink2, textAlign:"center", marginBottom:32 },
  dots:          { flexDirection:"row", gap:18, marginBottom:8 },
  dot:           { width:14, height:14, borderRadius:7, borderWidth:1.5, borderColor:C.border, backgroundColor:"transparent" },
  dotFilled:     { backgroundColor:C.acc, borderColor:C.acc },
  error:         { fontSize:12, color:C.red, minHeight:20, marginBottom:24, textAlign:"center" },
  keypad:        { width:"100%", maxWidth:280, flexDirection:"row", flexWrap:"wrap", gap:10, justifyContent:"center" },
  key:           { width:82, height:62, borderRadius:R.lg, backgroundColor:C.bgCard, borderWidth:0.5, borderColor:C.border2, alignItems:"center", justifyContent:"center" },
  keyEmpty:      { width:82, height:62 },
  keyText:       { fontSize:22, fontWeight:"700", color:C.ink },
  skipBtn:       { marginTop:28, paddingVertical:10, paddingHorizontal:20 },
  skipText:      { fontSize:13, color:C.ink3, textDecorationLine:"underline", textAlign:"center" },
  stageRow:      { flexDirection:"row", gap:8, marginTop:16 },
  stageDot:      { width:8, height:8, borderRadius:4, backgroundColor:C.border },
  stageDotActive:{ backgroundColor:C.acc },
});
