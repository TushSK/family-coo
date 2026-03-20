// app/(auth)/login.tsx
// Tester login — two modes:
//   1. Access Token entry: tester pastes token from approval email/page
//      → validates with /api/waitlist/validate → logs in with their email
//   2. Owner shortcut: "Continue as owner" hardcoded to tushar.khandare@gmail.com
//      → skips token validation (local dev / owner use only)

import React, { useState } from "react";
import {
  View, Text, TouchableOpacity, TextInput, StyleSheet,
  SafeAreaView, ActivityIndicator, KeyboardAvoidingView, Platform,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { C, R, S, API_BASE } from "../constants/config";
import { useAuth } from "../context/AuthContext";

const OWNER_EMAIL = "tushar.khandare@gmail.com";

export default function LoginScreen() {
  const { markLogin }  = useAuth();
  const [mode, setMode]       = useState<"choose"|"token">("choose");
  const [token, setToken]     = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  // ── Owner shortcut (local dev / admin) ────────────────────────────────────
  async function handleOwnerLogin() {
    setLoading(true);
    setError("");
    try {
      await markLogin(OWNER_EMAIL);
    } catch {
      setError("Login failed. Try again.");
    } finally {
      setLoading(false);
    }
  }

  // ── Token-based login (testers) ───────────────────────────────────────────
  async function handleTokenLogin() {
    const t = token.trim();
    if (!t) { setError("Please paste your access token."); return; }
    setLoading(true);
    setError("");
    try {
      const res  = await fetch(`${API_BASE}/api/waitlist/validate?token=${encodeURIComponent(t)}`);
      const data = await res.json();
      if (!res.ok || !data.approved) {
        setError(data.detail || "Invalid or expired token. Check your approval email.");
        return;
      }
      await markLogin(data.email);
    } catch {
      setError("Could not connect to server. Check your internet connection.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.gradTop} />
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

        <View style={st.spacer} />

        {/* ── Choose mode ── */}
        {mode === "choose" && (
          <>
            {/* Tester token entry */}
            <TouchableOpacity
              style={[st.primaryBtn, S.sm]}
              onPress={() => setMode("token")}
              activeOpacity={0.85}
            >
              <Ionicons name="key-outline" size={18} color="#fff" />
              <Text style={st.primaryBtnText}>Enter Access Token</Text>
            </TouchableOpacity>

            <Text style={st.orDivider}>— received your approval email? paste your token —</Text>

            {/* Owner shortcut */}
            <TouchableOpacity
              style={[st.ownerBtn, S.sm]}
              onPress={handleOwnerLogin}
              disabled={loading}
              activeOpacity={0.85}
            >
              {loading
                ? <ActivityIndicator color={C.acc} size="small"/>
                : <>
                    <Text style={st.googleG}>G</Text>
                    <Text style={st.ownerBtnText}>Continue as owner</Text>
                  </>
              }
            </TouchableOpacity>
          </>
        )}

        {/* ── Token entry mode ── */}
        {mode === "token" && (
          <>
            <TouchableOpacity
              style={st.backRow}
              onPress={() => { setMode("choose"); setError(""); setToken(""); }}
            >
              <Ionicons name="arrow-back" size={16} color={C.acc} />
              <Text style={st.backText}>Back</Text>
            </TouchableOpacity>

            <Text style={st.tokenLabel}>PASTE YOUR ACCESS TOKEN</Text>
            <Text style={st.tokenHint}>
              Copy the token from your approval email or the "You're in" page.
            </Text>

            <TextInput
              style={[st.tokenInput, error ? st.tokenInputErr : null]}
              value={token}
              onChangeText={t => { setToken(t); setError(""); }}
              placeholder="e.g. 7cbb9ca2-df78-4e4a-be43-a17645fa38be"
              placeholderTextColor={C.ink3}
              autoCapitalize="none"
              autoCorrect={false}
              autoFocus
              multiline
            />

            {error ? (
              <View style={st.errRow}>
                <Ionicons name="alert-circle-outline" size={14} color={C.red} />
                <Text style={st.errText}>{error}</Text>
              </View>
            ) : null}

            <TouchableOpacity
              style={[st.primaryBtn, S.sm, { marginTop: 16 }, !token.trim() && { opacity: 0.45 }]}
              onPress={handleTokenLogin}
              disabled={loading || !token.trim()}
              activeOpacity={0.85}
            >
              {loading
                ? <ActivityIndicator color="#fff" size="small"/>
                : <>
                    <Ionicons name="checkmark-circle-outline" size={18} color="#fff" />
                    <Text style={st.primaryBtnText}>Verify & Sign In</Text>
                  </>
              }
            </TouchableOpacity>
          </>
        )}

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
  primaryBtn:   { width:"100%", backgroundColor:C.acc2, borderRadius:R.lg, flexDirection:"row", alignItems:"center", justifyContent:"center", paddingVertical:15, gap:10, marginBottom:12 },
  primaryBtnText:{ fontSize:15, fontWeight:"700", color:"#fff" },
  orDivider:    { fontSize:11, color:C.ink3, textAlign:"center", marginVertical:12 },
  ownerBtn:     { width:"100%", backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:0.5, borderColor:C.border2, flexDirection:"row", alignItems:"center", justifyContent:"center", paddingVertical:15, gap:12, marginBottom:20 },
  ownerBtnText: { fontSize:15, fontWeight:"600", color:C.ink },
  googleG:      { fontSize:18, fontWeight:"800", color:"#4285F4" },
  backRow:      { flexDirection:"row", alignItems:"center", gap:6, alignSelf:"flex-start", marginBottom:20 },
  backText:     { fontSize:14, color:C.acc, fontWeight:"600" },
  tokenLabel:   { alignSelf:"flex-start", fontSize:10, fontWeight:"700", color:C.ink3, letterSpacing:1, marginBottom:8 },
  tokenHint:    { alignSelf:"flex-start", fontSize:13, color:C.ink2, lineHeight:19, marginBottom:14 },
  tokenInput:   { width:"100%", backgroundColor:C.bgCard, borderRadius:R.lg, borderWidth:0.5, borderColor:C.border2, paddingHorizontal:14, paddingVertical:13, fontSize:13, color:C.ink, fontFamily:Platform.OS==="ios"?"Menlo":"monospace", minHeight:70 },
  tokenInputErr:{ borderColor:C.red },
  errRow:       { flexDirection:"row", alignItems:"center", gap:6, alignSelf:"flex-start", marginTop:8 },
  errText:      { fontSize:12, color:C.red, flex:1, lineHeight:18 },
  badges:       { flexDirection:"row", gap:10, marginTop:20, marginBottom:16, flexWrap:"wrap", justifyContent:"center" },
  badge:        { flexDirection:"row", alignItems:"center", gap:5, backgroundColor:C.soft, borderRadius:R.full, borderWidth:0.5, borderColor:C.border, paddingHorizontal:10, paddingVertical:5 },
  badgeEmoji:   { fontSize:12 },
  badgeText:    { fontSize:10, fontWeight:"700", color:C.acc },
  terms:        { fontSize:12, color:C.ink3, textAlign:"center", lineHeight:18 },
});
