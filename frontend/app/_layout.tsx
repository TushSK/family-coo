// app/_layout.tsx  — Root layout with auth gating (fixed loop)
import React, { useEffect, useState, useCallback } from "react";
import { View, StyleSheet } from "react-native";
import { Slot, useRouter, useSegments } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { C, STORAGE_KEYS } from "./constants/config";

SplashScreen.preventAutoHideAsync();

type AuthState = "loading" | "login" | "pin" | "onboard" | "app";

export default function RootLayout() {
  const [auth,   setAuth]   = useState<AuthState>("loading");
  const [ready,  setReady]  = useState(false);
  const router   = useRouter();
  const segments = useSegments();

  // ── Re-check every time segments change (catches post-onboard navigation) ──
  const checkAuth = useCallback(async () => {
    try {
      const email      = await AsyncStorage.getItem(STORAGE_KEYS.userEmail);
      const pinOk      = await AsyncStorage.getItem(STORAGE_KEYS.pinVerified);
      const onboardDone= await AsyncStorage.getItem(STORAGE_KEYS.onboardDone);

      if (!email)        setAuth("login");
      else if (!pinOk)   setAuth("pin");
      else if (!onboardDone) setAuth("onboard");
      else               setAuth("app");
    } catch {
      setAuth("login");
    } finally {
      setReady(true);
      await SplashScreen.hideAsync().catch(()=>{});
    }
  }, []);

  // Run once on mount
  useEffect(() => { checkAuth(); }, []);

  // Guard on every route change
  useEffect(() => {
    if (!ready || auth === "loading") return;

    const inAuth = segments[0] === "(auth)";
    const inTabs = segments[0] === "(tabs)";

    // Already in the right place — do nothing
    if (auth === "app"     && inTabs) return;
    if (auth === "login"   && inAuth) return;
    if (auth === "pin"     && inAuth) return;
    if (auth === "onboard" && inAuth) return;

    // Redirect to correct place
    if (auth === "login")   router.replace("/(auth)/login");
    if (auth === "pin")     router.replace("/(auth)/pin");
    if (auth === "onboard") router.replace("/(auth)/onboard");
    if (auth === "app")     router.replace("/(tabs)");
  }, [auth, ready, segments]);

  return (
    <View style={st.root}>
      <Slot />
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
});
