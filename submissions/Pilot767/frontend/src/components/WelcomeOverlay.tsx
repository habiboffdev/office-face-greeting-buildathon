import { useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

export interface WelcomeContent {
  title: string;
  subtitle: string;
  isVip?: boolean;
  isBirthday?: boolean;
  isFounder?: boolean;
  founderImageUrl?: string;
  /** Asoschi: UTC kun bo‘yicha bugungi tashriflar (badge uchun) */
  founderVisitsToday?: number;
  /** VIP: bugungi tashrif — badge */
  visitsToday?: number;
  /** Tanlangan inson (dublikatni tekshirish) */
  personId?: number;
  /** Har bir welcome voqeasi uchun noyob (navbat + animatsiya kaliti) */
  welcomeSeq: number;
}

interface Props {
  welcome: WelcomeContent | null;
}

const SPARKLE_CHARS = ['✨', '⭐', '✦', '·', '🌟'] as const;

function BirthdaySparkleField() {
  const particles = useMemo(
    () =>
      Array.from({ length: 36 }, (_, i) => ({
        id: i,
        left: `${((i * 19 + 31) * 11) % 88 + 6}%`,
        top: `${((i * 13 + 7) * 9) % 78 + 8}%`,
        delay: (i % 12) * 0.1,
        duration: 1.8 + (i % 8) * 0.35,
        char: SPARKLE_CHARS[i % SPARKLE_CHARS.length],
        drift: ((i % 7) - 3) * 0.8,
        size: i % 4 === 0 ? 'text-xl sm:text-2xl' : 'text-base sm:text-lg',
      })),
    [],
  );

  const slowStars = useMemo(
    () =>
      Array.from({ length: 12 }, (_, i) => ({
        id: `s-${i}`,
        left: `${(i * 53 + 17) % 80 + 10}%`,
        top: `${(i * 41 + 29) % 70 + 15}%`,
        delay: i * 0.25,
        scalePulse: 0.9 + (i % 4) * 0.08,
      })),
    [],
  );

  const confettiDots = useMemo(
    () =>
      Array.from({ length: 20 }, (_, i) => ({
        id: `d-${i}`,
        left: `${(i * 29) % 96 + 2}%`,
        size: 3 + (i % 4),
        delay: (i % 9) * 0.15,
        hue: i % 3 === 0 ? 'bg-pink-300' : i % 3 === 1 ? 'bg-amber-200' : 'bg-rose-200',
        drift: (i % 5) * 14 - 28,
        duration: 4 + (i % 3),
      })),
    [],
  );

  return (
    <div className="pointer-events-none absolute inset-0 z-[5] overflow-hidden">
      {particles.map((p) => (
        <motion.span
          key={p.id}
          className={`absolute select-none filter drop-shadow-[0_0_6px_rgba(251,182,233,0.9)] ${p.size}`}
          style={{ left: p.left, top: p.top }}
          initial={{ opacity: 0, scale: 0.4 }}
          animate={{
            opacity: [0.15, 0.95, 0.35, 0.9, 0.2],
            scale: [0.5, 1.2, 0.75, 1.05, 0.55],
            y: [0, -22, 8, -35, 5],
            x: [0, p.drift * 14, p.drift * -10, p.drift * 12, 0],
            rotate: [0, 18, -12, 10, 0],
          }}
          transition={{
            duration: p.duration,
            repeat: Infinity,
            delay: p.delay,
            ease: 'easeInOut',
          }}
        >
          {p.char}
        </motion.span>
      ))}
      {slowStars.map((s) => (
        <motion.span
          key={s.id}
          className="absolute text-2xl opacity-90 sm:text-3xl"
          style={{ left: s.left, top: s.top }}
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{
            opacity: [0.4, 1, 0.55, 1, 0.4],
            scale: [s.scalePulse, s.scalePulse + 0.25, s.scalePulse, s.scalePulse + 0.15, s.scalePulse],
          }}
          transition={{
            duration: 2.8,
            repeat: Infinity,
            delay: s.delay,
            ease: 'easeInOut',
          }}
        >
          ⭐
        </motion.span>
      ))}
      {/* Yumshoq “confetti” nuqtalari — pastdan yuqoriga */}
      {confettiDots.map((d) => (
        <motion.span
          key={d.id}
          className={`absolute rounded-full ${d.hue} opacity-70 shadow-[0_0_8px_currentColor]`}
          style={{
            left: d.left,
            top: '-4%',
            width: d.size,
            height: d.size,
          }}
          animate={{
            y: ['0vh', '110vh'],
            x: [0, d.drift],
            opacity: [0, 0.85, 0.6, 0],
            rotate: [0, 360],
          }}
          transition={{
            duration: d.duration,
            repeat: Infinity,
            delay: d.delay,
            ease: 'linear',
          }}
        />
      ))}
    </div>
  );
}

