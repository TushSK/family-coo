// app/(auth)/login.tsx
import React, { useState } from "react";
import {
  View, Text, TouchableOpacity, StyleSheet,
  SafeAreaView, ActivityIndicator, Image, Platform,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useRouter } from "expo-router";
import { C, R, S, STORAGE_KEYS, USER_ID } from "../constants/config";

export default function LoginScreen() {
  const router  = useRouter();
  const [loading, setLoading] = useState(false);

  // Simulate Google OAuth — replace with real expo-auth-session in production
  async function handleGoogle() {
    setLoading(true);
    try {
      // TODO: replace with real OAuth flow
      // const result = await promptAsync();
      // if (result.type !== "success") return;
      await new Promise(r => setTimeout(r, 800)); // simulate network
      await AsyncStorage.setItem(STORAGE_KEYS.userEmail, USER_ID);
      router.replace("/(auth)/pin");
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={st.safe}>
      {/* Gradient bg approximation */}
      <View style={st.gradTop} />

      <View style={st.center}>
        {/* Logo */}
        <View style={[st.logoWrap, S.md]}>
          <Text style={st.logoEmoji}>🏠</Text>
        </View>
        <Text style={st.title}>Family COO</Text>
        <Text style={st.sub}>Your AI household executive assistant</Text>

        <View style={st.spacer} />

        {/* Google button */}
        <TouchableOpacity
          style={[st.googleBtn, S.sm]}
          onPress={handleGoogle}
          disabled={loading}
          activeOpacity={0.85}
        >
          {loading ? (
            <ActivityIndicator color={C.acc} size="small" />
          ) : (
            <>
              {/* Google G icon via text — replace with SVG asset if desired */}
              <Text style={st.googleG}>G</Text>
              <Text style={st.googleText}>Continue with Google</Text>
            </>
          )}
        </TouchableOpacity>

        {/* Security badges */}
        <View style={st.badges}>
          {[["🔒","Encrypted"],["🛡️","OAuth 2.0"],["👁️","No data sold"]].map(([e,l])=>(
            <View key={l} style={st.badge}>
              <Text style={st.badgeEmoji}>{e}</Text>
              <Text style={st.badgeText}>{l}</Text>
            </View>
          ))}
        </View>

        <Text style={st.terms}>
          By continuing you agree to our Terms of Service.{"\n"}
          Your profile stays private and encrypted.
        </Text>
      </View>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe:       { flex:1, backgroundColor:C.bg },
  gradTop:    {
    position:"absolute", top:0, left:0, right:0, height:280,
    backgroundColor:C.soft, opacity:0.5, borderBottomLeftRadius:80, borderBottomRightRadius:80,
  },
  center:     { flex:1, alignItems:"center", paddingHorizontal:28, paddingTop:64, paddingBottom:32 },
  logoWrap:   {
    width:80, height:80, borderRadius:22,
    backgroundColor:C.acc2, alignItems:"center", justifyContent:"center", marginBottom:20,
  },
  logoEmoji:  { fontSize:40 },
  title:      { fontSize:28, fontWeight:"800", color:C.ink, marginBottom:8 },
  sub:        { fontSize:14, color:C.ink2, textAlign:"center", lineHeight:21 },
  spacer:     { flex:1, minHeight:32 },
  googleBtn:  {
    width:"100%", backgroundColor:C.bgCard,
    borderRadius:R.lg, borderWidth:0.5, borderColor:C.border2,
    flexDirection:"row", alignItems:"center", justifyContent:"center",
    paddingVertical:15, gap:12, marginBottom:20,
  },
  googleG:    { fontSize:18, fontWeight:"800", color:"#4285F4" },
  googleText: { fontSize:15, fontWeight:"600", color:C.ink },
  badges:     { flexDirection:"row", gap:10, marginBottom:24, flexWrap:"wrap", justifyContent:"center" },
  badge:      {
    flexDirection:"row", alignItems:"center", gap:5,
    backgroundColor:C.soft, borderRadius:R.full,
    borderWidth:0.5, borderColor:C.border,
    paddingHorizontal:10, paddingVertical:5,
  },
  badgeEmoji: { fontSize:12 },
  badgeText:  { fontSize:10, fontWeight:"700", color:C.acc },
  terms:      { fontSize:12, color:C.ink3, textAlign:"center", lineHeight:18 },
});
