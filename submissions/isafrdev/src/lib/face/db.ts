import { openDB, type IDBPDatabase } from "idb";
import { supabase } from "@/lib/supabase";
import type { Person, PlaylistItem, RecognitionLog } from "./types";
import { pushPlaylistRemote } from "./playlistSync";
import { loadKioskPrefs } from "./kioskPrefs";

export const PLAYLIST_LS_KEY = "visiongate:playlist";
export const PLAYLIST_DAY_LS_KEY = "visiongate:playlist_day";
/** Emitted when playlist saved; `detail.key` identifies which playlist bucket changed. */
export const PLAYLIST_CHANGE_EVENT = "visiongate:playlist-change";

export function loadPlaylistFromStorage(storageKey = PLAYLIST_LS_KEY): PlaylistItem[] {
  try {
    const raw = localStorage.getItem(storageKey);
    if (raw) return JSON.parse(raw) as PlaylistItem[];
  } catch {
    /* ignore */
  }
  return [];
}

export function writePlaylistLocal(items: PlaylistItem[], storageKey = PLAYLIST_LS_KEY) {
  localStorage.setItem(storageKey, JSON.stringify(items));
  window.dispatchEvent(new CustomEvent(PLAYLIST_CHANGE_EVENT, { detail: { key: storageKey } }));
}

export function persistPlaylist(items: PlaylistItem[], storageKey = PLAYLIST_LS_KEY) {
  writePlaylistLocal(items, storageKey);
  if (storageKey === PLAYLIST_LS_KEY && loadKioskPrefs().cloudPlaylistSync) {
    void pushPlaylistRemote(items);
  }
}

// ─── IndexedDB (local cache & heavy blob data) ────────────────────────
const DB_NAME = "smart-office-db";
const DB_VERSION = 3;

let dbPromise: Promise<IDBPDatabase> | null = null;

function getDB() {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains("people")) db.createObjectStore("people", { keyPath: "id" });
        if (!db.objectStoreNames.contains("logs")) {
          const s = db.createObjectStore("logs", { keyPath: "id" });
          s.createIndex("by-time", "timestamp");
        }
        if (!db.objectStoreNames.contains("files")) db.createObjectStore("files", { keyPath: "id" });
      },
    });
  }
  return dbPromise;
}

// ─── PEOPLE ────────────────────────────────────────────────────────────

export async function listPeople(): Promise<Person[]> {
  try {
    const { data, error } = await supabase
      .from("people")
      .select("*")
      .order("created_at", { ascending: false });
    if (!error && data && data.length > 0) {
      // Map snake_case → camelCase
      const mapped = data.map(mapPersonFromDB);
      // Sync to local cache
      const db = await getDB();
      for (const p of mapped) await db.put("people", p);
      return mapped;
    }
  } catch (e) {
    console.warn("[DB] Supabase unreachable, using local cache", e);
  }
  // Fallback to IndexedDB
  const db = await getDB();
  const all = (await db.getAll("people")) as Person[];
  return all.sort((a, b) => b.createdAt - a.createdAt);
}

export async function savePerson(p: Person) {
  // Save locally first (instant)
  const db = await getDB();
  await db.put("people", p);
  // Then sync to Supabase
  try {
    const row = mapPersonToDB(p);
    await supabase.from("people").upsert(row, { onConflict: "id" });
  } catch (e) {
    console.warn("[DB] Supabase sync failed for person:", e);
  }
}

export const addPerson = savePerson; // alias

export async function deletePerson(id: string) {
  const db = await getDB();
  await db.delete("people", id);
  try {
    await supabase.from("people").delete().eq("id", id);
  } catch (e) {
    console.warn("[DB] Supabase delete failed:", e);
  }
}

// ─── LOGS ──────────────────────────────────────────────────────────────

export async function addLog(log: RecognitionLog) {
  const db = await getDB();
  await db.put("logs", log);
  try {
    await supabase.from("recognition_logs").upsert({
      id: log.id,
      person_id: log.personId,
      name: log.name,
      confidence: log.confidence,
      timestamp: log.timestamp,
      expression: log.expression,
      snapshot: log.snapshot?.slice(0, 500) || null,
    });
  } catch (e) {
    console.warn("[DB] Supabase log insert failed:", e);
  }
}

export async function listLogs(limit = 200): Promise<RecognitionLog[]> {
  try {
    const { data, error } = await supabase
      .from("recognition_logs")
      .select("*")
      .order("timestamp", { ascending: false })
      .limit(limit);
    if (!error && data && data.length > 0) {
      return data.map((r: any) => ({
        id: r.id,
        personId: r.person_id,
        name: r.name,
        confidence: r.confidence,
        timestamp: r.timestamp,
        expression: r.expression,
        snapshot: r.snapshot,
      }));
    }
  } catch (e) {
    console.warn("[DB] Supabase logs fetch failed, using local:", e);
  }
  const db = await getDB();
  const tx = db.transaction("logs");
  const idx = tx.store.index("by-time");
  const out: RecognitionLog[] = [];
  let cursor = await idx.openCursor(null, "prev");
  while (cursor && out.length < limit) {
    out.push(cursor.value as RecognitionLog);
    cursor = await cursor.continue();
  }
  return out;
}

export async function clearLogs() {
  const db = await getDB();
  await db.clear("logs");
  try {
    await supabase.from("recognition_logs").delete().not("id", "is", null);
  } catch (e) {
    console.warn("[DB] Supabase clearLogs failed:", e);
  }
}

// ─── FILES (local only – blobs stay in IndexedDB) ──────────────────────

export async function saveFile(id: string, file: Blob | File) {
  const db = await getDB();
  await db.put("files", { id, data: file });
}

export async function getFile(id: string): Promise<Blob | null> {
  const db = await getDB();
  const res = await db.get("files", id);
  return res ? res.data : null;
}

export async function deleteFile(id: string) {
  const db = await getDB();
  await db.delete("files", id);
}

// ─── Mappers ───────────────────────────────────────────────────────────

function mapPersonFromDB(row: any): Person {
  return {
    id: row.id,
    name: row.name,
    role: row.role || "",
    language: row.language || "uz",
    customMessage: row.custom_message || undefined,
    birthday: row.birthday || undefined,
    cooldownMinutes: row.cooldown_minutes ?? 10,
    greetingMode: row.greeting_mode || "cooldown",
    voiceEnabled: row.voice_enabled ?? true,
    embeddings: row.embeddings || [],
    avatar: row.avatar || undefined,
    isBlacklisted: row.is_blacklisted ?? false,
    createdAt: row.created_at ? new Date(row.created_at).getTime() : Date.now(),
  };
}

function mapPersonToDB(p: Person) {
  return {
    id: p.id,
    name: p.name,
    role: p.role,
    language: p.language,
    custom_message: p.customMessage || null,
    birthday: p.birthday || null,
    cooldown_minutes: p.cooldownMinutes,
    greeting_mode: p.greetingMode,
    voice_enabled: p.voiceEnabled,
    embeddings: p.embeddings,
    avatar: p.avatar || null,
    is_blacklisted: p.isBlacklisted ?? false,
    created_at: new Date(p.createdAt).toISOString(),
  };
}
