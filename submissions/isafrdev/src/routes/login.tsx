import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Lock, User, LogIn, ShieldAlert } from "lucide-react";

export const Route = createFileRoute("/login")({
  component: LoginPage,
});

function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    // If already logged in, redirect to admin
    if (localStorage.getItem("visiongate:auth") === "true") {
      navigate({ to: "/admin" });
    }
  }, [navigate]);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (username === "admin" && password === "admin123") {
      localStorage.setItem("visiongate:auth", "true");
      navigate({ to: "/admin" });
    } else {
      setError(true);
      setTimeout(() => setError(false), 2000);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6 font-sans">
      <div className="absolute inset-0 grid-bg opacity-40" />
      
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-strong relative w-full max-w-md overflow-hidden rounded-[2.5rem] border border-white/10 p-1 shadow-2xl"
      >
        <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-primary/10 to-transparent" />
        
        <form onSubmit={handleLogin} className="relative p-10">
          <div className="mb-10 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/20 text-primary shadow-glow">
              <Lock className="h-8 w-8" />
            </div>
            <h1 className="font-display text-3xl font-black tracking-tight text-white uppercase">Admin Portal</h1>
            <p className="mt-2 text-sm text-muted-foreground uppercase tracking-widest opacity-60">Authentication Required</p>
          </div>

          <div className="space-y-4">
            <div className="relative">
              <User className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Login"
                className="w-full rounded-2xl border border-white/10 bg-background/50 py-4 pl-12 pr-4 text-sm font-medium outline-none transition-all focus:border-primary/50 focus:ring-4 focus:ring-primary/10"
                required
              />
            </div>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Parol"
                className="w-full rounded-2xl border border-white/10 bg-background/50 py-4 pl-12 pr-4 text-sm font-medium outline-none transition-all focus:border-primary/50 focus:ring-4 focus:ring-primary/10"
                required
              />
            </div>
          </div>

          {error && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="mt-4 flex items-center gap-2 rounded-xl bg-destructive/10 p-3 text-xs font-bold text-destructive"
            >
              <ShieldAlert className="h-4 w-4" /> LOGIN YOKI PAROL NOTO'G'RI!
            </motion.div>
          )}

          <button
            type="submit"
            className="mt-8 flex w-full items-center justify-center gap-2 rounded-2xl bg-primary py-4 text-sm font-black uppercase tracking-[0.2em] text-primary-foreground shadow-glow transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <LogIn className="h-5 w-5" /> Tizimga kirish
          </button>
        </form>

        <div className="border-t border-white/5 bg-background/40 p-6 text-center">
          <p className="text-[10px] font-mono font-medium uppercase tracking-[0.3em] text-muted-foreground/40">
            VisionGate AI // Secure Terminal
          </p>
        </div>
      </motion.div>

      <style>{`
        .grid-bg {
          background-image: radial-gradient(circle at 2px 2px, rgba(255,255,255,0.05) 1px, transparent 0);
          background-size: 32px 32px;
        }
      `}</style>
    </div>
  );
}
