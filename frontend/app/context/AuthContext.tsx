// app/context/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { STORAGE_KEYS, setActiveUser } from "../constants/config";

export type AuthState = "loading" | "login" | "pin" | "onboard" | "app";

interface AuthCtx {
  auth:     AuthState;
  setAuth:  (s: AuthState) => void;
  markPin:  () => Promise<void>;
  markOnboard: () => Promise<void>;
  markLogin:   (email: string) => Promise<void>;
  logout:   () => Promise<void>;
}

const Ctx = createContext<AuthCtx>({
  auth:"loading", setAuth:()=>{},
  markPin:async()=>{}, markOnboard:async()=>{},
  markLogin:async()=>{}, logout:async()=>{},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>("loading");

  // Read once on mount
  useEffect(() => {
    (async () => {
      try {
        const email       = await AsyncStorage.getItem(STORAGE_KEYS.userEmail);
        const pinOk       = await AsyncStorage.getItem(STORAGE_KEYS.pinVerified);
        const onboardDone = await AsyncStorage.getItem(STORAGE_KEYS.onboardDone);

        // Restore active user so all API calls use the right email
        if (email) setActiveUser(email);

        if (!email)            setAuth("login");
        else if (!pinOk)       setAuth("pin");
        else if (!onboardDone) setAuth("onboard");
        else                   setAuth("app");
      } catch {
        setAuth("login");
      }
    })();
  }, []);

  // Called after Google login
  const markLogin = useCallback(async (email: string) => {
    await AsyncStorage.setItem(STORAGE_KEYS.userEmail, email);
    setActiveUser(email);  // update global so all API calls use this email
    setAuth("pin");
  }, []);

  // Called after correct PIN
  const markPin = useCallback(async () => {
    await AsyncStorage.setItem(STORAGE_KEYS.pinVerified, "1");
    const onboardDone = await AsyncStorage.getItem(STORAGE_KEYS.onboardDone);
    setAuth(onboardDone ? "app" : "onboard");
  }, []);

  // Called after onboarding finishes
  const markOnboard = useCallback(async () => {
    await AsyncStorage.setItem(STORAGE_KEYS.onboardDone, "1");
    setAuth("app");
  }, []);

  // Logout — clear everything
  const logout = useCallback(async () => {
    await AsyncStorage.multiRemove([
      STORAGE_KEYS.userEmail,
      STORAGE_KEYS.pinVerified,
      STORAGE_KEYS.onboardDone,
    ]);
    setAuth("login");
  }, []);

  return (
    <Ctx.Provider value={{ auth, setAuth, markLogin, markPin, markOnboard, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
