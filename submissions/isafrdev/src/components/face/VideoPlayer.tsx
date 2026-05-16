import { useEffect, useRef, useState } from "react";
import type { PlaylistItem } from "@/lib/face/types";
import { motion, AnimatePresence } from "framer-motion";
import { getFile } from "@/lib/face/db";
import { SmartInfoCard } from "./SmartInfoCard";

const SAMPLE_ITEMS: PlaylistItem[] = [
  { id: "1", type: "video", url: "https://cdn.coverr.co/videos/coverr-aerial-view-of-a-modern-city-2633/1080p.mp4" },
  { id: "info", type: "info", duration: 15000 },
  { id: "2", type: "card", title: "Innovatsiya", description: "Yangi g'oyalar sari olg'a!", duration: 5000 },
  { id: "3", type: "video", url: "https://cdn.coverr.co/videos/coverr-typing-on-a-laptop-2633/1080p.mp4" },
];

const IMAGE_SLIDE_MS = 5000;
const CROSSFADE_SEC = 1.35;

type Props = {
  playlist: PlaylistItem[];
  /** Pause slideshow / video while overlays (e.g. greeting) are visible */
  paused?: boolean;
  /** Browser autoplay rules — keep muted unless operator explicitly allows sound */
  videoUnmuted?: boolean;
};

