import { supabase } from "@/lib/supabase";
import type { PlaylistItem } from "@/lib/face/types";

const REMOTE_KEY = "visiongate_playlist";

export type PlaylistCloudPayload = {
  v: 1;
  updatedAt: number;
  items: PlaylistItem[];
};

/** Posters/thumbnails not synced (too large); http + local IDs still sent. */
export function stripHeavyPlaylistFields(items: PlaylistItem[]): PlaylistItem[] {
  return items.map(({ poster: _p, ...rest }) => ({ ...rest }));
}

export async function pushPlaylistRemote(items: PlaylistItem[]): Promise<void> {
  const url = import.meta.env.VITE_SUPABASE_URL || "";
  if (!url) return;

  const payload: PlaylistCloudPayload = {
    v: 1,
    updatedAt: Date.now(),
    items: stripHeavyPlaylistFields(items),
  };

  const { error } = await supabase.from("settings").upsert(
    {
      key: REMOTE_KEY,
      value: JSON.stringify(payload),
      updated_at: new Date().toISOString(),
    },
    { onConflict: "key" },
  );

  if (error) console.warn("[playlistSync] push failed:", error.message);
}

export async function fetchPlaylistRemote(): Promise<PlaylistCloudPayload | null> {
  const url = import.meta.env.VITE_SUPABASE_URL || "";
  if (!url) return null;

  const { data, error } = await supabase.from("settings").select("value").eq("key", REMOTE_KEY).maybeSingle();

  if (error || !data?.value) return null;

  try {
    const parsed = JSON.parse(data.value) as PlaylistCloudPayload;
    if (!parsed.items || !Array.isArray(parsed.items)) return null;
    return parsed;
  } catch {
    return null;
  }
}
