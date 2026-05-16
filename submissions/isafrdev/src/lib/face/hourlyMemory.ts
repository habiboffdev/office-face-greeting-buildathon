import type { Language } from "@/lib/face/types";

const LS = "visiongate:hourly_mem_v1";

export type HourlyMem = {
  lastAt: number;
  transcript: string;
};

function readAll(): Record<string, HourlyMem> {
  try {
    const raw = localStorage.getItem(LS);
    if (!raw) return {};
    return JSON.parse(raw) as Record<string, HourlyMem>;
  } catch {
    return {};
  }
}

function writeAll(m: Record<string, HourlyMem>) {
  localStorage.setItem(LS, JSON.stringify(m));
}

export function getHourlyMem(personId: string): HourlyMem | null {
  return readAll()[personId] ?? null;
}

/** Minimal pause between mood/plan prompts (default 30 minutes). */
export const HOURLY_CHECK_INTERVAL_MS = 30 * 60 * 1000;

/** ≥ interval since last prompt */
export function shouldAskHourlyCheck(personId: string): boolean {
  const mem = getHourlyMem(personId);
  if (!mem) return true;
  return Date.now() - mem.lastAt >= HOURLY_CHECK_INTERVAL_MS;
}

export function saveHourlyResponse(personId: string, transcript: string) {
  const all = readAll();
  all[personId] = {
    lastAt: Date.now(),
    transcript: transcript.trim().slice(0, 280),
  };
  writeAll(all);
}

export function buildHourlyQuestion(name: string, lang: Language, priorNote: string | null): string {
  const shortPrior = priorNote?.length ? priorNote.trim().slice(0, 120) : "";

  if (lang === "en") {
    if (shortPrior) {
      return `${name}, about half an hour ago you shared: "${shortPrior}". How are you feeling now, and what's on your agenda?`;
    }
    return `${name}, quick check-in every thirty minutes — how do you feel, and what's your main plan today?`;
  }

  if (lang === "ru") {
    if (shortPrior) {
      return `${name}, совсем недавно вы говорили: «${shortPrior}». Как настроение и какие задачи на сегодня?`;
    }
    return `${name}, каждые полчаса спрашиваю: как ваше состояние и план на сегодня?`;
  }

  if (shortPrior) {
    return `${name}, yarim soat oldin aytdingiz: "${shortPrior}". Endi kayfiyatingiz va bugungi rejangiz qanday?`;
  }
  return `${name}, har o'ttiz minutda so‘rayman: ahvolingiz yaxshimi va bugungi asosiy rejangiz nima?`;
}
