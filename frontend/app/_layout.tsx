// app/_layout.tsx  — Root layout using AuthContext (no race condition)
import React, { useEffect } from "react";
import { View, StyleSheet } from "react-native";
import { Slot, useRouter, useSegments } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { C } from "./constants/config";

SplashScreen.preventAutoHideAsync();

function AuthGate() {
  const { auth } = useAuth();
  const router   = useRouter();
  const segments = useSegments();

  useEffect(() => {
    if (auth !== "loading") {
      SplashScreen.hideAsync().catch(() => {});
    }
  }, [auth]);

  useEffect(() => {
    if (auth === "loading") return;

    const inAuth = segments[0] === "(auth)";
    const inTabs = segments[0] === "(tabs)";

    if (auth === "app"     && inTabs) return;
    if (auth === "login"   && inAuth) return;
    if (auth === "pin"     && inAuth) return;
    if (auth === "onboard" && inAuth) return;

    if (auth === "pin" || auth === "pin_setup") router.replace("/(auth)/pin");
    if (auth === "pin")     router.replace("/(auth)/pin");
    if (auth === "onboard") router.replace("/(auth)/onboard");
    if (auth === "app")     router.replace("/(tabs)");
  }, [auth, segments]);

  return <Slot />;
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <View style={st.root}>
        <AuthGate />
      </View>
    </AuthProvider>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
});
