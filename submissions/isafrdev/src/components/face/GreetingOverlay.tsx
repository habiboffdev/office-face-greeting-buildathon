import { AnimatePresence, motion } from "framer-motion";
import { ShieldCheck, Smile, Fingerprint, Users, Cake, Sparkles, Gift } from "lucide-react";
import type { Language, Person } from "@/lib/face/types";

export type GreetingResultRow = { person: Person; confidence: number; expression: string };

function birthdayCopy(lang: Language, name: string) {
  const n = name.trim();
  if (lang === "en") {
    return {
      title: "HAPPY BIRTHDAY!",
      lead: `This day is all about you, ${n}!`,
      sub: "Wishing you a year of boundless joy and success.",
    };
  }
  if (lang === "ru") {
    return {
      title: "С днём рождения!",
      lead: `${n}, этот день — ваш!`,
      sub: "Здоровья, улыбок и ярких впечатлений.",
    };
  }
  return {
    title: "Tugilgan kuningiz bilan!",
    lead: `${n}, bugun sizning bayramingiz`,
    sub: "Soglik, omad va cheksiz tabassum tilaymiz.",
  };
}

function BirthdaySideRibbon({ person, lang: overrideLang }: { person: Person; lang?: Language }) {
  const lang = overrideLang || person.language || "uz";
  const copy = birthdayCopy(lang, person.name);

  return (
    <motion.aside
      initial={{ x: 120, opacity: 0, rotate: 2 }}
      animate={{ x: 0, opacity: 1, rotate: 0 }}
      exit={{ x: 120, opacity: 0 }}
      transition={{ type: "spring", stiffness: 280, damping: 26 }}
      className="pointer-events-none relative order-1 w-full max-w-[min(100%,18rem)] shrink-0 md:order-2"
    >
      <div className="relative overflow-hidden rounded-[2rem] border border-amber-400/35 bg-gradient-to-br from-amber-500/25 via-primary/20 to-fuchsia-600/20 px-6 py-8 shadow-[0_0_60px_-12px_rgba(251,191,36,0.45)] backdrop-blur-md">
        <div className="pointer-events-none absolute -right-6 -top-6 h-28 w-28 rounded-full bg-amber-300/30 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-8 left-0 h-24 w-24 rounded-full bg-fuchsia-500/25 blur-2xl" />

        <div className="relative flex flex-col items-center text-center gap-3">
          <div className="flex items-center justify-center gap-2 rounded-full bg-black/25 px-4 py-1.5 text-[9px] font-mono font-bold uppercase tracking-[0.35em] text-amber-100 border border-amber-400/30">
            <Sparkles className="h-3.5 w-3.5 text-amber-300" /> Tabrik
          </div>
          <div className="relative">
            <Cake className="mx-auto h-14 w-14 text-amber-200 drop-shadow-[0_0_18px_rgba(251,191,36,0.6)]" />
            <Gift className="absolute -right-2 -top-1 h-7 w-7 text-fuchsia-300/90 drop-shadow-md" />
          </div>
          <h3 className="font-display text-xl md:text-2xl font-black uppercase tracking-tight text-white drop-shadow-md leading-tight">
            {copy.title}
          </h3>
          <p className="text-sm font-semibold text-amber-50/95 leading-snug">{copy.lead}</p>
          <p className="text-[11px] text-white/75 leading-relaxed font-medium">{copy.sub}</p>
          <div className="mt-2 flex gap-1 justify-center flex-wrap">
            {["✨", "🎈", "🎉", "⭐"].map((e, i) => (
              <motion.span
                key={i}
                className="text-lg opacity-90"
                animate={{ y: [0, -4, 0] }}
                transition={{ duration: 2.2, repeat: Infinity, delay: i * 0.15 }}
              >
                {e}
              </motion.span>
            ))}
          </div>
        </div>
      </div>
    </motion.aside>
  );
}

