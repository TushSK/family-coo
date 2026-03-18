// app/context/IdeasStore.ts
//
// ── Storage architecture ───────────────────────────────────────────────────────
//
//   PRIMARY  →  Supabase (user_memory.ideas)
//               Survives cache clears, reinstalls, browser changes, new devices.
//               Written on every mutation (add / remove / convert).
//
//   CACHE    →  AsyncStorage (fcoo_ideas_v1)
//               Instant reads with no network round-trip.
//               Kept in sync after every mutation.
//               Seeded from Supabase on first load.
//
// Read flow:
//   1. Return AsyncStorage immediately (instant UI).
//   2. In background, fetch from Supabase.
//   3. Merge (Supabase wins on conflicts), deduplicate by id.
//   4. Save merged list back to AsyncStorage.
//   5. Return merged list to caller.
//
// Write flow:
//   1. Write to AsyncStorage first (instant local feedback).
//   2. POST full array to Supabase (durable, device-independent).
//
// ──────────────────────────────────────────────────────────────────────────────

import AsyncStorage from "@react-native-async-storage/async-storage";
import { API_BASE, USER_ID } from "../constants/config";

const LOCAL_KEY = "fcoo_ideas_v1";

export interface Idea {
  id:        string;
  text:      string;
  converted: boolean;
  createdAt: string;
}

// ── Local cache helpers ───────────────────────────────────────────────────────

async function _localRead(): Promise<Idea[]> {
  try {
    const raw = await AsyncStorage.getItem(LOCAL_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

async function _localWrite(ideas: Idea[]): Promise<void> {
  try {
    await AsyncStorage.setItem(LOCAL_KEY, JSON.stringify(ideas));
  } catch {}
}

// ── Supabase helpers ──────────────────────────────────────────────────────────

async function _remoteRead(): Promise<Idea[] | null> {
  try {
    const res = await fetch(`${API_BASE}/api/memory/ideas?user_id=${encodeURIComponent(USER_ID)}`);
    if (!res.ok) return null;
    const data = await res.json();
    return Array.isArray(data.ideas) ? data.ideas : null;
  } catch { return null; }
}

async function _remoteWrite(ideas: Idea[]): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/memory/ideas`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ user_id: USER_ID, ideas }),
    });
  } catch {}
}

// ── Merge: deduplicate by id, Supabase wins on conflict ──────────────────────
function _merge(local: Idea[], remote: Idea[]): Idea[] {
  const map = new Map<string, Idea>();
  // local first, then remote overwrites — remote is source of truth
  for (const idea of local)  map.set(idea.id, idea);
  for (const idea of remote) map.set(idea.id, idea);
  return Array.from(map.values()).sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * getIdeas()
 * Returns ideas from local cache immediately, then reconciles with Supabase
 * in the background. Call sites that need the freshest data should await
 * the returned promise — it resolves after the reconciliation completes.
 */
export async function getIdeas(): Promise<Idea[]> {
  const local  = await _localRead();
  const remote = await _remoteRead();

  if (remote === null) {
    // Supabase unreachable — return local cache as-is
    return local;
  }

  const merged = _merge(local, remote);

  // Keep local cache up to date with server state
  if (JSON.stringify(merged) !== JSON.stringify(local)) {
    await _localWrite(merged);
  }

  return merged;
}

/**
 * addIdea(text)
 * Adds a new idea to both local cache and Supabase.
 * Returns the updated list immediately after local write so the UI is instant.
 */
export async function addIdea(text: string): Promise<Idea[]> {
  const existing = await _localRead();

  const newIdea: Idea = {
    id:        Date.now().toString(),
    text:      text.trim(),
    converted: false,
    createdAt: new Date().toISOString(),
  };

  const updated = [newIdea, ...existing];

  // 1. Write locally first → instant UI feedback
  await _localWrite(updated);

  // 2. Persist to Supabase → durable, cross-device
  _remoteWrite(updated).catch(() => {});

  return updated;
}

/**
 * convertIdea(id)
 * Marks an idea as converted (→ Mission). Syncs both stores.
 */
export async function convertIdea(id: string): Promise<Idea[]> {
  const ideas   = await _localRead();
  const updated = ideas.map(i => i.id === id ? { ...i, converted: true } : i);
  await _localWrite(updated);
  _remoteWrite(updated).catch(() => {});
  return updated;
}

/**
 * removeIdea(id)
 * Removes an idea permanently. Syncs both stores.
 */
export async function removeIdea(id: string): Promise<Idea[]> {
  const ideas   = await _localRead();
  const updated = ideas.filter(i => i.id !== id);
  await _localWrite(updated);
  _remoteWrite(updated).catch(() => {});
  return updated;
}

/**
 * getPendingCount()
 * Fast local-only count for badge displays.
 */
export async function getPendingCount(): Promise<number> {
  const ideas = await _localRead();
  return ideas.filter(i => !i.converted).length;
}

/**
 * syncFromRemote()
 * Force a full pull from Supabase → overwrites local cache.
 * Call this on app launch or when switching devices.
 */
export async function syncFromRemote(): Promise<Idea[]> {
  const remote = await _remoteRead();
  if (remote === null) return _localRead();
  await _localWrite(remote);
  return remote;
}
