import type { Language, Person } from "./types";

const HOUR_GREETING: Record<Language, (h: number) => string> = {
  uz: (h) => h < 12 ? "Xayrli tong" : h < 18 ? "Xayrli kun" : "Xayrli kech",
  en: (h) => h < 12 ? "Xayrli tong" : h < 18 ? "Xayrli kun" : "Xayrli kech",
  ru: (h) => h < 12 ? "Xayrli tong" : h < 18 ? "Xayrli kun" : "Xayrli kech",
};

const WELCOME_BACK: Record<Language, string> = {
  uz: "Xush kelibsiz",
  en: "Xush kelibsiz",
  ru: "Xush kelibsiz",
};

const BIRTHDAY: Record<Language, string> = {
  uz: "Tug'ilgan kuningiz bilan",
  en: "Tug'ilgan kuningiz bilan",
  ru: "Tug'ilgan kuningiz bilan",
};

export function isBirthday(p: Person) {
  if (!p.birthday) return false;
  const d = new Date();
  const [, m, day] = p.birthday.split("-");
  return Number(m) === d.getMonth() + 1 && Number(day) === d.getDate();
}

export function buildGreeting(p: Person) {
  const lang = p.language;
  const h = new Date().getHours();
  if (isBirthday(p)) {
    return { headline: `🎉 ${BIRTHDAY[lang]}, ${p.name}!`, sub: p.role };
  }
  if (p.customMessage?.trim()) {
    return { headline: `${HOUR_GREETING[lang](h)}, ${p.name}`, sub: p.customMessage };
  }
  return { headline: `${HOUR_GREETING[lang](h)}, ${p.name}`, sub: p.role || WELCOME_BACK[lang] };
}

export function speak(text: string, lang: Language) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang === "uz" ? "uz-UZ" : lang === "ru" ? "ru-RU" : "en-US";
    u.rate = 1; u.pitch = 1; u.volume = 0.9;
    window.speechSynthesis.speak(u);
  } catch {}
}