export function GreetingOverlay({
  results,
  spokenText,
  birthdayHighlight,
  language,
}: {
  results: GreetingResultRow[] | null;
  spokenText?: string | null;
  /** Tug‘ilgan kuni bo‘lsa — markaz kartadan tashqari yon tabrik lentasi */
  birthdayHighlight?: boolean;
  language?: Language;
}) {
  if (!results || results.length === 0) return null;

  const main = results[0];
  const others = results.slice(1);
  const isHappy = main.expression === "happy";
  const finalLang = language || main.person.language;

  return (
    <AnimatePresence>
      <motion.div
        key={results.map((r) => r.person.id).join("-")}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="pointer-events-none absolute inset-0 z-30 flex items-center justify-center p-4 md:p-8 bg-black/10 backdrop-blur-[2px]"
      >
        <div className="relative flex w-full max-w-5xl flex-col items-center justify-center gap-6 md:flex-row md:items-center md:justify-center md:gap-10">
          {birthdayHighlight && <BirthdaySideRibbon person={main.person} lang={finalLang} />}

          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 40 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ type: "spring", stiffness: 260, damping: 20 }}
            className="glass-strong pointer-events-auto relative order-2 w-full max-w-lg rounded-[2.5rem] border border-primary/20 bg-card p-1 shadow-glow overflow-hidden md:order-1"
          >
            <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-primary/10 to-transparent" />

            <div className="relative p-8">
              <div className="flex flex-wrap items-center gap-3 mb-6">
                <div className="flex items-center gap-2 px-3 py-1.5 bg-primary/20 border border-primary/30 rounded-lg text-[10px] font-bold text-primary uppercase tracking-wider">
                  <ShieldCheck className="h-3 w-3" /> Identified
                </div>
                <div
                  className={`flex items-center gap-2 px-3 py-1.5 border rounded-lg text-[10px] font-bold uppercase tracking-wider ${
                    isHappy
                      ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-500"
                      : "bg-primary/5 border-border text-muted-foreground"
                  }`}
                >
                  <Smile className="h-3 w-3" /> {main.expression.toUpperCase()}
                </div>
                {others.length > 0 && (
                  <div className="flex items-center gap-1.5 px-3 py-1.5 bg-accent/10 border border-accent/25 rounded-lg text-[10px] font-bold text-accent uppercase tracking-wider">
                    <Users className="h-3 w-3" /> +{others.length} kadr
                  </div>
                )}
              </div>

              {others.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-6">
                  {others.map((r) => (
                    <div
                      key={r.person.id}
                      className="flex items-center gap-2 pl-1 pr-3 py-1 rounded-full bg-background/80 border border-border text-[10px] font-semibold"
                    >
                      <div className="h-7 w-7 rounded-full overflow-hidden border border-primary/20 bg-muted">
                        {r.person.avatar ? (
                          <img src={r.person.avatar} alt="" className="h-full w-full object-cover" />
                        ) : (
                          <div className="h-full w-full flex items-center justify-center text-muted-foreground">
                            <Fingerprint className="h-3.5 w-3.5" />
                          </div>
                        )}
                      </div>
                      <span className="truncate max-w-[8rem]">{r.person.name}</span>
                      <span className="text-primary/70 tabular-nums">{(r.confidence * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-6 mb-8">
                <div className="h-20 w-20 rounded-2xl border-2 border-primary/30 bg-background overflow-hidden shadow-xl ring-4 ring-background flex-shrink-0">
                  {main.person.avatar ? (
                    <img src={main.person.avatar} alt={main.person.name} className="h-full w-full object-cover" />
                  ) : (
                    <div className="h-full w-full flex items-center justify-center text-primary/30">
                      <Fingerprint className="h-10 w-10" />
                    </div>
                  )}
                </div>
                <div className="min-w-0">
                  <h2 className="font-display text-2xl font-bold text-foreground leading-tight tracking-tight truncate">
                    {main.person.name}
                  </h2>
                  <p className="text-primary font-bold text-[10px] mt-1 uppercase tracking-widest opacity-90 truncate">
                    {main.person.role || "Authorized Personnel"}
                  </p>
                </div>
              </div>

              <AnimatePresence mode="wait">
                {spokenText && (
                  <motion.div
                    key={spokenText.slice(0, 80)}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 10 }}
                    className="mb-8 p-6 rounded-2xl bg-primary/5 border border-primary/10 relative whitespace-pre-wrap"
                  >
                    <div className="absolute -top-2 left-6 px-2 bg-card text-[8px] font-mono font-bold text-primary uppercase tracking-widest">
                      AI_Message
                    </div>
                    <p className="text-sm font-medium leading-relaxed text-foreground/90 italic">"{spokenText}"</p>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="grid grid-cols-2 gap-6 border-t border-border pt-6">
                <div className="space-y-1">
                  <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest">Confidence</div>
                  <div className="text-xs font-bold text-primary tabular-nums">{(main.confidence * 100).toFixed(1)}%</div>
                </div>
                <div className="space-y-1">
                  <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest">Last Entry</div>
                  <div className="text-xs font-bold text-foreground tabular-nums">
                    {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
