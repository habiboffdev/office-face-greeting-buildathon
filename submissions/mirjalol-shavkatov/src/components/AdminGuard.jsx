import { ShieldX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/AuthContext";

export default function AdminGuard({ children }) {
  const { user, isLoadingAuth } = useAuth();

  const status = isLoadingAuth ? "loading" : (user?.role === "admin" ? "allowed" : "denied");

  if (status === "loading") {
    return (
      <div className="fixed inset-0 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-800 rounded-full animate-spin" />
      </div>
    );
  }

  if (status === "denied") {
    return (
      <div className="fixed inset-0 flex flex-col items-center justify-center gap-4 text-center px-6">
        <ShieldX className="w-14 h-14 text-destructive opacity-60" />
        <h1 className="text-2xl font-semibold">Access Denied</h1>
        <p className="text-muted-foreground max-w-sm">
          This page is restricted to administrators only. Please contact the system admin if you need access.
        </p>
        <Button variant="outline" onClick={() => window.location.href = "/"}>Go Home</Button>
      </div>
    );
  }

  return children;
}