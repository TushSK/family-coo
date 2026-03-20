// app/(auth)/login.tsx
// Simple email-based login for beta testers.
// Tester enters email → backend checks waitlist approval → lets them in.
// No tokens, no copy-paste, no friction.

import React, { useState } from "react";
import {
  View, Text, TouchableOpacity, TextInput, StyleSheet,
  SafeAreaView, ActivityIndicator, KeyboardAvoidingView,
  Platform, Linking,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { C, R, S, API_BASE } from "../constants/config";
import { useAuth } from "../context/AuthContext";

const OWNER_EMAIL   = "tushar.khandare@gmail.com";
const LANDING_URL   = "https://family-coo-landing.vercel.app";

export default function LoginScreen() {
  const { markLogin }         = useAuth();
  const [email, setEmail]     = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");
  const [status, setStatus]   = useState<"idle"|"pending"|"not_found">("idle");

  async function handleSignIn() {
    const e = email.trim().toLowerCase();
    if (!e || !e.includes("@")) {
      setError("Please enter a valid email address.");
      return;
    }
    setLoading(true);
    setError("");
    setStatus("idle");
    try {
      const res  = await fetch(
        `${API_BASE}/api/waitlist/status?email=${encodeURIComponent(e)}`,
        { headers: { Accept: "application/json" } }
      );

      if (res.status === 404) {
        // Not on waitlist at all
        setStatus("not_found");
        setLoading(false);
        return;
      }

      const data = await res.json();

      if (data.status === "approved") {
        await markLogin(e);
        // AuthGate in _layout.tsx handles redirect automatically
      } else {
        // pending / rejected
        setStatus("pending");
      }
    } catch {
      setError("Could not connect. Check your internet and try again.");
    } finally {
      setLoading(false);
    }
  }

  // Owner shortcut — bypasses waitlist check
  async function handleOwnerLogin() {
    setLoading(true);
    await markLogin(OWNER_EMAIL);
    setLoading(false);
  }

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.gradTop}/>
      <KeyboardAvoidingView
        style={st.center}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        {/* Logo */}
        <View style={[st.logoWrap, S.md]}>
          <Text style={st.logoEmoji}>🏠</Text>
        </View>
        <Text style={st.title}>Family COO</Text>
        <Text style={st.sub}>Your AI household executive assistant</Text>

        <View style={st.spacer}/>

        {/* Email input */}
        <Text style={st.inputLabel}>YOUR EMAIL ADDRESS</Text>
        <TextInput
          style={[st.input, error ? st.inputErr : null]}
          value={email}
          onChangeText={t => { setEmail(t); setError(""); setStatus("idle"); }}
          placeholder="you@gmail.com"
          placeholderTextColor={C.ink3}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          autoFocus
          returnKeyType="done"
          onSubmitEditing={handleSignIn}
        />

        {/* Error */}
        {error ? (
          <View style={st.msgRow}>
            <Ionicons name="alert-circle-outline" size={14} color={C.red}/>
            <Text style={[st.msgText, { color: C.red }]}>{error}</Text>
          </View>
        ) : null}

        {/* Pending state */}
        {status === "pending" && (
          <View style={[st.msgRow, st.msgAmber]}>
            <Ionicons name="time-outline" size={14} color={C.amber}/>
            <Text style={[st.msgText, { color: C.amber }]}>
              Your application is pending. We'll approve you soon — check back shortly.
            </Text>
          </View>
        )}

        {/* Not found state */}
        {status === "not_found" && (
          <View style={[st.msgRow, st.msgAmber]}>
            <Ionicons name="information-circle-outline" size={14} color={C.amber}/>
            <View style={{ flex: 1 }}>
              <Text style={[st.msgText, { color: C.amber }]}>
                This email isn't on the waitlist yet.{" "}
                <Text
                  style={{ textDecorationLine: "underline" }}
                  onPress={() => Linking.openURL(LANDING_URL)}
                >
                  Apply for beta access →
                </Text>
              </Text>
            </View>
          </View>
        )}

        {/* Sign in button */}
        <TouchableOpacity
          style={[st.signInBtn, S.sm, (!email.trim() || loading) && { opacity: 0.45 }]}
          onPress={handleSignIn}
          disabled={loading || !email.trim()}
          activeOpacity={0.85}
        >
          {loading
            ? <ActivityIndicator color="#fff" size="small"/>
            : <>
                <Ionicons name="checkmark-circle-outline" size={18} color="#fff"/>
                <Text style={st.signInBtnText}>Sign In</Text>
              </>
          }
        </TouchableOpacity>

        {/* Owner shortcut — subtle, for admin use */}
        <TouchableOpacity
          style={st.ownerLink}
          onPress={handleOwnerLogin}
          disabled={loading}
        >
          <Text style={st.ownerLinkText}>Admin access</Text>
        </TouchableOpacity>

        <View style={st.badges}>
          {[["🔒","Encrypted"],["🛡️","Beta access"],["👁️","No data sold"]].map(([e,l])=>(
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
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe:         { flex:1, backgroundColor:C.bg },
  gradTop:      { position:"absolute", top:0, left:0, right:0, height:280, backgroundColor:C.soft, opacity:0.5, borderBottomLeftRadius:80, borderBottomRightRadius:80 },
  center:       { flex:1, alignItems:"center", paddingHorizontal:28, paddingTop:64, paddingBottom:32 },
  logoWrap:     { width:80, height:80, borderRadius:22, backgroundColor:C.acc2, alignItems:"center", justifyContent:"center", marginBottom:20 },
  logoEmoji:    { fontSize:40 },
  title:        { fontSize:28, fontWeight:"800", color:C.ink, marginBottom:8 },
  sub:          { fontSize:14, color:C.ink2, textAlign:"center", lineHeight:21 },
  spacer:       { flex:1, minHeight:32 },
  inputLabel:   { alignSelf:"flex-start", fontSize:10, fontWeight:"700", color:C.ink3, letterSpacing:1, marginBottom:8 },
  input:        { width:"100%", backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:0.5, borderColor:C.border2, paddingHorizontal:16, paddingVertical:14, fontSize:15, color:C.ink, marginBottom:4 },
  inputErr:     { borderColor:C.red },
  msgRow:       { flexDirection:"row", alignItems:"flex-start", gap:8, width:"100%", backgroundColor:C.amberS, borderRadius:R.md, borderWidth:0.5, borderColor:C.amberB, padding:10, marginTop:8, marginBottom:4 },
  msgAmber:     { backgroundColor:C.amberS, borderColor:C.amberB },
  msgText:      { flex:1, fontSize:12, lineHeight:18 },
  signInBtn:    { width:"100%", backgroundColor:C.acc2, borderRadius:R.lg, flexDirection:"row", alignItems:"center", justifyContent:"center", paddingVertical:15, gap:10, marginTop:16, marginBottom:8 },
  signInBtnText:{ fontSize:15, fontWeight:"700", color:"#fff" },
  ownerLink:    { paddingVertical:10, paddingHorizontal:16, marginBottom:8 },
  ownerLinkText:{ fontSize:12, color:C.ink3, textDecorationLine:"underline" },
  badges:       { flexDirection:"row", gap:10, marginTop:12, marginBottom:16, flexWrap:"wrap", justifyContent:"center" },
  badge:        { flexDirection:"row", alignItems:"center", gap:5, backgroundColor:C.soft, borderRadius:R.full, borderWidth:0.5, borderColor:C.border, paddingHorizontal:10, paddingVertical:5 },
  badgeEmoji:   { fontSize:12 },
  badgeText:    { fontSize:10, fontWeight:"700", color:C.acc },
  terms:        { fontSize:12, color:C.ink3, textAlign:"center", lineHeight:18 },
});
