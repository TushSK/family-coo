// app/constants/config.ts

// Hardcoded for production — single user private app
// Change RENDER_URL if your Render service URL changes
const RENDER_URL = "https://family-coo.onrender.com";

export const API_BASE: string =
  (typeof process !== "undefined" && process.env?.EXPO_PUBLIC_API_BASE)
    ? process.env.EXPO_PUBLIC_API_BASE
    : RENDER_URL;

export const USER_ID = "tushar.khandare@gmail.com";

export const C = {
  bg:           "#F8FAFC",
  bgCard:       "#FFFFFF",
  bgInput:      "#F1F5F9",
  indigo:       "#4F46E5",
  indigoDark:   "#3730A3",
  indigoSoft:   "#EEF2FF",
  indigoBorder: "#C7D2FE",
  green:        "#10B981",
  greenSoft:    "#ECFDF5",
  greenBorder:  "#A7F3D0",
  amber:        "#F59E0B",
  amberSoft:    "#FFFBEB",
  amberBorder:  "#FDE68A",
  red:          "#EF4444",
  redSoft:      "#FEF2F2",
  redBorder:    "#FECACA",
  ink:          "#0F172A",
  inkMid:       "#1E293B",
  inkSub:       "#64748B",
  inkMuted:     "#94A3B8",
  border:       "#E2E8F0",
  borderSoft:   "#F1F5F9",
  slateLight:   "#CBD5E1",
};

export const R = { xs:4, sm:6, md:10, lg:16, xl:22, full:9999 };

export const S = {
  xs: { shadowColor:"#0F172A", shadowOffset:{width:0,height:1}, shadowOpacity:0.04, shadowRadius:3,  elevation:1 },
  sm: { shadowColor:"#0F172A", shadowOffset:{width:0,height:2}, shadowOpacity:0.06, shadowRadius:6,  elevation:2 },
  md: { shadowColor:"#0F172A", shadowOffset:{width:0,height:4}, shadowOpacity:0.08, shadowRadius:12, elevation:4 },
};

// Legacy aliases
export const COLORS = {
  bg: C.bg, bgCard: C.bgCard, bgInput: C.bgInput,
  accent: C.indigo, accentDark: C.indigoDark, accentSoft: C.indigoSoft,
  success: C.green, successSoft: C.greenSoft,
  warning: C.amber, warningSoft: C.amberSoft,
  danger: C.red, dangerSoft: C.redSoft,
  purple: "#8B5CF6", purpleSoft: "#EDE9FE",
  textPrimary: C.ink, textSecondary: C.inkSub, textMuted: C.inkMuted,
  border: C.border, borderSoft: C.borderSoft,
  tabActive: C.indigo, tabInactive: C.inkMuted, tabBg: C.bgCard,
};
export const RADIUS = R;
export const SHADOW = S;
