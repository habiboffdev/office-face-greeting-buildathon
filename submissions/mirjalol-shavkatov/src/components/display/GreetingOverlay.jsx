import { useEffect, useState, useRef } from "react";
import { Sparkles, Clock, MapPin, Megaphone, AlertTriangle, PartyPopper } from "lucide-react";
import { base44 } from "@/api/base44Client";
import { format, isToday } from "date-fns";
import { useCompanySettings } from "@/lib/useCompanySettings";
import { t } from "@/lib/i18n";
import confetti from "canvas-confetti";

function useLiveData(employeeId, companyId) {
  const [meetings, setMeetings] = useState([]);
  const [announcements, setAnnouncements] = useState([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!employeeId) { setReady(true); return; }
    const now = new Date();

    Promise.all([
      base44.entities.Meeting.filter({ employee_id: employeeId, company_id: companyId }).then((all) =>
        all
          .filter((m) => m.end_time && new Date(m.end_time) > now)
          .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
          .slice(0, 2)
      ).catch(() => []),
      base44.entities.Announcement.filter({ is_active: true, company_id: companyId }).then((all) =>
        all
          .filter((a) => !a.expires_at || new Date(a.expires_at) > now)
          .sort((a, b) => {
            const order = { urgent: 0, normal: 1, low: 2 };
            return (order[a.priority] ?? 1) - (order[b.priority] ?? 1);
          })
          .slice(0, 2)
      ).catch(() => []),
    ]).then(([m, a]) => {
      setMeetings(m);
      setAnnouncements(a);
      setReady(true);
    });
  }, [employeeId, companyId]);

  return { meetings, announcements, ready };
}

function formatMeetingTime(start, end) {
  const s = new Date(start);
  const e = new Date(end);
  const now = new Date();
  const isOngoing = s <= now && e >= now;
  const label = isToday(s) ? format(s, "h:mm a") : format(s, "MMM d, h:mm a");
  return { label, isOngoing };
}

// Marquee text: scrolls right-to-left only if text overflows its container
function MarqueeText({ text, className, style, isVisible }) {
  const containerRef = useRef(null);
  const textRef = useRef(null);
  const [scrollState, setScrollState] = useState({ shouldScroll: false, duration: 8 });
  const [animKey, setAnimKey] = useState(0);

  useEffect(() => {
    // Reset animation and re-measure after overlay entrance animation settles
    setScrollState({ shouldScroll: false, duration: 8 });
    const id = setTimeout(() => {
      if (!containerRef.current || !textRef.current) return;
      const cw = containerRef.current.offsetWidth;
      const tw = textRef.current.scrollWidth;
      if (tw > cw + 2) {
        setScrollState({ shouldScroll: true, duration: Math.max(6, tw / 60) });
        setAnimKey((k) => k + 1);
      }
    }, 800);
    return () => clearTimeout(id);
  }, [text, isVisible]);

  const { shouldScroll, duration } = scrollState;
  const pauseDelay = 1; // 1s pause before scrolling starts

  return (
    <div ref={containerRef} className="overflow-hidden w-full">
      <span
        key={animKey}
        ref={textRef}
        className={className}
        style={{
          ...style,
          display: "inline-block",
          whiteSpace: "nowrap",
          animation: shouldScroll ? `marquee ${duration}s linear ${pauseDelay}s infinite` : "none",
          animationFillMode: "both",
          paddingRight: shouldScroll ? "3rem" : 0,
        }}
      >
        {text}
      </span>
      <style>{`
        @keyframes marquee {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-100%); }
        }
      `}</style>
    </div>
  );
}