export function VideoPlayer({ playlist, paused = false, videoUnmuted = false }: Props) {
  const queue = playlist.length ? playlist : SAMPLE_ITEMS;
  const [idx, setIdx] = useState(0);
  const [errored, setErrored] = useState(false);
  const [resolvedUrl, setResolvedUrl] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const blobUrlRef = useRef<string | null>(null);
  const item = queue[idx] || queue[0];

  const next = () => {
    setIdx((i) => (i + 1) % queue.length);
    setErrored(false);
    setResolvedUrl(null);
  };

  // ── Resolve media URL (runs while paused so frame stays visible) ─────────
  useEffect(() => {
    if (!item) return;

    let cancelled = false;

    const setMediaUrl = (url: string) => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
      }
      blobUrlRef.current = url.startsWith("blob:") ? url : null;
      setResolvedUrl(url);
    };

    const run = async () => {
      setErrored(false);

      if (item.type !== "video" && item.type !== "image") {
        if (blobUrlRef.current) {
          URL.revokeObjectURL(blobUrlRef.current);
          blobUrlRef.current = null;
        }
        setResolvedUrl(null);
        return;
      }

      if (!item.url) return;

      if (item.url.startsWith("http")) {
        setMediaUrl(item.url);
        return;
      }

      const blob = await getFile(item.url);
      if (cancelled) return;
      if (blob) {
        const url = URL.createObjectURL(blob);
        setMediaUrl(url);
      } else {
        setErrored(true);
      }
    };

    void run();

    return () => {
      cancelled = true;
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [idx, queue, item?.id, item?.type, item?.url]);

  // ── Advance timers (paused = freeze slideshow) ────────────────────────────
  useEffect(() => {
    if (!item || paused) return;

    let slideTimer: ReturnType<typeof setTimeout> | undefined;

    const armImageAdvance = () => {
      slideTimer = setTimeout(next, item.duration ?? IMAGE_SLIDE_MS);
    };

    if (item.type === "info") {
      slideTimer = setTimeout(next, item.duration || 15000);
    } else if (item.type === "card") {
      slideTimer = setTimeout(next, item.duration || 5000);
    } else if (item.type === "image" && resolvedUrl && !errored) {
      armImageAdvance();
    } else if (item.type === "image" && errored) {
      slideTimer = setTimeout(next, 3000);
    } else if (item.type === "video" && errored) {
      slideTimer = setTimeout(next, 3000);
    }

    return () => {
      if (slideTimer !== undefined) clearTimeout(slideTimer);
    };
  }, [item, paused, resolvedUrl, errored, idx, queue]);

  // ── Video play/pause sync ─────────────────────────────────────────────────
  useEffect(() => {
    const v = videoRef.current;
    if (!v || item?.type !== "video" || !resolvedUrl) return;
    if (paused) {
      v.pause();
    } else {
      void v.play().catch(() => {});
    }
  }, [paused, resolvedUrl, item?.type]);

  if (!item) return <AmbientFallback />;

  const vidMuted = !videoUnmuted;

  return (
    <div className="absolute inset-0 overflow-hidden bg-background">
      <AnimatePresence mode="sync" initial={false}>
        {item.type === "video" ? (
          <motion.div
            key={item.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: CROSSFADE_SEC }}
            className="h-full w-full"
          >
            {resolvedUrl && !errored ? (
              <video
                ref={videoRef}
                src={resolvedUrl}
                autoPlay
                muted={vidMuted}
                playsInline
                onEnded={paused ? undefined : next}
                onError={() => setErrored(true)}
                className="h-full w-full object-cover"
              />
            ) : (
              <AmbientFallback />
            )}
          </motion.div>
        ) : item.type === "image" ? (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, scale: 1.04 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.02 }}
            transition={{ duration: CROSSFADE_SEC }}
            className="h-full w-full"
          >
            {resolvedUrl && !errored ? (
              <img src={resolvedUrl} className="h-full w-full object-cover" alt="" />
            ) : (
              <AmbientFallback />
            )}
          </motion.div>
        ) : item.type === "info" ? (
          <motion.div
            key={item.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: CROSSFADE_SEC }}
            className="h-full w-full"
          >
            <SmartInfoCard />
          </motion.div>
        ) : (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, scale: 1.04 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: CROSSFADE_SEC, ease: "easeOut" }}
            className="flex h-full w-full items-center justify-center bg-gradient-to-br from-background via-accent/5 to-primary/10 p-10"
          >
            <div className="glass-strong max-w-4xl rounded-[3rem] p-16 text-center shadow-2xl backdrop-blur-3xl">
              {item.image && (
                <img src={item.image} className="mx-auto mb-10 h-64 w-64 rounded-3xl object-cover shadow-xl" alt="" />
              )}
              <h2 className="font-display text-6xl font-bold tracking-tight text-primary md:text-8xl">
                {item.title}
              </h2>
              <p className="mt-8 text-2xl font-light leading-relaxed text-muted-foreground md:text-4xl">
                {item.description}
              </p>
              <div className="mt-12 flex justify-center gap-3">
                <div className="h-1.5 w-12 rounded-full bg-primary/20 overflow-hidden">
                  <motion.div
                    initial={{ x: "-100%" }}
                    animate={{ x: "0%" }}
                    transition={{ duration: (item.duration || 5000) / 1000, ease: "linear" }}
                    className="h-full w-full bg-primary"
                  />
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background/20 via-transparent to-background/50" />
    </div>
  );
}

function AmbientFallback() {
  return (
    <div className="grid-bg relative flex h-full w-full items-center justify-center overflow-hidden">
      <div className="absolute inset-0" style={{ background: "var(--gradient-aurora)" }} />
      <div className="absolute -left-40 top-1/4 h-96 w-96 animate-pulse rounded-full bg-primary/30 blur-3xl" />
      <div className="absolute -right-40 bottom-1/4 h-[28rem] w-[28rem] animate-pulse rounded-full bg-accent/30 blur-3xl" style={{ animationDelay: "1s" }} />
      <div className="relative text-center">
        <div className="font-display text-7xl font-bold tracking-tight text-primary drop-shadow-[0_0_30px_oklch(0.7_0.25_45_/_0.3)] md:text-9xl">
          VISIONGATE
        </div>
        <div className="mt-4 font-mono text-xs uppercase tracking-[0.4em] text-muted-foreground/60">
          AI Aqlli Qabulxona · Jonli · Mahalliy Neyrotarmoq
        </div>
      </div>
    </div>
  );
}
