import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState, useRef } from "react";
import { format, subDays, eachDayOfInterval, isSameDay, subMonths, startOfToday } from "date-fns";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Users, 
  Settings, 
  Activity, 
  Play, 
  Plus, 
  Trash2, 
  ShieldCheck, 
  Terminal, 
  LogOut, 
  Bell, 
  Wifi, 
  Cloud, 
  Clock,
  History,
  ShieldAlert,
  Layout,
  Upload,
  Image as ImageIcon,
  Eraser,
  X
} from "lucide-react";
import { listPeople, deletePerson, listLogs, clearLogs, saveFile, deleteFile, getFile, persistPlaylist, loadPlaylistFromStorage, PLAYLIST_LS_KEY, PLAYLIST_DAY_LS_KEY } from "@/lib/face/db";
import { saveKioskPrefs, loadKioskPrefs, type KioskPrefs } from "@/lib/face/kioskPrefs";
import { pushPlaylistRemote } from "@/lib/face/playlistSync";
import { captureVideoPosterDataUrl } from "@/lib/face/videoPoster";
import type { Person, RecognitionLog, PlaylistItem } from "@/lib/face/types";
import { EnrollDialog } from "@/components/face/EnrollDialog";
import { BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

export const Route = createFileRoute("/admin")({
  component: AdminPage,
  head: () => ({
    meta: [
      { title: "Admin Panel · VisionGate" },
      { name: "description", content: "Xodimlar, loglar va playlistni boshqarish." },
    ],
  }),
});

type Tab = "monitor" | "employees" | "attendance" | "settings" | "media" | "logs";

function AdminPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<Tab>("monitor");
  const [people, setPeople] = useState<Person[]>([]);
  const [logs, setLogs] = useState<RecognitionLog[]>([]);
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [editingPerson, setEditingPerson] = useState<Person | undefined>();
  const [playlistMain, setPlaylistMain] = useState<PlaylistItem[]>([]);
  const [playlistDay, setPlaylistDay] = useState<PlaylistItem[]>([]);
  const [mediaBucket, setMediaBucket] = useState<"main" | "day">("main");
  const [apiKey, setApiKey] = useState("");
  const [tgToken, setTgToken] = useState("");
  const [tgChatId, setTgChatId] = useState("");
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    if (localStorage.getItem("visiongate:auth") !== "true") {
      navigate({ to: "/login" });
    }
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem("visiongate:auth");
    navigate({ to: "/login" });
  };

  const refresh = async () => {
    if (localStorage.getItem("visiongate:auth") !== "true") return;
    setPeople(await listPeople());
    setLogs(await listLogs(100));
    setPlaylistMain(loadPlaylistFromStorage(PLAYLIST_LS_KEY));
    setPlaylistDay(loadPlaylistFromStorage(PLAYLIST_DAY_LS_KEY));
  };

  const openEnroll = () => {
    setEditingPerson(undefined);
    setEnrollOpen(true);
  };

  const openEdit = (p: Person) => {
    setEditingPerson(p);
    setEnrollOpen(true);
  };

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    refresh();
    try {
      setPlaylistMain(loadPlaylistFromStorage(PLAYLIST_LS_KEY));
      setPlaylistDay(loadPlaylistFromStorage(PLAYLIST_DAY_LS_KEY));
      setApiKey(localStorage.getItem("visiongate:elevenlabs_key") || "");
      setTgToken(localStorage.getItem("visiongate:tg_token") || "");
      setTgChatId(localStorage.getItem("visiongate:tg_chatid") || "");
    } catch {}
    return () => clearInterval(t);
  }, []);

  const saveTg = () => {
    localStorage.setItem("visiongate:tg_token", tgToken);
    localStorage.setItem("visiongate:tg_chatid", tgChatId);
    alert("Telegram sozlamalari saqlandi!");
  };

  const saveKey = (val: string) => {
    setApiKey(val);
    localStorage.setItem("visiongate:elevenlabs_key", val);
  };

  const resetSettings = () => {
    if (!confirm("Barcha sozlamalar (API kalitlar, Telegram tokenlar) o'chirilsinmi?")) return;
    localStorage.removeItem("visiongate:elevenlabs_key");
    localStorage.removeItem("visiongate:tg_token");
    localStorage.removeItem("visiongate:tg_chatid");
    setApiKey("");
    setTgToken("");
    setTgChatId("");
    alert("Sozlamalar tozalandi!");
  };

  const stats = useMemo(() => {
    const today = new Date().toDateString();
    const todayLogs = logs.filter((l) => new Date(l.timestamp).toDateString() === today);
    const known = todayLogs.filter((l) => l.personId);
    const uniqueToday = new Set(known.map((l) => l.personId)).size;
    const unknown = todayLogs.filter((l) => !l.personId).length;
    
    // Mood distribution
    const moods = known.reduce((acc, l) => {
      if (l.expression) acc[l.expression] = (acc[l.expression] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return {
      totalPeople: people.length,
      todayDetections: todayLogs.length,
      uniqueToday,
      unknown,
      moods,
      burnoutRisk: known.filter(l => l.expression === "sad" || l.expression === "fearful").length > 5
    };
  }, [people, logs]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground font-sans">
      {/* Sidebar - Technical Style */}
      <aside className="w-64 border-r border-border bg-card flex flex-shrink-0 flex-col shadow-xl">
        <div className="p-6 border-b border-border bg-primary/5">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center border border-primary/20 shadow-glow">
              <ShieldCheck className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="font-display font-bold text-lg tracking-tight leading-none uppercase">VisionGate</h1>
              <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mt-1">Admin Terminali v2.5</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-4 py-8 space-y-1 overflow-y-auto">
          <SidebarLink active={activeTab === "monitor"} icon={Activity} label="Jonli Monitor" onClick={() => setActiveTab("monitor")} />
          <SidebarLink active={activeTab === "attendance"} icon={History} label="Davomat Tizimi" onClick={() => setActiveTab("attendance")} />
          <SidebarLink active={activeTab === "employees"} icon={Users} label="Xodimlar Bazasi" onClick={() => setActiveTab("employees")} />
          <SidebarLink active={activeTab === "settings"} icon={Settings} label="Boshqaruv Paneli" onClick={() => setActiveTab("settings")} />
          <SidebarLink active={activeTab === "media"} icon={Play} label="Media Manager" onClick={() => setActiveTab("media")} />
          <SidebarLink active={activeTab === "logs"} icon={History} label="Tizim Loglari" onClick={() => setActiveTab("logs")} />
        </nav>

        <div className="p-5 border-t border-border bg-primary/5 space-y-4">
          <div className="flex flex-col gap-2">
            <button 
              onClick={openEnroll}
              className="flex items-center gap-3 px-4 py-2.5 bg-primary text-primary-foreground rounded-xl text-[11px] font-bold uppercase tracking-wider hover:brightness-110 transition shadow-lg shadow-primary/20"
            >
              <Plus className="h-4 w-4" /> Yangi Xodim
            </button>
            <button 
              onClick={handleLogout}
              className="flex items-center gap-3 px-4 py-2.5 bg-destructive/10 text-destructive border border-destructive/20 rounded-xl text-[11px] font-bold uppercase tracking-wider justify-center hover:bg-destructive/20 transition group w-full"
            >
              <LogOut className="h-4 w-4 group-hover:-translate-x-1 transition" /> CHIQISH
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 bg-background/50 backdrop-blur-sm grid-bg">
        {/* Technical Header Bar */}
        <header className="h-16 border-b border-border bg-card/80 backdrop-blur-md px-8 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 px-3 py-1 bg-primary/10 border border-primary/20 rounded-full">
              <div className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
              <span className="text-[9px] font-mono font-bold text-primary uppercase tracking-tighter">Holat: Faol Skanerlash</span>
            </div>
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-4 text-muted-foreground font-mono text-[11px] tabular-nums">
              <Clock className="h-3.5 w-3.5" />
              <span suppressHydrationWarning>{now.toLocaleTimeString([], { hour12: false })} Toshkent</span>
            </div>
          </div>

          <div className="flex items-center gap-5">
            <Cloud className="h-4 w-4 text-muted-foreground/40" />
            <Wifi className="h-4 w-4 text-primary" />
            <Bell className="h-4 w-4 text-muted-foreground/40" />
            <div className="h-8 w-8 rounded-full bg-primary/10 border border-primary/20 overflow-hidden ring-1 ring-primary/20">
              <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Admin" alt="Admin" />
            </div>
          </div>
        </header>

        {/* View Port */}
        <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          <div className="max-w-6xl mx-auto pb-12">
            {activeTab === "monitor" && <MonitorView logs={logs} stats={stats} />}
            {activeTab === "attendance" && <AttendanceView logs={logs} people={people} />}
            {activeTab === "employees" && (
              <EmployeesView people={people} onRefresh={refresh} onEdit={openEdit} onAdd={openEnroll} />
            )}
            {activeTab === "settings" && (
              <SettingsView 
                tgToken={tgToken} setTgToken={setTgToken}
                tgChatId={tgChatId} setTgChatId={setTgChatId}
                apiKey={apiKey} onSaveKey={saveKey}
                onSaveTg={saveTg}
                onReset={resetSettings}
              />
            )}
            {activeTab === "media" && (
              <MediaView
                playlist={mediaBucket === "main" ? playlistMain : playlistDay}
                storageKey={mediaBucket === "main" ? PLAYLIST_LS_KEY : PLAYLIST_DAY_LS_KEY}
                mediaBucket={mediaBucket}
                onMediaBucketChange={setMediaBucket}
                onRefresh={refresh}
              />
            )}
            {activeTab === "logs" && <LogsView logs={logs} onClear={async () => { await clearLogs(); refresh(); }} />}
          </div>
        </div>
      </main>

      <EnrollDialog 
        open={enrollOpen} 
        initialPerson={editingPerson}
        onClose={() => { setEnrollOpen(false); setEditingPerson(undefined); }} 
        onCreated={refresh} 
      />
    </div>
  );
}

function SidebarLink({ active, icon: Icon, label, onClick }: { active: boolean; icon: any; label: string; onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={`flex items-center gap-3 w-full px-4 py-3 rounded-xl transition-all duration-200 group ${
        active 
          ? "bg-primary/10 text-primary border border-primary/20 shadow-glow" 
          : "text-muted-foreground hover:bg-primary/5 hover:text-foreground border border-transparent"
      }`}
    >
      <Icon className={`h-5 w-5 transition-transform duration-300 ${active ? "scale-110" : "group-hover:scale-110 opacity-70"}`} />
      <span className="text-sm font-semibold tracking-tight leading-none">{label}</span>
      {active && <div className="ml-auto h-1.5 w-1.5 rounded-full bg-primary shadow-glow" />}
    </button>
  );
}

function MonitorView({ logs, stats }: { logs: any[]; stats: any }) {
  const [activeCam, setActiveCam] = useState("CAM-01");
  const cameras = ["CAM-01", "CAM-02", "CAM-03"];

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold font-display tracking-tight uppercase">Tizim Umumiy Ko'rinishi</h2>
        <div className="flex items-center gap-4">
          <div className="flex gap-2 p-1 bg-background border border-border rounded-xl">
            {cameras.map(cam => (
              <button 
                key={cam}
                onClick={() => setActiveCam(cam)}
                className={`px-3 py-1.5 rounded-lg text-[10px] font-mono font-bold transition-all ${activeCam === cam ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-primary/10'}`}
              >
                {cam}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 rounded-lg text-[10px] font-bold uppercase tracking-widest">
            <ShieldCheck className="h-3.5 w-3.5" /> Tizim Barqaror
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="glass rounded-2xl overflow-hidden aspect-video border-primary/20 relative group">
              <div className="absolute top-3 left-3 flex items-center gap-2 px-2 py-1 bg-black/70 rounded-md text-[9px] font-mono uppercase backdrop-blur border border-white/10 z-10 text-white">
                <div className="h-1.5 w-1.5 rounded-full bg-destructive animate-pulse" />
                {activeCam} // {activeCam === "CAM-01" ? "REAL_LIVE_FEED" : "IP_STREAM_ACTIVE"}
              </div>
              {activeCam === "CAM-01" ? <SimpleCamera /> : <div className="h-full w-full bg-black flex items-center justify-center font-mono text-[10px] text-primary/40">CONNECTING TO IP STREAM...</div>}
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent pointer-events-none" />
              <div className="scan-line absolute inset-0 pointer-events-none" />
            </div>
            <div className="glass rounded-2xl overflow-hidden aspect-video border-border relative group p-6 flex flex-col justify-center bg-card/40">
               <h4 className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-4">Noma'lum Mehmonlar</h4>
               <div className="space-y-2">
                 {logs.filter(l => !l.personId).slice(0, 2).map((l, i) => (
                   <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-destructive/5 border border-destructive/10">
                     <ShieldAlert className="h-4 w-4 text-destructive/60" />
                     <div className="text-[10px] font-mono uppercase text-destructive/80">Mehmon Detected // {new Date(l.timestamp).toLocaleTimeString()}</div>
                   </div>
                 ))}
                 {logs.filter(l => !l.personId).length === 0 && (
                   <div className="text-[10px] font-mono text-muted-foreground/30 uppercase text-center py-4 tracking-widest">Hozircha bo'sh</div>
                 )}
               </div>
            </div>
          </div>

          <div className="glass rounded-2xl p-6 border-border shadow-xl">
            <div className="flex items-center justify-between mb-8 border-b border-border pb-4">
              <h3 className="font-bold text-xs uppercase tracking-[0.3em] text-muted-foreground flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 text-primary" /> Oxirgi Aniqlashlar
              </h3>
            </div>
            <div className="space-y-3">
              {logs.slice(0, 5).map((log, i) => (
                <div key={i} className="flex items-center justify-between p-3.5 rounded-xl bg-primary/5 border border-transparent hover:border-primary/20 transition-all duration-300 group">
                  <div className="flex items-center gap-4">
                    <div className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center border border-primary/20 group-hover:bg-primary/20 transition">
                      {log.personId ? <ShieldCheck className="h-6 w-6 text-primary" /> : <ShieldAlert className="h-6 w-6 text-destructive/60" />}
                    </div>
                    <div>
                      <div className="font-bold text-sm tracking-tight text-foreground/90">{log.name}</div>
                      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
                        {log.personId ? `TASDIQLANGAN KIRISH // DARVOZA 01` : "NOMA'LUM SHAXS // OGOHLANTIRISH"}
                      </div>
                    </div>
                  </div>
                  <div className="text-right flex flex-col items-end">
                    <div className="text-xs font-mono font-bold tabular-nums text-primary">
                      {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}
                    </div>
                    <div className="px-1.5 py-0.5 rounded bg-background/80 text-[9px] font-mono uppercase text-muted-foreground mt-1 border border-border">
                      ANIQLIK: {(log.confidence * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="glass rounded-2xl p-6 border-border bg-card/20 shadow-xl">
             <h3 className="font-bold text-[10px] uppercase tracking-[0.3em] mb-6 text-muted-foreground">Apparat Boshqaruvi (Relay / GPIO)</h3>
             <div className="flex gap-4">
               <button onClick={() => alert("Eshik ochildi (Relay-1 Triggered)")} className="flex-1 py-4 bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 rounded-xl text-[10px] font-bold uppercase tracking-widest hover:bg-emerald-500/20 transition">ESHIKNI OCHISH</button>
               <button onClick={() => alert("Signalizatsiya faollashdi (Relay-2 Triggered)")} className="flex-1 py-4 bg-destructive/10 text-destructive border border-destructive/20 rounded-xl text-[10px] font-bold uppercase tracking-widest hover:bg-destructive/20 transition">TREVOGA</button>
             </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="glass-strong rounded-2xl p-6 border-primary/20 relative overflow-hidden shadow-2xl">
            <div className="absolute top-0 right-0 p-4 opacity-5">
              <Terminal className="h-20 w-20 text-primary" />
            </div>
            <h3 className="font-bold text-[10px] uppercase tracking-[0.3em] mb-6 text-primary">Neyron Tarmoq Analitikasi</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-background border border-border shadow-sm">
                <div className="text-muted-foreground text-[8px] uppercase font-mono tracking-widest mb-1">Aniqlash/Soat</div>
                <div className="text-2xl font-display font-bold text-primary tabular-nums">{stats.todayDetections}</div>
              </div>
              <div className="p-4 rounded-xl bg-background border border-border shadow-sm">
                <div className="text-muted-foreground text-[8px] uppercase font-mono tracking-widest mb-1">Xodimlar</div>
                <div className="text-2xl font-display font-bold text-primary tabular-nums">{stats.totalPeople}</div>
              </div>
            </div>
            <div className="mt-6 pt-6 border-t border-border">
              <div className="flex justify-between text-[9px] font-mono uppercase mb-2 text-muted-foreground">
                <span>Tanish Aniq'ligi</span>
                <span className="text-primary">98.2%</span>
              </div>
              <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                <div className="h-full bg-primary/60 w-[98.2%]" />
              </div>
            </div>
          </div>

          <div className="glass rounded-2xl p-6 border-border shadow-xl">
            <h3 className="font-bold text-[10px] uppercase tracking-[0.3em] mb-5 text-muted-foreground">Kayfiyat Tahlili (Mood Analytics)</h3>
            {Object.keys(stats.moods).length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={Object.entries(stats.moods).map(([mood, count]) => ({ mood, count: count as number }))}>
                    <XAxis dataKey="mood" tick={{ fontSize: 9, fill: "#888" }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: "#1a1a2e", border: "1px solid rgba(241,90,36,0.2)", borderRadius: 12, fontSize: 11 }} />
                    <Bar dataKey="count" fill="#F15A24" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  {Object.entries(stats.moods).map(([mood, count]) => (
                    <div key={mood} className="flex justify-between text-[9px] font-mono uppercase px-2 py-1 rounded bg-primary/5 border border-primary/10">
                      <span>{mood}</span>
                      <span className="text-primary font-bold">{count as number}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="text-[10px] font-mono text-muted-foreground/30 text-center py-8">Ma'lumotlar yo'q</div>
            )}
            
            {stats.burnoutRisk && (
              <div className="mt-6 p-4 rounded-xl bg-destructive/10 border border-destructive/20 flex items-center gap-3">
                <ShieldAlert className="h-5 w-5 text-destructive animate-pulse" />
                <div className="text-[9px] font-bold text-destructive uppercase tracking-widest leading-tight">
                  DIQQAT: Jamoada charchoq darajasi yuqori!<br/>Dam olish tavsiya etiladi.
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}

function EmployeesView({
  people,
  onRefresh,
  onEdit,
  onAdd,
}: {
  people: Person[];
  onRefresh: () => void;
  onEdit: (p: Person) => void;
  onAdd: () => void;
}) {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-3xl font-bold font-display tracking-tight uppercase">Xodimlar Bazasi</h2>
          <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest mt-1">
            Holat: Neyron Sinxronizatsiya Faol
          </p>
        </div>
        <button
          type="button"
          onClick={onAdd}
          className="flex items-center justify-center gap-2 px-6 py-3.5 bg-primary text-primary-foreground rounded-xl text-[10px] font-bold uppercase tracking-wider hover:brightness-110 transition shadow-lg shadow-primary/20 shrink-0"
        >
          <Plus className="h-4 w-4" /> Yangi Xodim
        </button>
      </div>

      <div className="glass-strong rounded-2xl border-border overflow-hidden shadow-2xl">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-primary/5 border-b border-border text-[10px] uppercase tracking-[0.3em] text-muted-foreground font-mono">
              <th className="px-8 py-5">Xodim Ma'lumotlari</th>
              <th className="px-8 py-5">Lavozimi</th>
              <th className="px-8 py-5">AI Salomlashish Rejimi</th>
              <th className="px-8 py-5">Til / Aloqa</th>
              <th className="px-8 py-5 text-right">Amallar</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {people.map((p) => (
              <tr key={p.id} className="hover:bg-primary/[0.02] transition-colors group">
                <td className="px-8 py-5">
                  <div className="flex items-center gap-4">
                    <div className="h-11 w-11 rounded-xl border border-border overflow-hidden group-hover:border-primary/40 transition-all duration-500 bg-background shadow-sm">
                      {p.avatar ? <img src={p.avatar} alt={p.name} className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center text-primary/30"><Users className="h-5 w-5" /></div>}
                    </div>
                    <div>
                      <div className="font-bold text-sm tracking-tight text-foreground/90">{p.name}</div>
                      <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mt-0.5">ID: #VG-{p.id.slice(0, 4)}</div>
                    </div>
                  </div>
                </td>
                <td className="px-8 py-5">
                  <div className="flex items-center gap-2">
                    <div className="inline-flex px-2 py-0.5 rounded bg-primary/10 border border-primary/20 text-primary text-[9px] font-bold uppercase tracking-wider">
                      {p.role}
                    </div>
                    {p.isBlacklisted && (
                      <div className="inline-flex px-2 py-0.5 rounded bg-destructive/10 border border-destructive/20 text-destructive text-[9px] font-bold uppercase tracking-wider animate-pulse">
                        BLACKLIST
                      </div>
                    )}
                  </div>
                </td>
                <td className="px-8 py-5">
                  <span className="text-[11px] text-muted-foreground italic">"{(p.greetingMode || "Har doim").toUpperCase()}"</span>
                </td>
                <td className="px-8 py-5">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground uppercase">
                    <Wifi className="h-3 w-3 text-primary/40" /> {p.language.toUpperCase()} / EN
                  </div>
                </td>
                <td className="px-8 py-5 text-right">
                  <div className="flex justify-end gap-2">
                    <button 
                      onClick={() => onEdit(p)}
                      className="p-2.5 text-muted-foreground/40 hover:text-primary hover:bg-primary/10 rounded-xl transition-all duration-300"
                    >
                      <Settings className="h-4 w-4" />
                    </button>
                    <button 
                      onClick={async () => { if(confirm("Xodimni o'chirishni tasdiqlaysizmi?")) { await deletePerson(p.id); onRefresh(); }}}
                      className="p-2.5 text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 rounded-xl transition-all duration-300"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SettingsView({
  tgToken,
  setTgToken,
  tgChatId,
  setTgChatId,
  apiKey,
  onSaveKey,
  onSaveTg,
  onReset,
}: any) {
  const [kp, setKp] = useState(loadKioskPrefs);

  const patchKiosk = (partial: Partial<KioskPrefs>) => {
    const next = saveKioskPrefs(partial);
    setKp(next);
    if (partial.cloudPlaylistSync === true) {
      void pushPlaylistRemote(loadPlaylistFromStorage(PLAYLIST_LS_KEY));
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold font-display tracking-tight uppercase">Tizimni Sozlash</h2>
          <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest mt-1">Terminal konfiguratsiyasi</p>
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-2 px-5 py-3 bg-destructive/10 text-destructive border border-destructive/20 rounded-xl text-[9px] font-bold uppercase tracking-widest hover:bg-destructive/20 transition"
        >
          <Trash2 className="h-3.5 w-3.5" /> SOZLAMALARNI TOZALASH
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <section className="glass rounded-2xl p-8 border-primary/10 bg-primary/[0.02] relative group overflow-hidden shadow-xl">
          <div className="absolute top-0 right-0 p-4 opacity-[0.03] group-hover:opacity-[0.06] transition-opacity duration-700">
            <Bell className="h-32 w-32" />
          </div>
          <div className="flex items-center gap-4 mb-10">
            <div className="h-12 w-12 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-glow">
              <Bell className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h3 className="font-bold text-xl tracking-tight uppercase leading-none">Telegram Integratsiyasi</h3>
              <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest mt-2">Ogohlantirish protokollari</p>
            </div>
          </div>

          <div className="space-y-8">
            <div className="space-y-3">
              <label className="text-[9px] font-mono uppercase tracking-[0.3em] text-muted-foreground block">Telegram Bot Status</label>
              <div className="flex gap-4">
                <input
                  type="password"
                  value={tgToken}
                  onChange={(e) => setTgToken(e.target.value)}
                  placeholder="Bot Token"
                  className="flex-1 bg-background border border-border rounded-xl px-4 py-3.5 text-sm focus:border-primary outline-none transition shadow-sm"
                />
                <input
                  type="text"
                  value={tgChatId}
                  onChange={(e) => setTgChatId(e.target.value)}
                  placeholder="Chat ID"
                  className="w-1/3 bg-background border border-border rounded-xl px-4 py-3.5 text-sm focus:border-primary outline-none transition shadow-sm"
                />
              </div>
            </div>
            <button
              onClick={onSaveTg}
              className="w-full py-4 bg-primary text-primary-foreground font-bold rounded-xl text-[10px] uppercase tracking-[0.3em] hover:shadow-glow transition-all duration-300"
            >
              Update Neural Link
            </button>
          </div>
        </section>

        <section className="glass rounded-2xl p-8 border-border bg-card relative group overflow-hidden shadow-xl">
          <div className="absolute top-0 right-0 p-4 opacity-[0.03] group-hover:opacity-[0.06] transition-opacity duration-700">
            <Activity className="h-32 w-32" />
          </div>
          <div className="flex items-center gap-4 mb-10">
            <div className="h-12 w-12 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-glow">
              <Activity className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h3 className="font-bold text-xl tracking-tight uppercase leading-none">AI Ovoz Sozlamalari</h3>
              <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest mt-2">ElevenLabs Neyron Nutqi</p>
            </div>
          </div>

          <div className="space-y-8">
            <div className="space-y-3">
              <label className="text-[9px] font-mono uppercase tracking-[0.3em] text-muted-foreground block">Voice Synthesis Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => onSaveKey(e.target.value)}
                placeholder="ElevenLabs Secret"
                className="w-full bg-background border border-border rounded-xl px-4 py-3.5 text-sm focus:border-primary outline-none transition shadow-sm"
              />
            </div>
            <div className="p-5 rounded-2xl bg-primary/5 border border-primary/10 flex items-center gap-4">
              <ShieldAlert className="h-5 w-5 text-primary/40" />
              <p className="text-[10px] text-muted-foreground font-mono leading-relaxed">
                BIO-ENCRYPTION: AES-256 ACTIVE
                <br />
                ENDPOINT: OPTIMAL SYNC
              </p>
            </div>
          </div>
        </section>
      </div>

      <section className="glass rounded-2xl p-8 border-border bg-card shadow-xl space-y-8">
        <div className="flex items-center gap-4">
          <div className="h-12 w-12 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-glow">
            <Cloud className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h3 className="font-bold text-xl tracking-tight uppercase leading-none">Kiosk terminal</h3>
            <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest mt-2">
              Media, bulut ro‘yxagi, jadval va soatlik mini-suhbat
            </p>
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <label className="flex items-start gap-3 cursor-pointer rounded-xl border border-border p-4 hover:bg-muted/30 transition">
            <input
              type="checkbox"
              className="mt-1"
              checked={kp.cloudPlaylistSync}
              onChange={(e) => patchKiosk({ cloudPlaylistSync: e.target.checked })}
            />
            <span className="text-xs leading-relaxed">
              <span className="font-bold uppercase tracking-wide text-[10px] block text-primary">Bulut playlist</span>
              Supabase `settings` jadvalida asosiy ro‘yxakni saqlash — boshqa kiosk-brauzerlar tortib oladi (posterlar emas,
              faqat URL va indeks IDlari).
            </span>
          </label>

          <label className="flex items-start gap-3 cursor-pointer rounded-xl border border-border p-4 hover:bg-muted/30 transition">
            <input
              type="checkbox"
              className="mt-1"
              checked={kp.videoUnmuted}
              onChange={(e) => patchKiosk({ videoUnmuted: e.target.checked })}
            />
            <span className="text-xs leading-relaxed">
              <span className="font-bold uppercase tracking-wide text-[10px] block text-primary">Video ovozi</span>
              Ba’zi brauzerlar ovozsiz autoplay talab qiladi; yoqsangiz mijoz brauzer popupiga qarab ovoz chiqishi mumkin.
            </span>
          </label>

          <label className="flex items-start gap-3 cursor-pointer rounded-xl border border-border p-4 hover:bg-muted/30 transition md:col-span-2">
            <input
              type="checkbox"
              className="mt-1"
              checked={kp.scheduleEnabled}
              onChange={(e) => patchKiosk({ scheduleEnabled: e.target.checked })}
            />
            <span className="text-xs leading-relaxed">
              <span className="font-bold uppercase tracking-wide text-[10px] block text-primary">Vaqt bo‘yicha “kun sloti” playlist</span>
              Media Managerda «Kun sloti» ro‘yxagini to‘ldiring. Tanlangan soat oralig‘ida shu ro‘yxak ishlaydi; boshqa vaqtda asosiy
              playlist.
            </span>
          </label>

          <div className="flex flex-wrap gap-4 items-end md:col-span-2">
            <div>
              <label className="text-[9px] font-mono uppercase text-muted-foreground block mb-2">Kun boshlanishi (soat 0–23)</label>
              <input
                type="number"
                min={0}
                max={23}
                value={kp.dayStartHour}
                onChange={(e) => patchKiosk({ dayStartHour: Number(e.target.value) })}
                className="w-24 bg-background border border-border rounded-xl px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-[9px] font-mono uppercase text-muted-foreground block mb-2">Kun tugashi (eksklyuziv)</label>
              <input
                type="number"
                min={0}
                max={23}
                value={kp.dayEndHour}
                onChange={(e) => patchKiosk({ dayEndHour: Number(e.target.value) })}
                className="w-24 bg-background border border-border rounded-xl px-3 py-2 text-sm"
              />
            </div>
          </div>

          <label className="flex items-start gap-3 cursor-pointer rounded-xl border border-border p-4 hover:bg-muted/30 transition">
            <input
              type="checkbox"
              className="mt-1"
              checked={kp.hourlyCheckEnabled}
              onChange={(e) => patchKiosk({ hourlyCheckEnabled: e.target.checked })}
            />
            <span className="text-xs leading-relaxed">
              <span className="font-bold uppercase tracking-wide text-[10px] block text-primary">Har 30 daqiqada tekshiruv</span>
              Salomdan keyin kayfiyat va rejani so‘raydi; Web Speech tinglash (Chrome). Oxirgi savildan kamida <strong className="text-foreground">30 daqiqa</strong> o‘tgach qayta so‘raladi.
            </span>
          </label>

          <label className="flex items-start gap-3 cursor-pointer rounded-xl border border-border p-4 hover:bg-muted/30 transition">
            <input
              type="checkbox"
              className="mt-1"
              checked={kp.hourlyUseOpenAI}
              onChange={(e) => patchKiosk({ hourlyUseOpenAI: e.target.checked })}
            />
            <span className="text-xs leading-relaxed">
              <span className="font-bold uppercase tracking-wide text-[10px] block text-primary">OpenAI bilan gapirish</span>
              `.env` ichida `VITE_OPENAI_API_KEY` bo‘lsa va tanlangan bo‘lsa, keyingi savol qisqa yangilanadi (API xarajati).
            </span>
          </label>
        </div>
      </section>
    </div>
  );
}

function MediaView({
  playlist,
  storageKey,
  mediaBucket,
  onMediaBucketChange,
  onRefresh,
}: {
  playlist: PlaylistItem[];
  storageKey: string;
  mediaBucket: "main" | "day";
  onMediaBucketChange: (b: "main" | "day") => void;
  onRefresh: () => void;
}) {
  const [preview, setPreview] = useState<{ url: string; kind: "video" | "image" } | null>(null);
  const [uploading, setUploading] = useState(false);

  const setImageDurationSeconds = (id: string, sec: number) => {
    const secClamped = Math.min(120, Math.max(2, sec));
    const np = playlist.map((p) => (p.id === id ? { ...p, duration: secClamped * 1000 } : p));
    persistPlaylist(np, storageKey);
    onRefresh();
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    setUploading(true);
    try {
      const items = [...playlist];
      for (const file of Array.from(files)) {
        const isVideo = file.type.startsWith("video/");
        const isImage = file.type.startsWith("image/");

        if (!isVideo && !isImage) continue;

        const fileId = crypto.randomUUID();
        await saveFile(fileId, file);

        let poster: string | undefined;
        if (isVideo) {
          poster = (await captureVideoPosterDataUrl(file)) ?? undefined;
        }

        items.push({
          id: crypto.randomUUID(),
          url: fileId,
          name: file.name,
          type: isVideo ? "video" : "image",
          ...(isVideo ? { poster } : { duration: 5000 }),
        });
      }
      persistPlaylist(items, storageKey);
      onRefresh();
    } catch (err) {
      console.error(err);
      alert("Yuklashda xato yuz berdi. Iltimos qaytadan urining.");
    } finally {
      setUploading(false);
    }
  };

  const handlePreview = async (item: PlaylistItem) => {
    if (!item.url) return;
    if (item.url.startsWith("http")) {
      setPreview({ url: item.url, kind: item.type === "video" ? "video" : "image" });
      return;
    }
    const blob = await getFile(item.url);
    if (blob) {
      const url = URL.createObjectURL(blob);
      setPreview({ url, kind: item.type === "video" ? "video" : "image" });
    } else {
      alert("Fayl topilmadi.");
    }
  };

  const moveItem = (index: number, direction: "up" | "down") => {
    const newPlaylist = [...playlist];
    const newIndex = direction === "up" ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= newPlaylist.length) return;

    [newPlaylist[index], newPlaylist[newIndex]] = [newPlaylist[newIndex], newPlaylist[index]];
    persistPlaylist(newPlaylist, storageKey);
    onRefresh();
  };

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-3xl font-bold font-display tracking-tight uppercase">Media Boshqaruvchisi</h2>
          <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest mt-1">
            {playlist.length} ta element · ketma-ketlik ·{" "}
            {mediaBucket === "main" ? "Asosiy kiosk playlist" : "Kun sloti (jadval yoqilganda)"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex rounded-xl border border-border overflow-hidden bg-background/80">
            <button
              type="button"
              onClick={() => onMediaBucketChange("main")}
              className={`px-4 py-2 text-[10px] font-bold uppercase tracking-wider ${mediaBucket === "main" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted/50"}`}
            >
              Asosiy
            </button>
            <button
              type="button"
              onClick={() => onMediaBucketChange("day")}
              className={`px-4 py-2 text-[10px] font-bold uppercase tracking-wider ${mediaBucket === "day" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted/50"}`}
            >
              Kun sloti
            </button>
          </div>
          <label
            className={`flex items-center gap-3 px-8 py-4 bg-primary text-primary-foreground rounded-xl text-[10px] font-bold uppercase tracking-[0.2em] cursor-pointer hover:brightness-110 transition shadow-xl shadow-primary/20 ${uploading ? "opacity-50 cursor-wait" : ""}`}
          >
            <Upload className="h-4 w-4" /> {uploading ? "Yuklanmoqda..." : "Yangi Media Qo‘shish"}
            <input type="file" hidden onChange={handleUpload} accept="video/*,image/*" multiple disabled={uploading} />
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {playlist.map((item, idx) => (
          <div key={item.id} className="glass rounded-2xl overflow-hidden border-border hover:border-primary/30 transition-all duration-500 group shadow-lg flex flex-col">
            <div
              className="aspect-video bg-black flex items-center justify-center relative cursor-pointer"
              onClick={() => void handlePreview(item)}
            >
              <div className="absolute top-3 left-3 px-2 py-1 rounded bg-black/60 text-[9px] font-mono text-primary border border-primary/20 backdrop-blur z-10">
                {idx + 1}.{" "}
                {item.type === "video" ? "VIDEO" : item.type === "image" ? "RASM" : "KARTOCHKA"}
              </div>
              {item.type === "video" && item.poster && (
                <img
                  src={item.poster}
                  alt=""
                  className="absolute inset-0 h-full w-full object-cover opacity-45 group-hover:opacity-70 transition-opacity"
                />
              )}
              <div className="absolute top-3 right-3 flex flex-col gap-1 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    moveItem(idx, "up");
                  }}
                  disabled={idx === 0}
                  className="p-1.5 bg-black/60 rounded border border-white/10 text-white hover:bg-primary disabled:opacity-30"
                >
                  <Plus className="h-3 w-3 rotate-180 transform -scale-y-100" />
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    moveItem(idx, "down");
                  }}
                  disabled={idx === playlist.length - 1}
                  className="p-1.5 bg-black/60 rounded border border-white/10 text-white hover:bg-primary disabled:opacity-30"
                >
                  <Plus className="h-3 w-3" />
                </button>
              </div>

              {item.type === "video" ? (
                <Play className="relative z-[1] h-10 w-10 text-primary/20 group-hover:text-primary transition-all duration-500 group-hover:scale-110" />
              ) : (
                <ImageIcon className="relative z-[1] h-10 w-10 text-primary/20 group-hover:text-primary transition-all duration-500 group-hover:scale-110" />
              )}

              <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-60 pointer-events-none" />
              <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                <span className="bg-primary/90 text-primary-foreground text-[8px] font-bold uppercase px-3 py-1.5 rounded-full shadow-lg">
                  Ko'rish
                </span>
              </div>
            </div>
            <div className="p-5 bg-card border-t border-border flex-1 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="truncate flex-1 min-w-0">
                  <div className="text-xs font-bold truncate text-foreground/90">{item.name || "Media Element"}</div>
                  <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mt-1">
                    Ketma-ketlikda #{idx + 1}
                    {item.type === "video" && <span className="text-primary/70"> · tugaguncha ijro</span>}
                  </div>
                </div>
                <button 
                  type="button"
                  onClick={async (e) => {
                    e.stopPropagation();
                    if (!confirm("Ushbu elementni o'chirmoqchimisiz?")) return;
                    if (item.url && !item.url.startsWith("http")) await deleteFile(item.url);
                    const np = playlist.filter((p) => p.id !== item.id);
                    persistPlaylist(np, storageKey);
                    onRefresh();
                  }}
                  className="flex-shrink-0 p-3 text-muted-foreground/30 hover:text-destructive hover:bg-destructive/10 rounded-xl transition-all duration-300"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              {item.type === "image" && (
                <div className="flex items-center gap-2 pt-2 border-t border-border/80">
                  <label className="text-[9px] font-mono uppercase tracking-widest text-muted-foreground whitespace-nowrap">
                    Slid (sek)
                  </label>
                  <input
                    type="number"
                    key={item.id}
                    min={2}
                    max={120}
                    defaultValue={(item.duration ?? 5000) / 1000}
                    onBlur={(e) => setImageDurationSeconds(item.id, Number(e.target.value))}
                    className="w-full max-w-[5rem] bg-background border border-border rounded-lg px-2 py-1.5 text-[11px] font-mono outline-none focus:border-primary"
                  />
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <AnimatePresence>
        {preview && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 p-10 backdrop-blur-md"
            onClick={() => {
              if (preview.url.startsWith("blob:")) URL.revokeObjectURL(preview.url);
              setPreview(null);
            }}
          >
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="relative max-w-5xl w-full aspect-video rounded-3xl overflow-hidden border border-white/10 shadow-2xl shadow-primary/20"
              onClick={e => e.stopPropagation()}
            >
              {preview.kind === "video" ? (
                <video src={preview.url} controls autoPlay muted playsInline className="w-full h-full object-contain bg-black" />
              ) : (
                <img src={preview.url} alt="" className="w-full h-full object-contain bg-black" />
              )}
              <button 
                type="button"
                onClick={() => {
                  if (preview.url.startsWith("blob:")) URL.revokeObjectURL(preview.url);
                  setPreview(null);
                }}
                className="absolute top-6 right-6 p-4 bg-black/50 text-white hover:bg-black/80 rounded-2xl border border-white/10 transition backdrop-blur-xl"
              >
                <X className="w-6 h-6" />
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function LogsView({ logs, onClear }: { logs: any[]; onClear: () => void }) {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold font-display tracking-tight uppercase">Tizim Loglari</h2>
        <button onClick={onClear} className="flex items-center gap-2 px-4 py-2 text-[10px] font-mono uppercase tracking-widest text-muted-foreground hover:text-destructive transition">
          <Eraser className="h-3.5 w-3.5" /> Xotirani Tozalash
        </button>
      </div>
      <div className="glass-strong rounded-2xl border-border overflow-hidden shadow-2xl">
        <div className="max-h-[70vh] overflow-y-auto custom-scrollbar font-mono text-[10px] divide-y divide-border">
          {logs.map((log, i) => (
            <div key={i} className="px-8 py-4 flex items-center gap-8 hover:bg-primary/[0.02] transition-colors">
              <span className="text-primary/20 tabular-nums w-20">{new Date(log.timestamp).toLocaleTimeString([], { hour12: false })}</span>
              <span className={`font-bold uppercase tracking-[0.2em] w-24 ${log.personId ? "text-primary" : "text-destructive/70"}`}>
                {log.personId ? "TASDIQLANDI" : "NOMA'LUM"}
              </span>
              <span className="flex-1 text-muted-foreground truncate">
                Shaxs [{log.name}] Terminal_01 orqali aniqlandi. Aniqlik {(log.confidence*100).toFixed(2)}%.
              </span>
              <span className="text-primary/40 px-2 py-0.5 rounded border border-primary/10">BARQAROR</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AttendanceHeatmap({ logs }: { logs: RecognitionLog[] }) {
  const days = useMemo(() => {
    const today = startOfToday();
    const start = subMonths(today, 12);
    const interval = eachDayOfInterval({ start, end: today });
    
    return interval.map(day => {
      const count = logs.filter(l => isSameDay(new Date(l.timestamp), day)).length;
      let level = 0;
      if (count > 0) level = 1;
      if (count > 5) level = 2;
      if (count > 10) level = 3;
      if (count > 20) level = 4;
      
      return { day, count, level };
    });
  }, [logs]);

  const months = useMemo(() => {
    const labels: string[] = [];
    const today = startOfToday();
    for(let i=11; i>=0; i--) {
      labels.push(format(subMonths(today, i), "MMM"));
    }
    return labels;
  }, []);

  return (
    <div className="glass-strong p-8 rounded-3xl border-border bg-card/40 shadow-2xl">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xs font-mono uppercase tracking-[0.3em] text-muted-foreground/60 flex items-center gap-2">
          <Activity className="h-3 w-3 text-primary" /> Oxirgi 12 oylik faollik
        </h3>
        <div className="flex items-center gap-2 text-[9px] font-mono text-muted-foreground uppercase">
          <span>Kam</span>
          {[0, 1, 2, 3, 4].map(l => (
            <div 
              key={l} 
              className={`w-2.5 h-2.5 rounded-[2px] ${
                l === 0 ? "bg-white/5" : 
                l === 1 ? "bg-emerald-900/40" : 
                l === 2 ? "bg-emerald-700/60" : 
                l === 3 ? "bg-emerald-500/80" : "bg-emerald-400"
              }`} 
            />
          ))}
          <span>Ko'p</span>
        </div>
      </div>

      <div className="flex flex-col gap-2 overflow-x-auto pb-4 scrollbar-hide">
        <div className="flex gap-[18px] mb-2 pl-10">
          {months.map((m, i) => (
            <div key={i} className="text-[9px] font-mono text-muted-foreground/40 uppercase min-w-[42px]">{m}</div>
          ))}
        </div>
        
        <div className="flex gap-3">
          <div className="flex flex-col justify-between py-1 text-[8px] font-mono text-muted-foreground/30 uppercase h-[105px] w-8">
            <span>Du</span>
            <span>Ch</span>
            <span>Ju</span>
          </div>
          
          <div className="flex flex-wrap gap-[3px] h-[105px] flex-col content-start">
            {days.map((d, i) => (
              <div 
                key={i}
                title={`${format(d.day, "yyyy-MM-dd")}: ${d.count} ta faollik`}
                className={`w-3 h-3 rounded-[2px] transition-all hover:scale-125 hover:z-10 cursor-pointer ${
                  d.level === 0 ? "bg-white/5 hover:bg-white/10" : 
                  d.level === 1 ? "bg-emerald-900/40" : 
                  d.level === 2 ? "bg-emerald-700/60" : 
                  d.level === 3 ? "bg-emerald-500/80" : "bg-emerald-400"
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function AttendanceView({ logs, people }: { logs: RecognitionLog[]; people: Person[] }) {
  const attendanceData = useMemo(() => {
    const data: any[] = [];
    people.forEach(p => {
      const pLogs = logs.filter(l => l.personId === p.id);
      if (pLogs.length === 0) return;

      const sorted = pLogs.sort((a, b) => a.timestamp - b.timestamp);
      const firstArrived = sorted[0];
      const lastSeen = sorted[sorted.length - 1];
      
      const firstTime = new Date(firstArrived.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
      const lastTime = new Date(lastSeen.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
      
      // Calculate total hours (simulation based on first/last seen)
      const diffMs = lastSeen.timestamp - firstArrived.timestamp;
      const hours = Math.floor(diffMs / (1000 * 60 * 60));
      const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

      data.push({
        id: p.id,
        name: p.name,
        role: p.role,
        avatar: p.avatar,
        firstArrived: firstTime,
        lastSeen: lastTime,
        duration: `${hours}s ${mins}d`,
        timestamp: firstArrived.timestamp,
        status: "Active"
      });
    });
    return data.sort((a, b) => a.timestamp - b.timestamp);
  }, [logs, people]);

  const exportCSV = () => {
    const header = "Ism,Lavozim,Kelgan vaqti,Ketgan vaqti,Davomiyligi\n";
    const rows = attendanceData.map(d => `${d.name},${d.role},${d.firstArrived},${d.lastSeen},${d.duration}`).join("\n");
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `attendance_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold font-display tracking-tight uppercase">Davomat Tizimi</h2>
          <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest mt-1">Bugungi ish grafigi tahlili</p>
        </div>
        <button 
          onClick={exportCSV}
          className="px-6 py-3 bg-primary/10 text-primary border border-primary/20 rounded-xl text-[10px] font-bold uppercase tracking-widest hover:bg-primary/20 transition"
        >
          CSV EKSPORT
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="glass p-6 rounded-2xl border-border bg-card/40">
          <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mb-2">O'rtacha Kelish</div>
          <div className="text-3xl font-display font-bold text-primary">09:12</div>
        </div>
        <div className="glass p-6 rounded-2xl border-border bg-card/40">
          <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mb-2">Eng Erta Kelgan</div>
          <div className="text-xl font-bold truncate text-foreground/80">{attendanceData[0]?.name || "Noma'lum"}</div>
        </div>
        <div className="glass p-6 rounded-2xl border-border bg-card/40">
          <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mb-2">Kechikkanlar</div>
          <div className="text-3xl font-display font-bold text-destructive/60">02</div>
        </div>
        <div className="glass p-6 rounded-2xl border-border bg-card/40">
          <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mb-2">Faol Xodimlar</div>
          <div className="text-3xl font-display font-bold text-emerald-500">{attendanceData.length}</div>
        </div>
      </div>

      <AttendanceHeatmap logs={logs} />

      <div className="glass-strong rounded-2xl border-border overflow-hidden shadow-2xl">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-primary/5 border-b border-border text-[10px] uppercase tracking-[0.3em] text-muted-foreground font-mono">
              <th className="px-8 py-5">Xodim</th>
              <th className="px-8 py-5">Kelgan Vaqti</th>
              <th className="px-8 py-5">Oxirgi Ko'rilgan</th>
              <th className="px-8 py-5">Davomiyligi</th>
              <th className="px-8 py-5 text-right">Holati</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {attendanceData.map((d) => (
              <tr key={d.id} className="hover:bg-primary/[0.02] transition-colors group">
                <td className="px-8 py-5">
                  <div className="flex items-center gap-4">
                    <img src={d.avatar} className="h-10 w-10 rounded-xl object-cover border border-border" />
                    <div>
                      <div className="font-bold text-sm text-foreground/90">{d.name}</div>
                      <div className="text-[9px] font-mono text-muted-foreground uppercase">{d.role}</div>
                    </div>
                  </div>
                </td>
                <td className="px-8 py-5 font-mono text-sm text-primary font-bold">{d.firstArrived}</td>
                <td className="px-8 py-5 font-mono text-sm text-muted-foreground">{d.lastSeen}</td>
                <td className="px-8 py-5 font-mono text-xs">{d.duration}</td>
                <td className="px-8 py-5 text-right">
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 text-[9px] font-bold uppercase border border-emerald-500/20">O'z vaqtida</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SimpleCamera() {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    let stream: MediaStream | null = null;
    navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
      .then(s => { 
        stream = s;
        if(ref.current) ref.current.srcObject = s; 
      })
      .catch(err => console.error("[AdminCamera] Error:", err));
      
    return () => {
      stream?.getTracks().forEach(t => t.stop());
    };
  }, []);
  return <video ref={ref} autoPlay muted playsInline className="w-full h-full object-cover -scale-x-100" />;
}
