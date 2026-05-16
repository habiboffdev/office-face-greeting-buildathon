import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Camera, Check, RotateCcw, X, Upload, Sparkles } from "lucide-react";
import * as faceapi from "face-api.js";
import { loadFaceModels, detectAndDescribe } from "@/lib/face/recognizer";
import { savePerson } from "@/lib/face/db";
import type { GreetingMode, Language, Person } from "@/lib/face/types";

const OPTIONAL_HINTS = [
  "Asosiy surat (majburiy)",
  "Ixtiyoriy: biroz chapga buriling — aniqlik yaxshilanadi",
  "Ixtiyoriy: biroz o'ngga buriling — aniqlik yaxshilanadi",
];

const MAX_ANGLES = 3;

/** Yuz qutisi atrofidan kvadrat avatar — kartochka/salomda chiroyli ko'rinish. */
function avatarDataUrlFromFaceBox(
  source: HTMLVideoElement | HTMLImageElement,
  box: { x: number; y: number; width: number; height: number },
  opts: { mirror: boolean; size?: number; jpeg?: number },
): string {
  const size = opts.size ?? 320;
  const margin = 0.5;
  const sw = source instanceof HTMLVideoElement ? source.videoWidth : source.width;
  const sh = source instanceof HTMLVideoElement ? source.videoHeight : source.height;
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  let side = Math.max(box.width, box.height) * (1 + margin);
  side = Math.min(side, Math.min(sw, sh));
  let sx = cx - side / 2;
  let sy = cy - side / 2;
  sx = Math.max(0, Math.min(sx, sw - side));
  sy = Math.max(0, Math.min(sy, sh - side));

  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";

  if (opts.mirror) {
    ctx.save();
    ctx.translate(size, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(source, sx, sy, side, side, 0, 0, size, size);
    ctx.restore();
  } else {
    ctx.drawImage(source, sx, sy, side, side, 0, 0, size, size);
  }
  return canvas.toDataURL("image/jpeg", opts.jpeg ?? 0.92);
}

export function EnrollDialog({
  open,
  onClose,
  onCreated,
  initialPerson,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  initialPerson?: Person;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [captures, setCaptures] = useState<{ embedding: number[]; snapshot: string }[]>([]);
  /** Majburiy 1 ta suratdan keyin qo'shimcha suratni to'xtatish (formaga e'tibor). */
  const [photoFinished, setPhotoFinished] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [language, setLanguage] = useState<Language>("uz");
  const [customMessage, setCustomMessage] = useState("");
  const [birthday, setBirthday] = useState("");
  const [cooldownMinutes, setCooldownMinutes] = useState(2);
  const [greetingMode, setGreetingMode] = useState<GreetingMode>("always");
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [isBlacklisted, setIsBlacklisted] = useState(false);

  useEffect(() => {
    if (initialPerson) {
      setName(initialPerson.name);
      setRole(initialPerson.role);
      setLanguage(initialPerson.language);
      setCustomMessage(initialPerson.customMessage || "");
      setBirthday(initialPerson.birthday || "");
      setCooldownMinutes(Math.max(1, initialPerson.cooldownMinutes));
      setGreetingMode(initialPerson.greetingMode);
      setVoiceEnabled(initialPerson.voiceEnabled);
      setIsBlacklisted(initialPerson.isBlacklisted || false);
      setCaptures([]);
      setPhotoFinished(false);
    } else {
      setName("");
      setRole("");
      setCustomMessage("");
      setBirthday("");
      setCaptures([]);
      setPhotoFinished(false);
      setLanguage("uz");
      setCooldownMinutes(2);
      setGreetingMode("always");
      setVoiceEnabled(true);
      setIsBlacklisted(false);
    }
  }, [initialPerson, open]);

  useEffect(() => {
    if (!open) return;
    let stream: MediaStream | null = null;
    (async () => {
      try {
        await loadFaceModels();
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          throw new Error("MediaDevices API mavjud emas");
        }
        try {
          stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
          });
        } catch {
          stream = await navigator.mediaDevices.getUserMedia({ video: true });
        }
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
      } catch (e) {
        setErr((e as Error).message);
      }
    })();
    return () => {
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [open]);

  const canCaptureMore = captures.length < MAX_ANGLES && !photoFinished;

  const capture = async () => {
    if (!videoRef.current || !canCaptureMore) return;
    setBusy(true);
    setErr(null);
    try {
      const det = await detectAndDescribe(videoRef.current);
      if (!det || !det[0]) {
        setErr("Yuz aniqlanmadi, qaytadan urining");
        return;
      }
      const box = det[0].detection.box;
      const snapshot = avatarDataUrlFromFaceBox(videoRef.current, box, { mirror: true });
      setCaptures((arr) => [...arr, { embedding: Array.from(det[0].descriptor), snapshot }]);
    } finally {
      setBusy(false);
    }
  };

  const resetPhotos = () => {
    setCaptures([]);
    setPhotoFinished(false);
  };

  const submit = async () => {
    if (!name.trim()) return;
    if (captures.length < 1 && !initialPerson) return;

    const p: Person = {
      id: initialPerson?.id || crypto.randomUUID(),
      name: name.trim(),
      role: role.trim(),
      language,
      customMessage: customMessage.trim() || undefined,
      birthday: birthday || undefined,
      cooldownMinutes: greetingMode === "cooldown" ? Math.max(1, cooldownMinutes) : cooldownMinutes,
      greetingMode,
      voiceEnabled,
      isBlacklisted,
      embeddings: captures.length > 0 ? captures.map((c) => c.embedding) : initialPerson?.embeddings || [],
      avatar: captures.length > 0 ? captures[0]?.snapshot : initialPerson?.avatar || "",
      createdAt: initialPerson?.createdAt || Date.now(),
    };
    await savePerson(p);
    onCreated();
    onClose();
  };

  if (!open) return null;

  const hintIndex = Math.min(captures.length, OPTIONAL_HINTS.length - 1);
  const hintText =
    photoFinished && captures.length >= 1
      ? "Yuz rasmi tayyor — kerak bo'lsa «Qayta» bilan yangilang."
      : OPTIONAL_HINTS[hintIndex];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="glass-strong relative w-full max-w-3xl overflow-hidden rounded-3xl shadow-2xl border border-white/10"
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 z-10 rounded-full p-2 text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="grid gap-0 md:grid-cols-2">
          <div className="relative bg-background/40 p-6 border-r border-white/5">
            <div className="mb-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              {initialPerson ? "Yuz / avatar yangilash" : "Yuz rasmi"}
            </div>
            <h3 className="font-display text-xl font-semibold leading-snug">{hintText}</h3>
            <p className="mt-2 text-[11px] text-muted-foreground leading-relaxed">
              <strong className="text-foreground">Bitta</strong> surat yoki yuklangan rasm kifoya. Yana 1–2 ta burchak tanishni mustahkamlaydi — majburiy emas.
            </p>

            <div className="relative mt-4 aspect-square overflow-hidden rounded-2xl bg-background border border-white/5 shadow-inner ring-1 ring-primary/10">
              <video ref={videoRef} muted playsInline className="h-full w-full -scale-x-100 object-cover" />
              <div className="pointer-events-none absolute inset-6 rounded-full border-2 border-dashed border-primary/50" />
              <div className="scan-line pointer-events-none absolute inset-0" />
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {captures.map((c, i) => (
                <img
                  key={i}
                  src={c.snapshot}
                  alt=""
                  className="h-14 w-14 rounded-xl object-cover ring-2 ring-primary/50 shadow-md"
                />
              ))}
              {!photoFinished &&
                Array.from({ length: MAX_ANGLES - captures.length }).map((_, i) => (
                  <div
                    key={i}
                    className="h-14 w-14 rounded-xl border border-dashed border-border bg-background/40 text-[9px] text-muted-foreground flex items-center justify-center text-center px-1 leading-tight"
                  >
                    {captures.length + i === 0 ? "majburiy" : "ixtiyoriy"}
                  </div>
                ))}
            </div>

            <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              {canCaptureMore && (
                <>
                  <label className="flex flex-1 min-w-[8rem] cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-primary/35 bg-primary/10 px-4 py-3 text-sm font-semibold text-primary transition hover:bg-primary/15">
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      disabled={busy}
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        e.target.value = "";
                        if (!file) return;
                        setBusy(true);
                        setErr(null);
                        try {
                          const img = await faceapi.bufferToImage(file);
                          const det = await detectAndDescribe(img);
                          if (!det || !det[0]) throw new Error("Rasmda aniq yuz topilmadi");
                          const box = det[0].detection.box;
                          const snapshot = avatarDataUrlFromFaceBox(img, box, { mirror: false });
                          setCaptures((prev) => {
                            if (prev.length >= MAX_ANGLES) return prev;
                            return [...prev, { embedding: Array.from(det[0].descriptor), snapshot }];
                          });
                        } catch (er) {
                          setErr((er as Error).message);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    />
                    <Upload className="h-4 w-4 shrink-0" /> Rasm yuklash
                  </label>
                  <button
                    type="button"
                    onClick={() => void capture()}
                    disabled={busy}
                    className="flex flex-1 min-w-[8rem] items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
                  >
                    <Camera className="h-4 w-4 shrink-0" /> {busy ? "Tahlil..." : "Kameradan surat"}
                  </button>
                </>
              )}
              {captures.length > 0 && !photoFinished && captures.length < MAX_ANGLES && (
                <button
                  type="button"
                  onClick={() => setPhotoFinished(true)}
                  className="flex-1 min-w-full sm:min-w-[10rem] rounded-xl border border-border px-4 py-3 text-xs font-bold uppercase tracking-wide text-muted-foreground hover:bg-muted/40 hover:text-foreground sm:flex-none"
                >
                  Shu yerda tugatdim ({captures.length}/{MAX_ANGLES})
                </button>
              )}
              {captures.length > 0 && (
                <button
                  type="button"
                  onClick={resetPhotos}
                  title="Qayta boshlash"
                  className="rounded-xl border border-border px-4 py-3 text-sm hover:bg-foreground/5"
                >
                  <RotateCcw className="h-4 w-4" />
                </button>
              )}
            </div>

            {captures.length >= MAX_ANGLES && (
              <p className="mt-2 text-[10px] font-mono text-muted-foreground">Maksimal {MAX_ANGLES} ta embedding saqlandi.</p>
            )}
            {err && <div className="mt-2 text-xs text-destructive">{err}</div>}
          </div>

          <div className="p-6">
            <h3 className="font-display text-xl font-semibold">
              {initialPerson ? "Ma'lumotlarni tahrirlash" : "Xodim ma'lumotlari"}
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Standart: salom <strong className="text-foreground">har safar</strong>. «Kutish vaqtini» faqat kerak bo'lsa yoqing.
            </p>

            <div className="mt-4 space-y-3 text-sm">
              <Field label="Ism-familiya *">
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input"
                  placeholder="Akmal Karimov"
                />
              </Field>
              <Field label="Lavozimi">
                <input
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="input"
                  placeholder="Senior Backend Developer"
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Muloqot tili">
                  <select value={language} onChange={(e) => setLanguage(e.target.value as Language)} className="input">
                    <option value="uz">O'zbek</option>
                    <option value="en">English</option>
                    <option value="ru">Русский</option>
                  </select>
                </Field>
                <Field label="Tug'ilgan kuni">
                  <input type="date" value={birthday} onChange={(e) => setBirthday(e.target.value)} className="input" />
                </Field>
              </div>
              <Field label="Maxsus xabar (ixtiyoriy)">
                <input
                  value={customMessage}
                  onChange={(e) => setCustomMessage(e.target.value)}
                  className="input"
                  placeholder="Xush kelibsiz!"
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Salomlashish tartibi">
                  <select
                    value={greetingMode}
                    onChange={(e) => setGreetingMode(e.target.value as GreetingMode)}
                    className="input"
                  >
                    <option value="always">Har safar (kutish yo'q)</option>
                    <option value="cooldown">Oraliq bilan (daqiqa)</option>
                    <option value="once-per-day">Kuniga bir marta</option>
                  </select>
                </Field>
                <Field label={`Oraliq (faqat yuqorida «Oraliq» bo'lsa)`}>
                  <input
                    type="number"
                    min={1}
                    max={1440}
                    disabled={greetingMode !== "cooldown"}
                    value={cooldownMinutes}
                    onChange={(e) => setCooldownMinutes(Number(e.target.value))}
                    className="input disabled:opacity-40"
                  />
                </Field>
              </div>
              <div className="flex flex-col gap-2 border-t border-white/5 pt-4 mt-2">
                <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={voiceEnabled}
                    onChange={(e) => setVoiceEnabled(e.target.checked)}
                    className="accent-primary"
                  />
                  Ovozli salomlashish yoqilgan
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer select-none text-destructive font-bold">
                  <input
                    type="checkbox"
                    checked={isBlacklisted}
                    onChange={(e) => setIsBlacklisted(e.target.checked)}
                    className="accent-destructive"
                  />
                  Qora ro'yxatga olish (Blacklist)
                </label>
              </div>
            </div>

            <button
              type="button"
              onClick={() => void submit()}
              disabled={!name.trim() || (captures.length < 1 && !initialPerson)}
              className="mt-5 w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground shadow-glow transition hover:opacity-90 disabled:opacity-40"
            >
              <Check className="mr-2 inline h-4 w-4" /> {initialPerson ? "O'zgarishlarni saqlash" : "Xodimni qo'shish"}
            </button>

            <p className="mt-4 text-[10px] text-muted-foreground leading-relaxed border-t border-white/5 pt-4">
              <span className="font-mono uppercase tracking-wider text-primary">G'oya:</span> kunlik davomat eksporti, xodim uchun QR tezkor
              profil, va departament bo'yicha filter — keyingi bosqichda qo'shish mumkin.
            </p>
          </div>
        </div>
      </motion.div>

      <style>{`
        .input { width: 100%; border-radius: 0.75rem; background: var(--input); border: 1px solid var(--border); padding: 0.55rem 0.75rem; color: inherit; outline: none; }
        .input:focus { border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-ring); }
      `}</style>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}
