/** Kiosk / admin UX toggles persisted in localStorage */
export interface KioskPrefs {
  cloudPlaylistSync: boolean;
  /** Override autoplay mute when user accepts browser behavior */
  videoUnmuted: boolean;
  scheduleEnabled: boolean;
  dayStartHour: number;
  dayEndHour: number;
  /** Mood/plan prompt interval (~30 min) after greeting when speech enabled */
  hourlyCheckEnabled: boolean;
  /** Use `VITE_OPENAI_API_KEY` to phrase the hourly question (costs API usage) */
  hourlyUseOpenAI: boolean;
}

const LS_KIOSK_PREFS = "visiongate:kiosk_prefs";

export const DEFAULT_KIOSK_PREFS: KioskPrefs = {
  cloudPlaylistSync: false,
  videoUnmuted: false,
  scheduleEnabled: false,
  dayStartHour: 7,
  dayEndHour: 19,
  hourlyCheckEnabled: true,
  hourlyUseOpenAI: false,
};

export function loadKioskPrefs(): KioskPrefs {
  try {
    const raw = localStorage.getItem(LS_KIOSK_PREFS);
    if (!raw) return { ...DEFAULT_KIOSK_PREFS };
    return { ...DEFAULT_KIOSK_PREFS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_KIOSK_PREFS };
  }
}

export const KIOSK_PREFS_CHANGE_EVENT = "visiongate:kiosk-prefs-change";

export function saveKioskPrefs(partial: Partial<KioskPrefs>): KioskPrefs {
  const merged = { ...loadKioskPrefs(), ...partial };
  localStorage.setItem(LS_KIOSK_PREFS, JSON.stringify(merged));
  window.dispatchEvent(new Event(KIOSK_PREFS_CHANGE_EVENT));
  return merged;
}

/** Hour `[0–23)` inclusive start, exclusive end: `[dayStartHour, dayEndHour)` unless overnight. */
export function isInScheduledDayWindow(dayStartHour: number, dayEndHour: number): boolean {
  const h = new Date().getHours();
  if (dayStartHour === dayEndHour) return false;
  if (dayStartHour < dayEndHour) {
    return h >= dayStartHour && h < dayEndHour;
  }
  return h >= dayStartHour || h < dayEndHour;
}