export default function GreetingOverlay({ greeting, isVisible, companyId }) {
  const [animClass, setAnimClass] = useState("");
  const { meetings, announcements, ready } = useLiveData(greeting?.employeeId, companyId);
  const { brand_color, language } = useCompanySettings(companyId);
  const lang = language || "en";
  const color = greeting?.isBirthday ? "#f97316" : (brand_color || "#D4AF37");

  useEffect(() => {
    setAnimClass(isVisible ? "greeting-enter" : "greeting-exit");

    if (isVisible && greeting?.isBirthday) {
      // Initial burst from both sides
      const fire = (x, angle) => confetti({
        particleCount: 80,
        spread: 70,
        angle,
        origin: { x, y: 0.7 },
        colors: ["#f97316", "#facc15", "#fb923c", "#fde68a", "#ffffff", "#ff6b6b"],
        gravity: 0.8,
        scalar: 1.1,
      });
      fire(0.1, 60);
      fire(0.9, 120);

      // Second burst after a short delay
      const t1 = setTimeout(() => {
        fire(0.2, 65);
        fire(0.8, 115);
      }, 600);

      // Continuous slow drizzle
      let elapsed = 0;
      const interval = setInterval(() => {
        elapsed += 400;
        if (elapsed > 4000) { clearInterval(interval); return; }
        confetti({
          particleCount: 12,
          spread: 120,
          origin: { x: Math.random(), y: 0 },
          colors: ["#f97316", "#facc15", "#fb923c", "#fde68a", "#ffffff"],
          gravity: 0.6,
          scalar: 0.9,
          drift: Math.random() - 0.5,
        });
      }, 400);

      return () => {
        clearTimeout(t1);
        clearInterval(interval);
      };
    }
  }, [isVisible, greeting?.isBirthday]);

  const hasExtra = meetings.length > 0 || announcements.length > 0;

  if (!ready) return null;

  return (
    <div className="absolute inset-0 flex items-end justify-center pb-16 pointer-events-none z-20">
      <div className={`${animClass} relative w-full mx-6`} style={{ maxWidth: hasExtra ? "900px" : "672px" }}>
        <div
          className="relative overflow-hidden rounded-2xl"
          style={{
            background: "linear-gradient(135deg, rgba(0,0,0,0.78) 0%, rgba(10,15,30,0.88) 100%)",
            backdropFilter: "blur(20px)",
            border: `1px solid ${color}99`,
            boxShadow: `0 0 60px ${color}40, 0 20px 60px rgba(0,0,0,0.5)`
          }}
        >
          {/* Birthday banner */}
          {greeting?.isBirthday && (
            <div className="flex items-center justify-center gap-2 py-2 text-sm font-semibold tracking-wide" style={{ background: "linear-gradient(90deg, #b91c1c, #d97706, #b91c1c)", backgroundSize: "200% 100%", animation: "birthdayBanner 3s linear infinite" }}>
              <PartyPopper className="w-4 h-4 text-white" />
              <span className="text-white">{t(lang, "birthday_banner")}</span>
              <PartyPopper className="w-4 h-4 text-white" />
            </div>
          )}

          {/* Brand color top border */}
          <div className="h-0.5 w-full" style={{ background: `linear-gradient(90deg, transparent, ${color}, transparent)` }} />

          <div className={`flex ${hasExtra ? "divide-x divide-white/10" : ""}`}>
            {/* LEFT — identity */}
            <div className="flex-1 px-8 py-6 flex items-center gap-5 min-w-0 overflow-hidden">
              {greeting?.photoUrl && (
                <div className="relative flex-shrink-0">
                  <div className="w-18 h-18 rounded-full overflow-hidden pulse-glow" style={{ width: 72, height: 72, border: "2px solid rgba(212,175,55,0.6)" }}>
                    <img src={greeting.photoUrl} alt={greeting.name} className="w-full h-full object-cover" />
                  </div>
                  <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-green-500 border-2 border-black" />
                </div>
              )}
              <div className="min-w-0 flex-1 overflow-hidden">
                <div className="flex items-center gap-2 mb-1">
                  {greeting?.isBirthday
                    ? <PartyPopper className="w-3.5 h-3.5 flex-shrink-0" style={{ color }} />
                    : <Sparkles className="w-3.5 h-3.5 flex-shrink-0" style={{ color }} />
                  }
                  <span className="text-xs font-medium tracking-widest uppercase" style={{ color: `${color}cc` }}>
                    {greeting?.isBirthday ? t(lang, "birthday_label") : t(lang, "recognized")}
                  </span>
                </div>
                <MarqueeText
                  text={greeting?.message || ""}
                  className="font-display font-semibold text-white leading-tight"
                  isVisible={isVisible}
                  style={{
                    fontSize: (greeting?.message?.length || 0) > 40
                      ? "1.25rem"
                      : (greeting?.message?.length || 0) > 25
                        ? "1.5rem"
                        : "1.75rem"
                  }}
                />
                {greeting?.position && (
                  <p className="text-white/50 text-sm mt-1 font-body truncate">{greeting.position}</p>
                )}
              </div>
            </div>

            {/* RIGHT — meetings + announcements */}
            {hasExtra && (
              <div className="w-80 flex-shrink-0 px-6 py-5 flex flex-col gap-4 overflow-hidden">
                {/* Meetings */}
                {meetings.length > 0 && (
                  <div className="min-w-0">
                    <p className="text-xs tracking-widest uppercase text-white/40 mb-2">{t(lang, "todays_schedule")}</p>
                    <div className="space-y-2">
                      {meetings.map((m) => {
                        const { label, isOngoing } = formatMeetingTime(m.start_time, m.end_time);
                        return (
                          <div key={m.id} className="flex items-start gap-2">
                            <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${isOngoing ? "bg-green-400 animate-pulse" : "bg-white/30"}`} />
                            <div className="min-w-0">
                              <p className="text-white text-sm font-medium truncate leading-tight">{m.title}</p>
                              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5 text-white/40 text-xs">
                                <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{label}</span>
                                {m.location && (
                                  <span className="flex items-center gap-1 max-w-[90px] truncate">
                                    <MapPin className="w-3 h-3 flex-shrink-0" />{m.location}
                                  </span>
                                )}
                                {isOngoing && <span className="text-green-400 font-medium">{t(lang, "in_progress")}</span>}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Announcements */}
                {announcements.length > 0 && (
                  <div className="min-w-0">
                    <p className="text-xs tracking-widest uppercase text-white/40 mb-2">{t(lang, "announcements")}</p>
                    <div className="space-y-3">
                      {announcements.map((a) => (
                        <div key={a.id} className="flex items-start gap-2">
                          {a.priority === "urgent"
                            ? <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                            : <Megaphone className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: "#D4AF37" }} />
                          }
                          <div className="min-w-0">
                            <p className={`text-sm font-semibold leading-tight ${a.priority === "urgent" ? "text-red-300" : "text-white"}`}>
                              {a.title}
                            </p>
                            <p className="text-white/60 text-xs mt-0.5 leading-relaxed" style={{
                              display: "-webkit-box",
                              WebkitLineClamp: 3,
                              WebkitBoxOrient: "vertical",
                              overflow: "hidden",
                              whiteSpace: "normal",
                              wordBreak: "break-word"
                            }}>
                              {a.body}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Progress bar */}
          <div className="h-0.5 bg-white/10">
            <div className="h-full" style={{ background: `linear-gradient(90deg, ${color}, ${color}aa)`, animation: "progressBar 5s linear forwards" }} />
          </div>
        </div>
      </div>

      <style>{`
        @keyframes progressBar {
          from { width: 100%; }
          to { width: 0%; }
        }
        @keyframes birthdayBanner {
          0%   { background-position: 0% 0%; }
          100% { background-position: 200% 0%; }
        }
      `}</style>
    </div>
  );
}