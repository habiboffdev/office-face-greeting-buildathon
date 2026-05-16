import { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import { useCompany } from "@/lib/CompanyContext";
import { startOfDay, formatDistanceToNow, parseISO } from "date-fns";
import { RefreshCw, UserCheck, Clock, Building2, PartyPopper } from "lucide-react";

export default function WhosInDashboard() {
  const { activeCompany } = useCompany();
  const [logs, setLogs] = useState([]);
  const [employees, setEmployees] = useState({});
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState(new Date());

  const load = async () => {
    if (!activeCompany) return;
    setLoading(true);
    const [allLogs, allEmps] = await Promise.all([
      base44.entities.RecognitionLog.filter({ company_id: activeCompany.id }, "-created_date", 500),
      base44.entities.Employee.filter({ company_id: activeCompany.id, is_active: true }),
    ]);

    // Build employee map for photo lookups
    const empMap = {};
    allEmps.forEach((e) => { empMap[e.id] = e; });
    setEmployees(empMap);

    // Filter to today only
    const todayStart = startOfDay(new Date());
    const todayLogs = allLogs.filter((l) => l.created_date && new Date(l.created_date + "Z") >= todayStart);

    // Keep only the LATEST log per employee
    const seen = {};
    todayLogs.forEach((l) => {
      if (!seen[l.employee_id] || new Date(l.created_date + "Z") > new Date(seen[l.employee_id].created_date + "Z")) {
        seen[l.employee_id] = l;
      }
    });

    const unique = Object.values(seen).sort((a, b) =>
      new Date(b.created_date + "Z") - new Date(a.created_date + "Z")
    );

    setLogs(unique);
    setLastRefreshed(new Date());
    setLoading(false);
  };

  useEffect(() => {
    if (activeCompany) {
      load();
      const interval = setInterval(load, 30000);
      return () => clearInterval(interval);
    }
  }, [activeCompany]);

  // Group by department
  const byDept = logs.reduce((acc, l) => {
    const dept = l.department || "Other";
    if (!acc[dept]) acc[dept] = [];
    acc[dept].push(l);
    return acc;
  }, {});

  return (
    <div>
      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold font-display">Who's In Today</h2>
          <p className="text-sm text-muted-foreground">
            {logs.length} {logs.length === 1 ? "person" : "people"} recognized •{" "}
            <span className="text-xs">
              Updated {formatDistanceToNow(lastRefreshed, { addSuffix: true })}
            </span>
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted text-muted-foreground hover:text-foreground text-sm transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {loading && logs.length === 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-muted rounded-xl h-32 animate-pulse" />
          ))}
        </div>
      ) : logs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground gap-3">
          <UserCheck className="w-10 h-10 opacity-30" />
          <p className="font-medium">No one recognized yet today</p>
          <p className="text-sm">Recognitions will appear here as people arrive</p>
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(byDept).map(([dept, deptLogs]) => (
            <div key={dept}>
              <div className="flex items-center gap-2 mb-3">
                <Building2 className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-medium text-muted-foreground uppercase tracking-wide">{dept}</span>
                <span className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded-full">{deptLogs.length}</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6 gap-4">
                {deptLogs.map((log) => {
                  const emp = employees[log.employee_id];
                  return (
                    <EmployeeCard key={log.employee_id} log={log} employee={emp} />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EmployeeCard({ log, employee }) {
  const photoUrl = employee?.photo_url;
  const position = employee?.position;
  const timeAgo = log.created_date
    ? formatDistanceToNow(new Date(log.created_date + "Z"), { addSuffix: true })
    : null;

  return (
    <div className="bg-card border border-border rounded-xl p-4 flex flex-col items-center text-center gap-2 hover:shadow-md transition-shadow">
      <div className="relative">
        {photoUrl ? (
          <img
            src={photoUrl}
            alt={log.employee_name}
            className="w-14 h-14 rounded-full object-cover border-2 border-green-400/60"
          />
        ) : (
          <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center border-2 border-green-400/60">
            <span className="text-xl font-semibold text-muted-foreground">
              {log.employee_name?.charAt(0).toUpperCase()}
            </span>
          </div>
        )}
        {/* Green "in office" dot */}
        <span className="absolute bottom-0 right-0 w-3.5 h-3.5 rounded-full bg-green-500 border-2 border-card" />
        {log.is_birthday && (
          <span className="absolute -top-1 -right-1 text-sm" title="Birthday!">🎂</span>
        )}
      </div>
      <div className="min-w-0 w-full">
        <p className="text-sm font-medium truncate leading-tight">{log.employee_name}</p>
        {position && <p className="text-xs text-muted-foreground truncate">{position}</p>}
      </div>
      {timeAgo && (
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Clock className="w-3 h-3" />
          {timeAgo}
        </div>
      )}
    </div>
  );
}