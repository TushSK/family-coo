// app/(auth)/pin.tsx
import React, { useState, useEffect, useRef } from "react";
import {
  View, Text, TouchableOpacity, StyleSheet,
  SafeAreaView, Animated,
} from "react-native";
import { C, R, S, APP_PIN } from "../constants/config";
import { useAuth } from "../context/AuthContext";

const KEYS = [1,2,3,4,5,6,7,8,9,null,0,"⌫"] as const;

export default function PINScreen() {
  const { markPin } = useAuth();
  const [pin,   setPin]   = useState<string[]>([]);
  const [error, setError] = useState("");
  const shake = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (pin.length === 4) verifyPIN();
  }, [pin]);

  function tapKey(k: typeof KEYS[number]) {
    setError("");
    if (k === "⌫")               setPin(prev => prev.slice(0,-1));
    else if (k !== null && pin.length < 4) setPin(prev => [...prev, String(k)]);
  }

  async function verifyPIN() {
    if (pin.join("") === APP_PIN) {
      // markPin writes AsyncStorage AND updates context → AuthGate redirects automatically
      await markPin();
    } else {
      Animated.sequence([
        Animated.timing(shake, { toValue:10,  duration:50, useNativeDriver:true }),
        Animated.timing(shake, { toValue:-10, duration:50, useNativeDriver:true }),
        Animated.timing(shake, { toValue:10,  duration:50, useNativeDriver:true }),
        Animated.timing(shake, { toValue:0,   duration:50, useNativeDriver:true }),
      ]).start();
      setError("Incorrect PIN — try again");
      setPin([]);
    }
  }

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.gradTop} />
      <View style={st.center}>
        <View style={[st.iconWrap, S.sm]}>
          <Text style={{ fontSize:28 }}>🔐</Text>
        </View>
        <Text style={st.title}>Enter your PIN</Text>
        <Text style={st.sub}>Your household 4-digit passcode</Text>

        <Animated.View style={[st.dots, { transform:[{ translateX:shake }] }]}>
          {[0,1,2,3].map(i => (
            <View key={i} style={[st.dot, i < pin.length && st.dotFilled]} />
          ))}
        </Animated.View>

        <Text style={st.error}>{error}</Text>

        <View style={st.keypad}>
          {KEYS.map((k, i) => (
            k === null
              ? <View key={i} style={st.keyEmpty} />
              : (
                <TouchableOpacity key={i} style={[st.key, S.xs]}
                  onPress={() => tapKey(k)} activeOpacity={0.7}>
                  <Text style={st.keyText}>{k}</Text>
                </TouchableOpacity>
              )
          ))}
        </View>

        <Text style={st.hint}>Hint: your household code</Text>
        <TouchableOpacity style={st.reset}>
          <Text style={st.resetText}>Forgot PIN? Reset via Google →</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe:      { flex:1, backgroundColor:C.bg },
  gradTop:   { position:"absolute", top:0, left:0, right:0, height:260, backgroundColor:C.soft, opacity:0.5, borderBottomLeftRadius:80, borderBottomRightRadius:80 },
  center:    { flex:1, alignItems:"center", paddingHorizontal:28, paddingTop:56 },
  iconWrap:  { width:62, height:62, borderRadius:18, backgroundColor:C.soft, borderWidth:0.5, borderColor:C.border, alignItems:"center", justifyContent:"center", marginBottom:16 },
  title:     { fontSize:22, fontWeight:"800", color:C.ink, marginBottom:6 },
  sub:       { fontSize:13, color:C.ink2, textAlign:"center", marginBottom:32 },
  dots:      { flexDirection:"row", gap:18, marginBottom:8 },
  dot:       { width:14, height:14, borderRadius:7, borderWidth:1.5, borderColor:C.border, backgroundColor:"transparent" },
  dotFilled: { backgroundColor:C.acc, borderColor:C.acc },
  error:     { fontSize:12, color:C.red, minHeight:20, marginBottom:24, textAlign:"center" },
  keypad:    { width:"100%", maxWidth:280, flexDirection:"row", flexWrap:"wrap", gap:10, justifyContent:"center" },
  key:       { width:82, height:62, borderRadius:R.lg, backgroundColor:C.bgCard, borderWidth:0.5, borderColor:C.border2, alignItems:"center", justifyContent:"center" },
  keyEmpty:  { width:82, height:62 },
  keyText:   { fontSize:22, fontWeight:"700", color:C.ink },
  hint:      { marginTop:24, fontSize:12, color:C.acc, fontWeight:"600", backgroundColor:C.soft, borderRadius:R.full, paddingHorizontal:14, paddingVertical:5 },
  reset:     { marginTop:14 },
  resetText: { fontSize:12, color:C.ink3 },
});
