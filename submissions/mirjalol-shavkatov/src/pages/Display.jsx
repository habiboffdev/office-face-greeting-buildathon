import { useState, useEffect, useRef, useCallback } from "react";
import { base44 } from "@/api/base44Client";
import VideoPlayer from "@/components/display/VideoPlayer";
import GreetingOverlay from "@/components/display/GreetingOverlay";
import FaceScanner from "@/components/display/FaceScanner";
import DisplayClock from "@/components/display/DisplayClock";
import IdleScreen from "@/components/display/IdleScreen";
import { useCompanySettings } from "@/lib/useCompanySettings";
import { t } from "@/lib/i18n";
import { Camera, ChevronLeft, ChevronRight, Settings } from "lucide-react";
import { Link } from "react-router-dom";

export default function Display() {
  const params = new URLSearchParams(window.location.search);
  const companyId = params.get("company");

  const settings = useCompanySettings(companyId);
  const { language, debug_mode, idle_screen_enabled, idle_timeout_minutes } = settings;
  const lang = language || "en";
  const [employees, setEmployees] = useState([]);
  const [videos, setVideos] = useState([]);
  const [greeting, setGreeting] = useState(null);
  const [isGreetingVisible, setIsGreetingVisible] = useState(false);
  const [videoPaused, setVideoPaused] = useState(false);
  const [cameraIndex, setCameraIndex] = useState(0);
  const [isIdle, setIsIdle] = useState(false);
  const greetingTimerRef = useRef(null);
  const idleTimerRef = useRef(null);
  const cooldownRef = useRef({});

  const resetIdleTimer = useCallback(() => {
    setIsIdle(false);
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    if (idle_screen_enabled) {
      idleTimerRef.current = setTimeout(() => setIsIdle(true), (idle_timeout_minutes || 30) * 60 * 1000);
    }
  }, [idle_screen_enabled, idle_timeout_minutes]);

  const loadData = async () => {
    if (!companyId) return;
    const [emps, vids] = await Promise.all([
      base44.entities.Employee.filter({ company_id: companyId, is_active: true }),
      base44.entities.Video.filter({ company_id: companyId, is_active: true }, "order", 50)
    ]);
    setEmployees(emps);
    setVideos(vids.sort((a, b) => (a.order || 0) - (b.order || 0)));
  };

  useEffect(() => {
    loadData();
    resetIdleTimer();
    return () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    };
  }, [resetIdleTimer]);

  const handlePersonRecognized = useCallback((employee) => {
    resetIdleTimer();
    
    const now = Date.now();
    const lastGreeted = cooldownRef.current[employee.id] || 0;
    // 30 second cooldown per person
    if (now - lastGreeted < 30000) return;

    cooldownRef.current[employee.id] = now;

    // Log this recognition event
    base44.entities.RecognitionLog.create({
      company_id: companyId,
      employee_id: employee.id,
      employee_name: employee.name,
      department: employee.department || "",
      is_birthday: (() => {
        if (!employee.birth_date) return false;
        const parts = employee.birth_date.split("-");
        const today = new Date();
        return parseInt(parts[1]) - 1 === today.getMonth() && parseInt(parts[2]) === today.getDate();
      })()
    }).catch(() => {});

    if (greetingTimerRef.current) {
      clearTimeout(greetingTimerRef.current);
    }

    const today = new Date();
    const isBirthday = employee.birth_date
      ? (() => {
          const parts = employee.birth_date.split("-");
          // compare only month (parts[1]) and day (parts[2]), ignore year
          return parseInt(parts[1]) - 1 === today.getMonth() && parseInt(parts[2]) === today.getDate();
        })()
      : false;

    setGreeting({
      name: employee.name,
      message: isBirthday
        ? t(lang, "happy_birthday", employee.name)
        : (employee.greeting_message || t(lang, "welcome", employee.name)),
      photoUrl: employee.photo_url,
      position: employee.position,
      employeeId: employee.id,
      isBirthday
    });
    setIsGreetingVisible(true);

    greetingTimerRef.current = setTimeout(() => {
      setIsGreetingVisible(false);
      setTimeout(() => setGreeting(null), 600);
    }, 5000);
  }, [lang, resetIdleTimer]);

  const [user, setUser] = useState(undefined);
  useEffect(() => {
    base44.auth.me().then(setUser).catch(() => setUser(null));
  }, []);

  if (!companyId) {
    const isAdmin = user?.role === "admin";
    return (
      <div className="fixed inset-0 bg-black flex items-center justify-center text-white text-center px-6">
        <div>
          <p className="text-xl font-semibold mb-2">No company selected</p>
          <p className="text-sm opacity-60 mb-6">Open the display from the Admin panel to get a company-specific URL.</p>
          {user === undefined ? null : isAdmin ? (
            <Link to="/admin" className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors">
              <Settings className="w-4 h-4" />
              Go to Admin Panel
            </Link>
          ) : (
            <p className="text-xs opacity-40">Access to admin panel is restricted.</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="kiosk-mode fixed inset-0 bg-black overflow-hidden">
      {/* Video Background */}
      <VideoPlayer videos={videos} paused={videoPaused} />

      {/* Dark overlay for better visibility of UI elements */}
      <div className="absolute inset-0 bg-black/10 pointer-events-none" />

      {/* Clock */}
      <DisplayClock />

      {/* Ghost play/pause button */}
      <button
        onClick={() => setVideoPaused((p) => !p)}
        className="absolute bottom-6 right-6 z-20 w-10 h-10 rounded-full flex items-center justify-center opacity-10 hover:opacity-60 transition-opacity duration-300"
        style={{ cursor: "default" }}
      >
        {videoPaused ? (
          <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5"><path d="M8 5v14l11-7z"/></svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
        )}
      </button>

      {/* Camera Switch Controls */}
      <div className="absolute top-6 left-6 z-20 flex gap-2">
        <button
          onClick={() => setCameraIndex((i) => Math.max(0, i - 1))}
          className="w-9 h-9 rounded-full flex items-center justify-center opacity-20 hover:opacity-60 transition-opacity bg-white/10 backdrop-blur-sm"
          style={{ cursor: "default" }}
        >
          <ChevronLeft className="w-5 h-5 text-white" />
        </button>
        <button
          onClick={() => setCameraIndex((i) => i + 1)}
          className="w-9 h-9 rounded-full flex items-center justify-center opacity-20 hover:opacity-60 transition-opacity bg-white/10 backdrop-blur-sm"
          style={{ cursor: "default" }}
        >
          <ChevronRight className="w-5 h-5 text-white" />
        </button>
      </div>

      {/* Face Scanner (hidden camera processing) */}
      <FaceScanner
        employees={employees}
        onPersonRecognized={handlePersonRecognized}
        debug={debug_mode}
        cameraIndex={cameraIndex}
      />

      {/* Greeting Overlay */}
      {greeting && (
        <GreetingOverlay
          greeting={greeting}
          isVisible={isGreetingVisible}
          companyId={companyId}
        />
      )}

      {/* Idle Screen */}
      <IdleScreen isIdle={isIdle} companyId={companyId} />
    </div>
  );
}