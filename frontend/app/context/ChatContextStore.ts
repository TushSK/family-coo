// app/context/ChatContextStore.ts
// Simple module-level store — no React, no Zustand, no overhead.
// Any tab sets a pending prompt before navigating to Chat.
// Chat reads + immediately clears it on mount so general chat stays clean.
//
// ─────────────────────────────────────────────────────────────────────────────
// HOW CONTEXT INJECTION WORKS
// ─────────────────────────────────────────────────────────────────────────────
// 1. A tab button calls one of the ctx* builder functions below (e.g. ctxDiningIdeas)
// 2. The builder calls ChatContextStore.set() with a one-shot { prompt, label, source }
// 3. The tab then router.push("/(tabs)/chat")
// 4. On mount, ChatScreen calls ChatContextStore.consume() — which clears _pending —
//    and silently sends the prompt to the AI (no visible user bubble).
// 5. After consume(), _pending is null, so normal chat is NEVER polluted.
// ─────────────────────────────────────────────────────────────────────────────

export interface ChatContext {
  prompt: string;   // the silent message auto-sent to the AI
  label:  string;   // shown in chat header: "Dining Ideas", "Reschedule", etc.
  source: string;   // which tab triggered it — for analytics / debugging
}

let _pending: ChatContext | null = null;

export const ChatContextStore = {
  set(ctx: ChatContext) {
    _pending = ctx;
  },
  consume(): ChatContext | null {
    const c = _pending;
    _pending = null;   // one-shot — clears immediately
    return c;
  },
  peek(): ChatContext | null {
    return _pending;
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Pre-built context builders — called by buttons across tabs.
// Each function is pure: it writes to the store and returns void.
// Params let callers inject live data (prefs, counts, event names, etc.)
// ─────────────────────────────────────────────────────────────────────────────

// ── Calendar tab ──────────────────────────────────────────────────────────────

export function ctxDiningIdeas(
  prefs: string[] = [],
  city = "Tampa, FL",
  budget = "flexible",
  kidFriendly = true,
) {
  const cuisines = prefs.length ? prefs.join(", ") : "Indian cuisine, home cooking";
  const kidsNote = kidFriendly ? " Drishti (our child) will likely join." : " Adults only tonight.";
  ChatContextStore.set({
    label: "Dining Ideas",
    source: "calendar",
    prompt:
      `Suggest 3 dinner options for tonight based on my household preferences. ` +
      `Cuisine we love: ${cuisines}. Location: ${city}. Budget: ${budget}.${kidsNote} ` +
      `For each option include: (1) whether it's a home-cook or takeout/restaurant, ` +
      `(2) a specific dish recommendation (like Paneer Butter Masala for Indian cooking), ` +
      `(3) rough prep time or ETA. Keep it practical and directly actionable.`,
  });
}

export function ctxSuggestActivities(
  freeEvenings: number,
  city = "Tampa, FL",
  radius = "30",
  kidFriendly = true,
  budget = "Under $50",
  energyLevel = "Moderate",
) {
  const kidsNote = kidFriendly ? "Drishti (our child) is joining us" : "adults-only outing";
  ChatContextStore.set({
    label: "Activity Suggestions",
    source: "calendar",
    prompt:
      `I have ${freeEvenings} free evening${freeEvenings !== 1 ? "s" : ""} this week. ` +
      `Suggest 3 specific activity options for our family in the ${city} area (up to ${radius} miles). ` +
      `Context: ${kidsNote}, budget ${budget}, energy level: ${energyLevel}. ` +
      `For each: give the venue name, why it fits our family, estimated cost, and best time to go. ` +
      `Prioritise activities we haven't done recently.`,
  });
}

export function ctxRescheduleConflict(eventA: string, eventB: string, day: string) {
  ChatContextStore.set({
    label: "Reschedule Conflict",
    source: "calendar",
    prompt:
      `I have a scheduling conflict on ${day}: "${eventA}" overlaps with "${eventB}". ` +
      `Help me resolve this — which should I reschedule and why? ` +
      `Suggest a new time slot that works, and draft a quick calendar note for the change.`,
  });
}

export function ctxEventDetails(eventSummary: string) {
  ChatContextStore.set({
    label: eventSummary,
    source: "calendar",
    prompt:
      `Tell me everything useful about "${eventSummary}" — ` +
      `preparation I should do, what to bring, timing tips, and any relevant local info for Tampa, FL.`,
  });
}

// ── Briefing / Index tab ──────────────────────────────────────────────────────

export function ctxDailyBriefing(todayEvents: string[], pending: number) {
  const evList = todayEvents.length ? todayEvents.slice(0, 3).join(", ") : "no events";
  ChatContextStore.set({
    label: "Daily Briefing",
    source: "briefing",
    prompt:
      `Give me a smart briefing for today. Events: ${evList}. Pending missions: ${pending}. ` +
      `What should I prioritise, watch out for, or prepare for today? ` +
      `Be concise — bullet points, max 5 items.`,
  });
}

export function ctxQuickAction(action: string, context: string) {
  ChatContextStore.set({ label: action, source: "briefing", prompt: context });
}

// ── Missions tab ──────────────────────────────────────────────────────────────

export function ctxMissionCreate(pendingCount: number, overdueCount: number) {
  ChatContextStore.set({
    label: "Create Mission",
    source: "missions",
    prompt:
      `Help me create a new mission. I currently have ${pendingCount} active and ${overdueCount} overdue. ` +
      `Ask me what I want to accomplish, then format it as a clear mission with title, ` +
      `due date, and 2–3 action steps.`,
  });
}

export function ctxMissionInsight(insightText: string) {
  ChatContextStore.set({
    label: "Mission Insight",
    source: "missions",
    prompt:
      `I want to discuss this pattern: "${insightText}". ` +
      `Give me 3 concrete, actionable steps I can take this week to improve this — ` +
      `specific to my family schedule in Tampa.`,
  });
}

// ── Engine / Settings tab ─────────────────────────────────────────────────────

export function ctxEngineInsight(insightText: string) {
  ChatContextStore.set({
    label: "Pattern Insight",
    source: "engine",
    prompt:
      `I want to act on this behavioural pattern: "${insightText}". ` +
      `Build me a practical weekly plan to improve this, ` +
      `tailored to my family schedule and existing routines.`,
  });
}

export function ctxUpdateIdentity() {
  ChatContextStore.set({
    label: "Update Preferences",
    source: "engine",
    prompt:
      `I want to update my household preferences. Walk me through these one at a time: ` +
      `(1) Cuisine & dining preferences, (2) Weekend activity style, ` +
      `(3) Interests & hobbies, (4) Family routine. ` +
      `For each, tell me what you currently have on file, then ask what I'd like to change.`,
  });
}

export function ctxPreferenceDrill(preferencePill: string) {
  ChatContextStore.set({
    label: `About: ${preferencePill}`,
    source: "engine",
    prompt:
      `My household profile includes "${preferencePill}" as a preference. ` +
      `Based on this, give me 3 practical suggestions or ideas tailored specifically to this — ` +
      `could be meal ideas, activities, products to try, or routines to build.`,
  });
}
