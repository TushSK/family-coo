// app/context/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { STORAGE_KEYS, setActiveUser } from "../constants/config";

// ── States ────────────────────────────────────────────────────────────────────
// loading    → app just opened, checking storage
// login      → no email stored → show login screen
// pin_setup  → first login, no PIN set yet → show PIN setup (with skip)
// pin        → returning user with PIN set → show PIN entry
// onboard    → PIN cleared (or skipped), onboard not done yet
// app        → fully ready

export type AuthState = "loading"|"login"|"pin_setup"|"pin"|"onboard"|"app";

interface AuthCtx {
  auth:        AuthState;
  setAuth:     (s: AuthState) => void;
  markLogin:   (email: string) => Promise<void>;
  markPin:     () => Promise<void>;
  markPinSet:  (pin: string)   => Promise<void>;
  markPinSkip: ()              => Promise<void>;
  markOnboard: ()              => Promise<void>;
  logout:      ()              => Promise<void>;
}

const Ctx = createContext<AuthCtx>({
  auth:"loading", setAuth:()=>{},
  markLogin:async()=>{}, markPin:async()=>{},
  markPinSet:async()=>{}, markPinSkip:async()=>{},
  markOnboard:async()=>{}, logout:async()=>{},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>("loading");

  useEffect(() => {
    (async () => {
      try {
        const email       = await AsyncStorage.getItem(STORAGE_KEYS.userEmail);
        const pinVerified = await AsyncStorage.getItem(STORAGE_KEYS.pinVerified);
        const pinSkipped  = await AsyncStorage.getItem(STORAGE_KEYS.pinSkipped);
        const userPin     = await AsyncStorage.getItem(STORAGE_KEYS.userPin);
        const onboardDone = await AsyncStorage.getItem(STORAGE_KEYS.onboardDone);

        if (!email) {
          setAuth("login");
          return;
        }

        // Restore active user for all API calls
        setActiveUser(email);

        if (!userPin && !pinSkipped) {
          // First time — ask them to set (or skip) a PIN
          setAuth("pin_setup");
        } else if (userPin && !pinVerified) {
          // Has a PIN but hasn't entered it this session
          setAuth("pin");
        } else if (!onboardDone) {
          setAuth("onboard");
        } else {
          setAuth("app");
        }
      } catch {
        setAuth("login");
      }
    })();
  }, []);

  // Called when email login succeeds
  const markLogin = useCallback(async (email: string) => {
    await AsyncStorage.setItem(STORAGE_KEYS.userEmail, email);
    setActiveUser(email);
    // Check if this user already has a PIN or skipped
    const userPin    = await AsyncStorage.getItem(STORAGE_KEYS.userPin);
    const pinSkipped = await AsyncStorage.getItem(STORAGE_KEYS.pinSkipped);
    if (!userPin && !pinSkipped) {
      setAuth("pin_setup"); // first login → prompt to set PIN
    } else if (userPin) {
      setAuth("pin");       // has PIN → ask for it
    } else {
      // skipped PIN previously — go straight to onboard/app
      const onboardDone = await AsyncStorage.getItem(STORAGE_KEYS.onboardDone);
      setAuth(onboardDone ? "app" : "onboard");
    }
  }, []);

  // Called after user enters correct PIN on returning visit
  const markPin = useCallback(async () => {
    await AsyncStorage.setItem(STORAGE_KEYS.pinVerified, "1");
    const onboardDone = await AsyncStorage.getItem(STORAGE_KEYS.onboardDone);
    setAuth(onboardDone ? "app" : "onboard");
  }, []);

  // Called when user sets a new PIN for the first time
  const markPinSet = useCallback(async (pin: string) => {
    await AsyncStorage.setItem(STORAGE_KEYS.userPin, pin);
    await AsyncStorage.setItem(STORAGE_KEYS.pinVerified, "1");
    const onboardDone = await AsyncStorage.getItem(STORAGE_KEYS.onboardDone);
    setAuth(onboardDone ? "app" : "onboard");
  }, []);

  // Called when user skips PIN setup
  const markPinSkip = useCallback(async () => {
    await AsyncStorage.setItem(STORAGE_KEYS.pinSkipped, "1");
    const onboardDone = await AsyncStorage.getItem(STORAGE_KEYS.onboardDone);
    setAuth(onboardDone ? "app" : "onboard");
  }, []);

  // Called after onboarding finishes
  const markOnboard = useCallback(async () => {
    await AsyncStorage.setItem(STORAGE_KEYS.onboardDone, "1");
    setAuth("app");
  }, []);

  // Full logout — clear everything
  const logout = useCallback(async () => {
    await AsyncStorage.multiRemove([
      STORAGE_KEYS.userEmail,
      STORAGE_KEYS.pinVerified,
      STORAGE_KEYS.onboardDone,
      STORAGE_KEYS.userPin,
      STORAGE_KEYS.pinSkipped,
    ]);
    setAuth("login");
  }, []);

  return (
    <Ctx.Provider value={{
      auth, setAuth,
      markLogin, markPin, markPinSet, markPinSkip,
      markOnboard, logout,
    }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
