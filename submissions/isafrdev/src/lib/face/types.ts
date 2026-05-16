export type Language = "uz" | "en" | "ru";
export type GreetingMode = "always" | "cooldown" | "once-per-day";

export interface Person {
  id: string;
  name: string;
  role: string;
  language: Language;
  customMessage?: string;
  birthday?: string; // YYYY-MM-DD
  cooldownMinutes: number;
  greetingMode: GreetingMode;
  voiceEnabled: boolean;
  embeddings: number[][]; // multiple captures (3 angles)
  avatar?: string; // dataURL of first capture
  isBlacklisted?: boolean;
  createdAt: number;
}

export interface RecognitionLog {
  id: string;
  personId: string | null; // null = unknown
  name: string;
  confidence: number; // 0..1 (1 - distance)
  timestamp: number;
  snapshot?: string;
  expression?: string;
}

export interface RecognitionEvent {
  results: {
    person: Person;
    confidence: number;
    expression: string;
  }[];
}

export type PlaylistItemType = "video" | "image" | "card" | "info";

export interface PlaylistItem {
  id: string;
  type: PlaylistItemType;
  url?: string;
  name?: string; // original file name
  title?: string;
  description?: string;
  duration?: number; // slide duration (ms): image / card / info; video uses playback until ended
  image?: string; // for cards
  /** Local JPEG data URL for admin / kiosk preview (not cloud-synced) */
  poster?: string;
}

/** Mood analytics aggregation */
export interface MoodEntry {
  personId: string;
  name: string;
  expression: string;
  timestamp: number;
}

/** Attendance summary per person per day */
export interface AttendanceRecord {
  personId: string;
  name: string;
  role: string;
  avatar?: string;
  date: string; // YYYY-MM-DD
  firstSeen: number; // epoch ms
  lastSeen: number;
  totalVisits: number;
  dominantMood: string;
}
