import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { listPeople, addLog } from "@/lib/face/db";
import {
  loadFaceModels,
  detectAndDescribe,
  bestDistance,
  distanceToConfidence,
  MATCH_THRESHOLD,
} from "@/lib/face/recognizer";
import type { Person } from "@/lib/face/types";

interface Props {
  onRecognize: (results: { person: Person; confidence: number; expression: string }[]) => void;
  onUnknown: (descriptor: number[], snapshot?: string) => void;
  onClear: () => void;
  voiceEnabled: boolean;
}

const ABSENCE_FRAMES = 6;

export function RecognitionEngine({ onRecognize, onUnknown, onClear, voiceEnabled }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "denied" | "error">("idle");
  const [zoomSnapshot, setZoomSnapshot] = useState<string | null>(null);
  const [, setTick] = useState(0);

  const peopleRef = useRef<Person[]>([]);
  const lastGreetedAtRef = useRef<Map<string, number>>(new Map());
  const absenceRef = useRef(0);
  const lastUnknownLogRef = useRef(0);
  const runningRef = useRef(true);

  // Refresh people list periodically
  useEffect(() => {
    let mounted = true;
    const refresh = async () => {
      const ppl = await listPeople();
      if (mounted) {
        peopleRef.current = ppl;
        setTick((t) => t + 1);
      }
    };
    refresh();
    const id = setInterval(refresh, 5000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  // Start camera & detection loop
  useEffect(() => {
    let stream: MediaStream | null = null;
    runningRef.current = true;
    
    const init = async () => {
      try {
        console.log("[RecognitionEngine] Starting Camera...");
        setStatus("loading");

        // Start camera first for instant feedback
        stream = await navigator.mediaDevices.getUserMedia({
          video: { 
            width: { ideal: 640 }, 
            height: { ideal: 480 },
            facingMode: "user" 
          },
          audio: false,
        }).catch(async (err) => {
          console.warn("[RecognitionEngine] Primary camera failed, trying fallback:", err);
          return await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        });

        if (!videoRef.current) return;
        videoRef.current.srcObject = stream;
        
        await new Promise((resolve) => {
          if (!videoRef.current) return resolve(null);
          videoRef.current.onloadedmetadata = () => resolve(null);
        });

        await videoRef.current.play();
        console.log("[RecognitionEngine] Camera active. Loading AI models...");

        // Load models in background
        await loadFaceModels();
        console.log("[RecognitionEngine] AI Models ready.");
        
        setStatus("ready");
        loop();
      } catch (e) {
        console.error("[RecognitionEngine] init error:", e);
        setStatus("error");
      }
    };

    init();

    return () => {
      console.log("[RecognitionEngine] Cleaning up...");
      runningRef.current = false;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const takeSnapshot = () => {
    if (!videoRef.current) return undefined;
    const v = videoRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = 240;
    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.7);
  };

  function shouldGreet(p: Person): boolean {
    const now = Date.now();
    const last = lastGreetedAtRef.current.get(p.id) ?? 0;
    if (p.greetingMode === "always") return true;
    if (p.greetingMode === "once-per-day") {
      return new Date(last).toDateString() !== new Date(now).toDateString();
    }
    return now - last >= p.cooldownMinutes * 60 * 1000;
  }

  async function loop() {
    while (runningRef.current && videoRef.current) {
      try {
        const v = videoRef.current;
        const canvas = canvasRef.current;
        if (v.readyState >= 2) {
          const detections = await detectAndDescribe(v);

          // Draw bounding boxes on overlay canvas
          if (canvas) {
            const ctx = canvas.getContext("2d");
            if (ctx) {
              ctx.clearRect(0, 0, canvas.width, canvas.height);
              if (detections.length > 0) {
                // Digital zoom crop of first face
                const { x, y, width, height } = detections[0].detection.box;
                const cropCanvas = document.createElement("canvas");
                cropCanvas.width = 120; cropCanvas.height = 120;
                const cropCtx = cropCanvas.getContext("2d");
                if (cropCtx) {
                  cropCtx.translate(120, 0); cropCtx.scale(-1, 1);
                  cropCtx.drawImage(v, x, y, width, height, 0, 0, 120, 120);
                  setZoomSnapshot(cropCanvas.toDataURL("image/jpeg", 0.6));
                }

                const time = Date.now() / 500;
                const pulse = Math.abs(Math.sin(time)) * 0.4 + 0.6;

                detections.forEach(det => {
                  const { x, y, width, height } = det.detection.box;
                  const flippedX = v.videoWidth - x - width;

                  ctx.shadowBlur = 15;
                  ctx.shadowColor = "rgba(241, 90, 36, 0.5)";
                  ctx.strokeStyle = `rgba(241, 90, 36, ${pulse})`;
                  ctx.lineWidth = 2;

                  const len = Math.min(width, height) * 0.2;
                  // Top-left
                  ctx.beginPath();
                  ctx.moveTo(flippedX, y + len); ctx.lineTo(flippedX, y); ctx.lineTo(flippedX + len, y);
                  ctx.stroke();
                  // Top-right
                  ctx.beginPath();
                  ctx.moveTo(flippedX + width - len, y); ctx.lineTo(flippedX + width, y); ctx.lineTo(flippedX + width, y + len);
                  ctx.stroke();
                  // Bottom-left
                  ctx.beginPath();
                  ctx.moveTo(flippedX, y + height - len); ctx.lineTo(flippedX, y + height); ctx.lineTo(flippedX + len, y + height);
                  ctx.stroke();
                  // Bottom-right
                  ctx.beginPath();
                  ctx.moveTo(flippedX + width - len, y + height); ctx.lineTo(flippedX + width, y + height); ctx.lineTo(flippedX + width, y + height - len);
                  ctx.stroke();

                  ctx.fillStyle = "rgba(241, 90, 36, 0.05)";
                  ctx.fillRect(flippedX, y, width, height);

                  ctx.shadowBlur = 0;
                  ctx.fillStyle = "#F15A24";
                  ctx.font = "bold 9px 'JetBrains Mono', monospace";
                  ctx.fillText("NEURAL_SCAN // ACTIVE", flippedX, y > 15 ? y - 10 : 15);

                  const distLabel = width < 50 ? "DISTANCE: FAR" : "DISTANCE: OPTIMAL";
                  ctx.fillStyle = width < 50 ? "#ef4444" : "#F15A24";
                  ctx.fillText(distLabel, flippedX, y + height + 15);
                });
              } else {
                setZoomSnapshot(null);
              }
            }
          }

          // Match detections against known people (dedupe faces → one row per person)
          if (detections.length > 0) {
            absenceRef.current = 0;
            let unknownFound = false;
            const bucket = new Map<string, { person: Person; confidence: number; expression: string }>();

            for (const det of detections) {
              let bestId: string | null = null;
              let bestD = Infinity;
              for (const p of peopleRef.current) {
                const d = bestDistance(Array.from(det.descriptor), p.embeddings);
                if (d < bestD) {
                  bestD = d;
                  bestId = p.id;
                }
              }

              if (bestId && bestD < MATCH_THRESHOLD) {
                const person = peopleRef.current.find((p) => p.id === bestId)!;
                const confidence = distanceToConfidence(bestD);
                let expression = "neutral";
                if (det.expressions) {
                  expression = Object.entries(det.expressions).sort((a, b) => (b[1] as number) - (a[1] as number))[0][0];
                }
                const prev = bucket.get(person.id);
                if (!prev || confidence > prev.confidence) {
                  bucket.set(person.id, { person, confidence, expression });
                }
              } else {
                unknownFound = true;
              }
            }

            const sorted = Array.from(bucket.values()).sort((a, b) => b.confidence - a.confidence);

            if (unknownFound) {
              const now = Date.now();
              if (now - lastUnknownLogRef.current > 30000) {
                lastUnknownLogRef.current = now;
                addLog({
                  id: crypto.randomUUID(),
                  personId: null,
                  name: "Noma'lum",
                  confidence: 0,
                  timestamp: Date.now(),
                  snapshot: takeSnapshot(),
                  expression: "unknown",
                });
                onUnknown(Array.from(detections[0].descriptor), takeSnapshot());
              }
            }

            if (sorted.length > 0) {
              const primary = sorted[0];
              if (shouldGreet(primary.person)) {
                const now = Date.now();
                sorted.forEach((m) => lastGreetedAtRef.current.set(m.person.id, now));
                addLog({
                  id: crypto.randomUUID(),
                  personId: primary.person.id,
                  name: primary.person.name,
                  confidence: primary.confidence,
                  timestamp: now,
                  expression: primary.expression,
                });
                onRecognize(sorted);
              }
            }
          } else {
            absenceRef.current++;
            if (absenceRef.current >= ABSENCE_FRAMES) onClear();
          }
        }
      } catch (e) {
        // silently continue
      }
      await new Promise(r => setTimeout(r, 100));
    }
  }

  if (status === "denied" || status === "error") {
    return (
      <div className="pointer-events-auto absolute right-4 top-4 z-30 w-64 rounded-2xl bg-destructive/10 p-6 text-center backdrop-blur-xl border border-destructive/20 shadow-2xl animate-in fade-in zoom-in duration-300">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-destructive/20 text-destructive">
          <ShieldAlert className="h-6 w-6" />
        </div>
        <h3 className="mb-2 font-display text-sm font-bold text-destructive uppercase tracking-widest">Kamera Taqiqlangan</h3>
        <p className="mb-4 text-[10px] leading-relaxed text-muted-foreground uppercase font-mono">
          Brauzer sozlamalaridan kameraga ruxsat bering va sahifani yangilang.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="w-full rounded-xl bg-destructive px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-destructive-foreground transition hover:opacity-90 shadow-lg shadow-destructive/20"
        >
          Qaytadan urinish
        </button>
      </div>
    );
  }

  return (
    <div className="pointer-events-none absolute right-4 top-4 z-20 w-44 md:w-64">
      {zoomSnapshot && (
        <motion.div
          initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
          className="glass absolute -left-20 top-0 h-16 w-16 overflow-hidden rounded-xl border border-primary/40 shadow-glow z-30"
        >
          <img src={zoomSnapshot} className="h-full w-full object-cover" alt="Zoom" />
          <div className="absolute inset-0 bg-primary/10 animate-pulse" />
          <div className="absolute bottom-0 left-0 right-0 bg-primary/80 text-[6px] font-mono text-white text-center py-0.5 uppercase tracking-tighter">
            Digital Zoom
          </div>
        </motion.div>
      )}
      <div className="glass relative overflow-hidden rounded-2xl border border-white/10 shadow-2xl">
        <video ref={videoRef} muted playsInline className="aspect-[4/3] w-full -scale-x-100 object-cover" />
        <canvas ref={canvasRef} width={640} height={480} className="absolute inset-0 h-full w-full pointer-events-none" />
        <div className="scan-line pointer-events-none absolute inset-0" />
        <div className="absolute bottom-2 left-2 flex items-center gap-1.5 rounded-full bg-black/60 px-2 py-1 text-[9px] font-mono uppercase tracking-wider backdrop-blur border border-white/5">
          <span className={`h-1 w-1 rounded-full ${status === "ready" ? "bg-primary animate-pulse shadow-glow" : status === "loading" ? "bg-amber-500 animate-bounce" : "bg-destructive"}`} />
          {status === "ready" ? "Live Feed" : status === "loading" ? "AI yuklanmoqda..." : "Xatolik"}
        </div>
      </div>
    </div>
  );
}
