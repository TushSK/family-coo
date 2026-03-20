// app/constants/config.ts  — v3 Lavender theme

//const RENDER_URL = "http://localhost:8000";  // ← local dev
const RENDER_URL = "https://family-coo.onrender.com";

export const API_BASE: string =
  (typeof process !== "undefined" && process.env?.EXPO_PUBLIC_API_BASE)
    ? process.env.EXPO_PUBLIC_API_BASE
    : RENDER_URL;

export const USER_ID = "tushar.khandare@gmail.com"; // owner fallback only — use getActiveUser() for dynamic email

// ── Design tokens ─────────────────────────────────────────────────────────────
export const C = {
  // Backgrounds
  bg:        "#F8F7FF",
  bg2:       "#F0EFFE",
  bgCard:    "#FFFFFF",

  // Accent — indigo/violet
  acc:       "#6D28D9",
  acc2:      "#7C3AED",
  soft:      "#EDE9FE",
  border:    "#DDD6FE",
  border2:   "#E8E4FF",

  // Semantic
  green:     "#059669",
  greenS:    "#D1FAE5",
  greenB:    "#A7F3D0",
  amber:     "#D97706",
  amberS:    "#FEF3C7",
  amberB:    "#FCD34D",
  red:       "#DC2626",
  redS:      "#FEE2E2",
  redB:      "#FECACA",
  teal:      "#0891B2",
  tealS:     "#E0F2FE",

  // Typography
  ink:       "#1E1B4B",
  ink2:      "#4B5563",
  ink3:      "#9CA3AF",

  // Member colours
  tushar:    "#6D28D9",
  sonam:     "#DB2777",
  drishti:   "#D97706",
  family:    "#059669",
};

export const R = { xs:4, sm:6, md:10, lg:14, xl:18, full:9999 };

export const S = {
  xs: { shadowColor:"#6D28D9", shadowOffset:{width:0,height:1}, shadowOpacity:0.05, shadowRadius:3,  elevation:1 },
  sm: { shadowColor:"#6D28D9", shadowOffset:{width:0,height:2}, shadowOpacity:0.08, shadowRadius:6,  elevation:2 },
  md: { shadowColor:"#6D28D9", shadowOffset:{width:0,height:4}, shadowOpacity:0.12, shadowRadius:12, elevation:4 },
};

// Legacy aliases so older files compile
export const COLORS = {
  bg:C.bg, bgCard:C.bgCard, bgInput:C.bg2,
  accent:C.acc2, accentDark:C.acc, accentSoft:C.soft,
  success:C.green, successSoft:C.greenS,
  warning:C.amber, warningSoft:C.amberS,
  danger:C.red,   dangerSoft:C.redS,
  purple:C.acc2,  purpleSoft:C.soft,
  textPrimary:C.ink, textSecondary:C.ink2, textMuted:C.ink3,
  border:C.border, borderSoft:C.border2,
  tabActive:C.acc, tabInactive:C.ink3, tabBg:C.bgCard,
};
export const RADIUS = R;
export const SHADOW = S;

// ── Auth helpers ──────────────────────────────────────────────────────────────
export const STORAGE_KEYS = {
  pinVerified:  "fcoo_pin_verified",
  onboardDone:  "fcoo_onboard_done",
  userEmail:    "fcoo_user_email",
  userPin:      "fcoo_user_pin",      // each user sets their own PIN
  pinSkipped:   "fcoo_pin_skipped",   // true if user chose to skip PIN setup
};

export const APP_PIN = "4240"; // owner-only fallback

// Dynamic user ID — set at login, read by all screens
let _activeUserId = "tushar.khandare@gmail.com";
export const getActiveUser = () => _activeUserId;
export const setActiveUser = (email: string) => { _activeUserId = email; };