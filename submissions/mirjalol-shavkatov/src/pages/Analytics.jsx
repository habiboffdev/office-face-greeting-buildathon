import { useState, useEffect, useMemo } from "react";
import { base44 } from "@/api/base44Client";
import AdminGuard from "@/components/AdminGuard";
import { CompanyProvider, useCompany } from "@/lib/CompanyContext";
import { format, subDays, startOfDay, parseISO, isAfter } from "date-fns";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from "recharts";
import { Users, TrendingUp, Calendar, PartyPopper, ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

const RANGE_OPTIONS = [
  { label: "Last 7 days", days: 7 },
  { label: "Last 30 days", days: 30 },
  { label: "Last 90 days", days: 90 },
];

function StatCard({ icon: Icon, label, value, color = "text-primary" }) {
  return (
    <div className="bg-card border border-border rounded-xl p-5 flex items-center gap-4">
      <div className={`p-3 rounded-lg bg-muted ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold font-display">{value}</p>
      </div>
    </div>
  );
}

function AnalyticsInner() {
  const { activeCompany } = useCompany();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [rangeDays, setRangeDays] = useState(30);

  useEffect(() => {
    if (!activeCompany) return;
    base44.entities.RecognitionLog.filter({ company_id: activeCompany.id }, "-created_date", 2000).then((data) => {
      setLogs(data);
      setLoading(false);
    });
  }, [activeCompany]);

  const cutoff = useMemo(() => startOfDay(subDays(new Date(), rangeDays)), [rangeDays]);

  const filtered = useMemo(
    () => logs.filter((l) => l.created_date && isAfter(parseISO(l.created_date), cutoff)),
    [logs, cutoff]
  );

  // Daily trend
  const dailyData = useMemo(() => {
    const map = {};
    for (let i = rangeDays - 1; i >= 0; i--) {
      const d = format(subDays(new Date(), i), "MMM d");
      map[d] = 0;
    }
    filtered.forEach((l) => {
      const d = format(parseISO(l.created_date), "MMM d");
      if (d in map) map[d] = (map[d] || 0) + 1;
    });
    return Object.entries(map).map(([date, count]) => ({ date, count }));
  }, [filtered, rangeDays]);

  // By department
  const deptData = useMemo(() => {
    const map = {};
    filtered.forEach((l) => {
      const dept = l.department || "Unknown";
      map[dept] = (map[dept] || 0) + 1;
    });
    return Object.entries(map)
      .map(([dept, count]) => ({ dept, count }))
      .sort((a, b) => b.count - a.count);
  }, [filtered]);

  // Peak hours (hourly distribution)
  const hourlyData = useMemo(() => {
    const hours = Array.from({ length: 24 }, (_, i) => i);
    const map = hours.reduce((acc, h) => ({ ...acc, [h]: 0 }), {});
    filtered.forEach((l) => {
      const hour = new Date(l.created_date).getHours();
      map[hour]++;
    });
    return hours.map((h) => ({ 
      hour: `${h.toString().padStart(2, '0')}:00`,
      count: map[h]
    }));
  }, [filtered]);

  // Most active day of week
  const busyDayData = useMemo(() => {
    const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const map = { Sun: 0, Mon: 0, Tue: 0, Wed: 0, Thu: 0, Fri: 0, Sat: 0 };
    filtered.forEach((l) => {
      const d = days[new Date(l.created_date).getDay()];
      map[d]++;
    });
    return days.map((d) => ({ day: d, count: map[d] }));
  }, [filtered]);

  const totalGreetings = filtered.length;
  const birthdayGreetings = filtered.filter((l) => l.is_birthday).length;
  const uniquePeople = new Set(filtered.map((l) => l.employee_id)).size;
  const peakDay = dailyData.reduce((a, b) => (b.count > a.count ? b : a), { date: "-", count: 0 });

  const COLORS = ["#D4AF37", "#f97316", "#3b82f6", "#22c55e", "#a855f7", "#ec4899"];

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-border border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <AdminGuard>
    <div className="min-h-screen bg-background p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <Link to="/admin" className="text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold font-display">Recognition Analytics</h1>
          <p className="text-muted-foreground text-sm">Face recognition activity over time</p>
        </div>
        <div className="ml-auto flex gap-2">
          {RANGE_OPTIONS.map((o) => (
            <button
              key={o.days}
              onClick={() => setRangeDays(o.days)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                rangeDays === o.days
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard icon={TrendingUp} label="Total Greetings" value={totalGreetings} />
        <StatCard icon={Users} label="Unique People" value={uniquePeople} color="text-blue-500" />
        <StatCard icon={Calendar} label="Peak Day" value={peakDay.date} color="text-green-500" />
        <StatCard icon={PartyPopper} label="Birthdays" value={birthdayGreetings} color="text-orange-500" />
      </div>

      {/* Daily trend chart */}
      <div className="bg-card border border-border rounded-xl p-5 mb-6">
        <h2 className="font-semibold mb-4">Daily Greetings</h2>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={dailyData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              interval={rangeDays > 14 ? Math.floor(rangeDays / 10) : 0}
            />
            <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} allowDecimals={false} />
            <Tooltip
              contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }}
              labelStyle={{ color: "hsl(var(--foreground))" }}
            />
            <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} name="Greetings" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
         {/* By department */}
         <div className="bg-card border border-border rounded-xl p-5">
           <h2 className="font-semibold mb-4">By Department</h2>
           {deptData.length === 0 ? (
             <p className="text-muted-foreground text-sm">No data yet</p>
           ) : (
             <ResponsiveContainer width="100%" height={220}>
               <BarChart data={deptData} layout="vertical" margin={{ top: 0, right: 8, left: 8, bottom: 0 }}>
                 <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                 <XAxis type="number" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} allowDecimals={false} />
                 <YAxis dataKey="dept" type="category" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} width={90} />
                 <Tooltip
                   contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }}
                 />
                 <Bar dataKey="count" radius={[0, 4, 4, 0]} name="Greetings">
                   {deptData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                 </Bar>
               </BarChart>
             </ResponsiveContainer>
           )}
         </div>

         {/* By day of week */}
         <div className="bg-card border border-border rounded-xl p-5">
           <h2 className="font-semibold mb-4">Most Active Days of Week</h2>
           <ResponsiveContainer width="100%" height={220}>
             <BarChart data={busyDayData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
               <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
               <XAxis dataKey="day" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
               <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} allowDecimals={false} />
               <Tooltip
                 contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }}
               />
               <Bar dataKey="count" radius={[4, 4, 0, 0]} name="Greetings">
                 {busyDayData.map((entry, i) => (
                   <Cell key={i} fill={entry.count === Math.max(...busyDayData.map(d => d.count)) ? "hsl(var(--primary))" : "hsl(var(--muted))"} />
                 ))}
               </Bar>
             </BarChart>
           </ResponsiveContainer>
         </div>
       </div>

       {/* Peak hours */}
       <div className="bg-card border border-border rounded-xl p-5 mt-6">
         <h2 className="font-semibold mb-4">Peak Hours</h2>
         <ResponsiveContainer width="100%" height={240}>
           <BarChart data={hourlyData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
             <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
             <XAxis dataKey="hour" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} interval={2} />
             <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} allowDecimals={false} />
             <Tooltip
               contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }}
             />
             <Bar dataKey="count" radius={[4, 4, 0, 0]} name="Recognitions">
               {hourlyData.map((entry, i) => (
                 <Cell key={i} fill={entry.count === Math.max(...hourlyData.map(d => d.count)) ? "hsl(var(--primary))" : "hsl(var(--muted))"} />
               ))}
             </Bar>
           </BarChart>
         </ResponsiveContainer>
       </div>
    </div>
    </AdminGuard>
    );
    }

    export default function Analytics() {
    return (
    <CompanyProvider>
     <AnalyticsInner />
    </CompanyProvider>
    );
    }