export function WelcomeOverlay({ welcome }: Props) {
  return (
    <AnimatePresence>
      {welcome && (
        <motion.div
          key={`welcome-${welcome.welcomeSeq}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-gradient-to-b from-black/30 via-transparent to-black/40"
        >
          {welcome.isBirthday && <BirthdaySparkleField />}

          <motion.div
            initial={{ opacity: 0, y: 48, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -24, scale: 0.95 }}
            transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
            className={`relative z-10 mx-6 w-full overflow-hidden rounded-[2rem] border px-8 py-12 text-center shadow-[0_24px_80px_rgba(0,0,0,0.55)] md:px-14 md:py-16 ${
              welcome.isFounder
                ? 'max-w-4xl border-amber-300/55 bg-gradient-to-br from-violet-950/95 via-slate-950/92 to-amber-950/55'
                : welcome.isBirthday
                  ? 'max-w-3xl border-pink-400/50 bg-gradient-to-br from-pink-950/90 via-slate-950/85 to-rose-950/80'
                  : welcome.isVip
                    ? 'max-w-3xl border-amber-400/50 bg-gradient-to-br from-amber-950/90 via-slate-950/85 to-orange-950/80'
                    : 'max-w-3xl border-white/15 bg-gradient-to-br from-slate-950/90 via-slate-900/80 to-orange-950/70'
            } backdrop-blur-2xl`}
          >
            {welcome.isBirthday && (
              <>
                <motion.div
                  className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(244,114,182,0.22),transparent_55%)]"
                  animate={{ opacity: [0.5, 0.85, 0.5] }}
                  transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                />
                <motion.div
                  className="pointer-events-none absolute -right-12 -top-12 h-48 w-48 rounded-full bg-pink-400/25 blur-3xl"
                  animate={{ scale: [1, 1.15, 1], opacity: [0.35, 0.6, 0.35] }}
                  transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
                />
                <motion.div
                  className="pointer-events-none absolute -bottom-8 -left-8 h-40 w-40 rounded-full bg-amber-300/15 blur-3xl"
                  animate={{ scale: [1, 1.12, 1], opacity: [0.25, 0.45, 0.25] }}
                  transition={{ duration: 2.8, repeat: Infinity, ease: 'easeInOut', delay: 0.4 }}
                />
              </>
            )}

            <div className="pointer-events-none absolute -left-20 -top-20 h-56 w-56 rounded-full bg-orange-500/20 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-16 -right-16 h-48 w-48 rounded-full bg-cyan-500/15 blur-3xl" />

            <div className="relative">
              <motion.div
                animate={
                  welcome.isBirthday
                    ? { scale: [1, 1.06, 1], rotate: [0, -4, 4, 0] }
                    : undefined
                }
                transition={
                  welcome.isBirthday
                    ? { duration: 2.2, repeat: Infinity, ease: 'easeInOut' }
                    : undefined
                }
                className="mb-6 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-5 py-2"
              >
                <span
                  className={`flex h-9 w-9 items-center justify-center rounded-lg text-sm font-black text-white shadow-lg ${
                    welcome.isFounder
                      ? 'bg-gradient-to-br from-amber-400 to-violet-600'
                      : welcome.isBirthday
                        ? 'bg-gradient-to-br from-pink-500 to-rose-500'
                        : welcome.isVip
                          ? 'bg-gradient-to-br from-amber-500 to-yellow-600'
                          : 'bg-gradient-to-br from-orange-500 to-orange-600'
                  }`}
                >
                  {welcome.isFounder ? '★' : welcome.isBirthday ? '🎂' : welcome.isVip ? '✦' : 'R'}
                </span>
                <span className="text-sm font-semibold tracking-wide text-white/90">
                  {welcome.isFounder
                    ? 'Asoschi'
                    : welcome.isBirthday
                      ? "Tug'ilgan kun"
                      : welcome.isVip
                        ? 'VIP mehmon'
                        : 'Rocus'}
                </span>
              </motion.div>
              {(() => {
                const n = welcome.isFounder
                  ? welcome.founderVisitsToday
                  : welcome.isVip
                    ? welcome.visitsToday
                    : undefined;
                return n != null && n > 1 ? (
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.06, duration: 0.35 }}
                    className="-mt-2 mb-2 text-center text-xs font-semibold uppercase tracking-[0.2em] text-amber-200/85"
                  >
                    Bugungi {n}-tashrif
                  </motion.p>
                ) : null;
              })()}

              <div
                className={`mx-auto mb-6 h-px w-24 bg-gradient-to-r from-transparent to-transparent ${
                  welcome.isFounder
                    ? 'via-amber-300/90'
                    : welcome.isBirthday
                      ? 'via-pink-300/90'
                      : welcome.isVip
                        ? 'via-amber-400/85'
                        : 'via-orange-400/80'
                }`}
              />

              <div
                className={
                  welcome.isFounder && welcome.founderImageUrl
                    ? 'flex flex-col items-center gap-8 md:flex-row md:items-center md:text-left'
                    : ''
                }
              >
                {welcome.isFounder && welcome.founderImageUrl ? (
                  <motion.img
                    initial={{ opacity: 0, scale: 0.92 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.08, duration: 0.55 }}
                    src={welcome.founderImageUrl}
                    alt=""
                    className="mx-auto h-44 w-44 shrink-0 rounded-2xl object-cover shadow-[0_24px_70px_rgba(0,0,0,0.55)] ring-2 ring-amber-400/45 md:mx-0 md:h-52 md:w-52"
                  />
                ) : null}
                <div
                  className={
                    welcome.isFounder && welcome.founderImageUrl ? 'min-w-0 flex-1 text-center md:text-left' : ''
                  }
                >
              <motion.h1
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15, duration: 0.5 }}
                className={`text-4xl font-bold leading-tight tracking-tight drop-shadow-xl md:text-5xl ${
                  welcome.isBirthday
                    ? 'bg-gradient-to-br from-white via-pink-100 to-rose-200 bg-clip-text text-transparent'
                    : 'text-white'
                }`}
              >
                {welcome.title}
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.28, duration: 0.5 }}
                className={`mt-5 text-xl font-medium leading-snug md:text-2xl ${
                  welcome.isFounder
                    ? 'text-amber-100/95'
                    : welcome.isBirthday
                      ? 'text-pink-200/95'
                      : welcome.isVip
                        ? 'text-amber-200/95'
                        : 'text-orange-300'
                }`}
              >
                {welcome.subtitle}
              </motion.p>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
