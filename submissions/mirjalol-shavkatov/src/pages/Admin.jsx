import { useState } from "react";
import { Monitor, Users, Video, CalendarDays, Megaphone, ExternalLink, Settings, BarChart2, UserCheck, Download, Ticket } from "lucide-react";
import { Link } from "react-router-dom";
import WhosInDashboard from "@/components/admin/WhosInDashboard";
import EmployeeManager from "@/components/admin/EmployeeManager";
import VideoManager from "@/components/admin/VideoManager";
import MeetingManager from "@/components/admin/MeetingManager";
import AnnouncementManager from "@/components/admin/AnnouncementManager";
import CompanySettingsManager from "@/components/admin/CompanySettingsManager";
import TrialRequestsManager from "@/components/admin/TrialRequestsManager";
import { Button } from "@/components/ui/button";
import AdminGuard from "@/components/AdminGuard";
import ThemeToggle from "@/components/ThemeToggle";
import OnboardingWizard from "@/components/onboarding/OnboardingWizard";
import AIChat from "@/components/ai/AIChat";
import { CompanyProvider, useCompany } from "@/lib/CompanyContext";
import CompanySwitcher from "@/components/admin/CompanySwitcher";
import NoCompanyScreen from "@/components/admin/NoCompanyScreen";

const TAB_IDS = ["whosin", "employees", "videos", "meetings", "announcements", "requests", "settings"];
const TAB_LABELS = { whosin: "Who's In", employees: "Employees", videos: "Videos", meetings: "Meetings", announcements: "Announcements", requests: "Requests", settings: "Settings" };

function TabIcon({ id }) {
  if (id === "whosin") return <UserCheck className="w-4 h-4" />;
  if (id === "employees") return <Users className="w-4 h-4" />;
  if (id === "videos") return <Video className="w-4 h-4" />;
  if (id === "meetings") return <CalendarDays className="w-4 h-4" />;
  if (id === "announcements") return <Megaphone className="w-4 h-4" />;
  if (id === "settings") return <Settings className="w-4 h-4" />;
  if (id === "requests") return <Ticket className="w-4 h-4" />;
  return null;
}

function AdminInner() {
  const { activeCompany, loading } = useCompany();
  const [activeTab, setActiveTab] = useState("whosin");

  if (loading) return (
    <div className="fixed inset-0 flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-800 rounded-full animate-spin" />
    </div>
  );

  if (!activeCompany) return <NoCompanyScreen />;

  const handleAttendanceExport = async (format) => {
    const { base44 } = await import("@/api/base44Client");
    const logs = await base44.entities.RecognitionLog.filter({ company_id: activeCompany.id }, "-created_date", 1000);
    
    const grouped = {};
    logs.forEach(log => {
      const date = new Date(log.created_date).toLocaleDateString();
      if (!grouped[date]) grouped[date] = [];
      grouped[date].push(log);
    });

    if (format === 'csv') {
      let csv = 'Date,Name,Department,Time\n';
      Object.entries(grouped).forEach(([date, items]) => {
        items.forEach(log => {
          const time = new Date(log.created_date).toLocaleTimeString();
          csv += `${date},${log.employee_name},${log.department || 'N/A'},${time}\n`;
        });
      });
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `attendance-${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
    } else {
      const { jsPDF } = await import('jspdf');
      const doc = new jsPDF();
      doc.setFontSize(16);
      doc.text('Attendance Report', 14, 15);
      doc.setFontSize(10);
      
      let y = 30;
      Object.entries(grouped).forEach(([date, items]) => {
        doc.setFont(undefined, 'bold');
        doc.text(date, 14, y);
        y += 7;
        doc.setFont(undefined, 'normal');
        items.forEach(log => {
          const time = new Date(log.created_date).toLocaleTimeString();
          doc.text(`${log.employee_name} (${log.department || 'N/A'}) - ${time}`, 20, y);
          y += 6;
          if (y > 270) {
            doc.addPage();
            y = 15;
          }
        });
        y += 3;
      });
      doc.save(`attendance-${new Date().toISOString().split('T')[0]}.pdf`);
    }
  };

  return (
    <AdminGuard>
    <div className="min-h-screen bg-background">
      <OnboardingWizard />
      <AIChat />
      {/* Header */}
      <header className="border-b border-border bg-card sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Monitor className="w-4 h-4 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-foreground font-display">FaceGreet</h1>
              <p className="text-xs text-muted-foreground">Admin Panel</p>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            <CompanySwitcher />
            <Link to="/analytics">
              <Button variant="outline" size="sm" className="gap-2">
                <BarChart2 className="w-4 h-4" />
                Analytics
              </Button>
            </Link>
            <Button variant="outline" size="sm" className="gap-2" onClick={() => window.open(`/display?company=${activeCompany.id}`, "_blank")}>
              <ExternalLink className="w-4 h-4" />
              Open Display
            </Button>
            {activeTab === "whosin" && (
              <div className="flex gap-1">
                <Button variant="outline" size="sm" className="gap-2" onClick={() => handleAttendanceExport('csv')}>
                  <Download className="w-4 h-4" />
                  CSV
                </Button>
                <Button variant="outline" size="sm" className="gap-2" onClick={() => handleAttendanceExport('pdf')}>
                  <Download className="w-4 h-4" />
                  PDF
                </Button>
              </div>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-4 sm:pt-6">
        <div className="flex gap-1 p-1 bg-muted rounded-xl w-full sm:w-fit mb-6 sm:mb-8 overflow-x-auto">
          {TAB_IDS.map((id) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === id
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <TabIcon id={id} />
              {TAB_LABELS[id]}
            </button>
          ))}
        </div>

        {activeTab === "whosin" && <WhosInDashboard />}
        {activeTab === "employees" && <EmployeeManager />}
        {activeTab === "videos" && <VideoManager />}
        {activeTab === "meetings" && <MeetingManager />}
        {activeTab === "announcements" && <AnnouncementManager />}
        {activeTab === "requests" && <TrialRequestsManager />}
        {activeTab === "settings" && <CompanySettingsManager />}
      </div>
    </div>
    </AdminGuard>
  );
}

export default function Admin() {
  return (
    <CompanyProvider>
      <AdminInner />
    </CompanyProvider>
  );
}