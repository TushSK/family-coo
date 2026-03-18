// app/context/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { AppState, AppStateStatus } from "react-native";
import { STORAGE_KEYS } from "../constants/config";

export type AuthState = "loading" | "login" | "pin" | "onboard" | "app";

// ── Inactivity config ─────────────────────────────────────────────────────────
// PIN is re-required after this many milliseconds of background time
const INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes
const KEY_LAST_ACTIVE = "fcoo_last_active";

interface AuthCtx {
  auth:           AuthState;
  setAuth:        (s: AuthState) => void;
  markPin:        () => Promise<void>;
  markOnboard:    () => Promise<void>;
  markLogin:      (email: string) => Promise<void>;
  logout:         () => Promise<void>;
  /** Call on significant user interactions to reset the inactivity clock */
  touchActivity:  () => void;
}

const Ctx = createContext<AuthCtx>({
  auth:"loading", setAuth:()=>{},
  markPin:async()=>{}, markOnboard:async()=>{},
  markLogin:async()=>{}, logout:async()=>{},
  touchActivity:()=>{},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>("loading");
  // Track auth state in a ref so AppState handler always has latest value
  const authRef = useRef<AuthState>("loading");
  useEffect(() => { authRef.current = auth; }, [auth]);

  // ── Inactivity helpers ───────────────────────────────────────────────────────
  /** Write current epoch to AsyncStorage — resets the idle clock */
  const stampActivity = useCallback(async () => {
    try {
      await AsyncStorage.setItem(KEY_LAST_ACTIVE, String(Date.now()));
    } catch {}
  }, []);

  /** Exposed so any screen can poke the activity clock */
  const touchActivity = useCallback(() => {
    stampActivity();
  }, [stampActivity]);

  /**
   * Returns true if the user has been inactive long enough to require PIN again.
   * If so, it clears pinVerified and sets auth → "pin".
   */
  const checkInactivity = useCallback(async (): Promise<boolean> => {
    try {
      const raw = await AsyncStorage.getItem(KEY_LAST_ACTIVE);
      if (!raw) return false; // first launch — no stamp yet, no timeout
      const elapsed = Date.now() - parseInt(raw, 10);
      if (elapsed >= INACTIVITY_TIMEOUT_MS) {
        await AsyncStorage.removeItem(STORAGE_KEYS.pinVerified);
        setAuth("pin");
        return true;
      }
    } catch {}
    return false;
  }, []);

  // ── Initial load ─────────────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const email       = await AsyncStorage.getItem(STORAGE_KEYS.userEmail);
        const pinOk       = await AsyncStorage.getItem(STORAGE_KEYS.pinVerified);
        const onboardDone = await AsyncStorage.getItem(STORAGE_KEYS.onboardDone);

        if (!email) { setAuth("login"); return; }
        if (!pinOk) { setAuth("pin");   return; }

        // PIN was verified in a previous session — check staleness before continuing
        const timedOut = await checkInactivity();
        if (timedOut) return; // already set auth to "pin"

        // Fresh enough — proceed normally
        if (!onboardDone) setAuth("onboard");
        else              setAuth("app");
      } catch {
        setAuth("login");
      }
    })();
  }, []);

  // ── AppState listener — re-check on foreground ────────────────────────────
  useEffect(() => {
    const handleAppState = async (nextState: AppStateStatus) => {
      if (nextState === "active") {
        // App came back to foreground — only check timeout if user is already past PIN
        if (authRef.current === "app") {
          const timedOut = await checkInactivity();
          if (!timedOut) stampActivity(); // still valid — refresh stamp
        }
      } else if (nextState === "background" || nextState === "inactive") {
        // App going to background — record when we left
        if (authRef.current === "app") stampActivity();
      }
    };

    const sub = AppState.addEventListener("change", handleAppState);
    return () => sub.remove();
  }, [checkInactivity, stampActivity]);

  // ── Auth transitions ─────────────────────────────────────────────────────────
  const markLogin = useCallback(async (email: string) => {
    await AsyncStorage.setItem(STORAGE_KEYS.userEmail, email);
    setAuth("pin");
  }, []);

  const markPin = useCallback(async () => {
    await AsyncStorage.setItem(STORAGE_KEYS.pinVerified, "1");
    await stampActivity(); // start the inactivity clock fresh after PIN
    const onboardDone = await AsyncStorage.getItem(STORAGE_KEYS.onboardDone);
    setAuth(onboardDone ? "app" : "onboard");
  }, [stampActivity]);

  const markOnboard = useCallback(async () => {
    await AsyncStorage.setItem(STORAGE_KEYS.onboardDone, "1");
    await stampActivity();
    setAuth("app");
  }, [stampActivity]);

  const logout = useCallback(async () => {
    await AsyncStorage.multiRemove([
      STORAGE_KEYS.userEmail,
      STORAGE_KEYS.pinVerified,
      STORAGE_KEYS.onboardDone,
      KEY_LAST_ACTIVE,
    ]);
    setAuth("login");
  }, []);

  return (
    <Ctx.Provider value={{ auth, setAuth, markLogin, markPin, markOnboard, logout, touchActivity }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
