import type { Language } from "./types";
import { speakElevenLabs } from "./elevenlabs";

/** Lotin o‘zbekcha va apostroflarni TTS uchun biroz yumshatish */
function normalizeSpeechText(text: string, lang: Language): string {
  let t = text.replace(/\s+/g, " ").trim();
  if (lang === "uz") {
    t = t.replace(/ʻ|ʼ|′|`/g, "'").replace(/'/g, " ");
  }
  return t;
}

function pickSpeechVoice(voices: SpeechSynthesisVoice[], lang: Language): SpeechSynthesisVoice | undefined {
  const list = [...voices].filter(Boolean);
  const sorted = [...list].sort((a, b) => Number(b.localService) - Number(a.localService));

  if (lang === "uz") {
    return (
      sorted.find((v) => /^uz/i.test(v.lang || "")) ||
      sorted.find((v) => /^tr/i.test(v.lang || "")) ||
      sorted.find((v) => /^ru/i.test(v.lang || "")) ||
      sorted.find((v) => /^en-US/i.test(v.lang || "")) ||
      sorted[0]
    );
  }
  if (lang === "ru") {
    return sorted.find((v) => /^ru/i.test(v.lang || "")) || sorted.find((v) => /^uk/i.test(v.lang || "")) || sorted[0];
  }
  return sorted.find((v) => /^en/i.test(v.lang || "")) || sorted[0];
}

function utteranceLangFallback(lang: Language, voice?: SpeechSynthesisVoice): string {
  if (voice?.lang) return voice.lang;
  if (lang === "uz") return "ru-RU";
  if (lang === "ru") return "ru-RU";
  return "en-US";
}

export function speak(text: string, lang: Language = "uz", onEnd?: () => void) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    onEnd?.();
    return;
  }

  const normalized = normalizeSpeechText(text, lang);

  const run = () => {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(normalized);
    const voices = window.speechSynthesis.getVoices();
    const voice = pickSpeechVoice(voices, lang);
    if (voice) utterance.voice = voice;
    utterance.lang = utteranceLangFallback(lang, voice);

    utterance.rate = lang === "uz" ? 0.86 : lang === "ru" ? 0.9 : 0.95;
    utterance.pitch = lang === "uz" ? 1 : 1;
    utterance.volume = 1;

    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      onEnd?.();
    };

    if (onEnd) {
      utterance.onend = finish;
      setTimeout(finish, Math.min(45_000, Math.max(2500, normalized.length * 120)));
    }

    window.speechSynthesis.speak(utterance);
  };

  if (window.speechSynthesis.getVoices().length === 0) {
    let ran = false;
    const once = () => {
      if (ran) return;
      ran = true;
      run();
    };
    window.speechSynthesis.addEventListener("voiceschanged", once, { once: true });
    setTimeout(once, 750);
    return;
  }
  run();
}

/** Wait for TTS to finish (ElevenLabs if key works, else browser speech). */
export async function speakAndWait(
  text: string,
  lang: Language = "uz",
  opts?: { elevenKey?: string },
): Promise<void> {
  const normalized = normalizeSpeechText(text, lang);
  if (opts?.elevenKey) {
    const ok = await speakElevenLabs(normalized, undefined, opts.elevenKey);
    if (ok) return;
  }
  const cap = Math.min(45_000, Math.max(3500, 110 * normalized.length));
  await new Promise<void>((resolve) => {
    speak(normalized, lang, resolve);
    setTimeout(resolve, cap);
  });
}

/** Tug‘ilgan kun uchun qisqa nutq (asosiy salomdan keyin alohida ijro). */
export function birthdaySpeechLine(name: string, lang: Language): string {
  const n = name.trim();
  if (lang === "en") {
    return `Amazing! ${n}, it's your special day! Happy birthday! We wish you an incredible year ahead filled with joy, success, and wonderful moments. Enjoy your day!`;
  }
  if (lang === "ru") {
    return `${n}, поздравляю с днём рождения! Этот день полностью ваш. Желаю огромного счастья, здоровья и море улыбок!`;
  }
  return `${n}, bugun sizning unutilmas bayramingiz! Tug'ilgan kuningiz bilan chin qalbimizdan tabriklaymiz. Sizga sihat-salomatlik, baxt va ulkan zafarlar tilaymiz!`;
}

export async function listen(lang: Language = "uz"): Promise<string> {
  return new Promise((resolve) => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      console.warn("Speech recognition not supported");
      resolve("");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang =
      lang === "uz" ? "uz-UZ" : lang === "ru" ? "ru-RU" : "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      resolve(transcript);
    };

    recognition.onerror = () => resolve("");
    recognition.onend = () => resolve("");

    try {
      recognition.start();
    } catch {
      resolve("");
    }
  });
}

/** Parses natural language for time (e.g. "30 minutdan keyin") and returns minutes */
export function parseTime(text: string): number | null {
  const normalized = text.toLowerCase();

  const patterns: Record<string, number> = {
    bir: 1,
    "1": 1,
    ikki: 2,
    "2": 2,
    uch: 3,
    "3": 3,
    "to'rt": 4,
    "4": 4,
    besh: 5,
    "5": 5,
    olti: 6,
    "6": 6,
    yetti: 7,
    "7": 7,
    sakkiz: 8,
    "8": 8,
    "to'qqiz": 9,
    "9": 9,
    "o'n": 10,
    on: 10,
    "10": 10,
    "o'n besh": 15,
    "on besh": 15,
    "15": 15,
    yigirma: 20,
    "20": 20,
    "o'ttiz": 30,
    ottiz: 30,
    "yarim soat": 30,
    "30": 30,
    qirq: 40,
    "40": 40,
    ellik: 50,
    "50": 50,
    oltmish: 60,
    "bir soat": 60,
    "60": 60,
  };

  for (const [key, val] of Object.entries(patterns)) {
    if (normalized.includes(key)) return val;
  }

  const match = normalized.match(/(\d+)/);
  if (match) return parseInt(match[1]);

  return null;
}
