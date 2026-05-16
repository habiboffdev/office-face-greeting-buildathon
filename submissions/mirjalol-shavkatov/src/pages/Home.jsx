import { Link } from "react-router-dom";
import { Monitor, Settings, ArrowRight, Users, Video, Camera, LogIn, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/AuthContext";
import TrialBanner from "@/components/TrialBanner";

const features = [
  { icon: Video, title: "Video Playlist", desc: "Loop promo & branding videos seamlessly at your entrance" },
  { icon: Camera, title: "Face Recognition", desc: "Instant identification via camera — no action needed" },
  { icon: Users, title: "Personalized Greetings", desc: "Custom welcome message for every recognized employee" },
];

export default function Home() {
  const { user, isLoadingAuth, logout, navigateToLogin } = useAuth();

  const handleSignOut = () => logout();
  const handleSignIn = () => navigateToLogin();
  const isAdmin = user?.role === "admin";

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Top nav bar */}
      <nav className="flex items-center justify-between px-8 py-5 border-b border-border/50">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow">
            <Monitor className="w-5 h-5 text-primary-foreground" />
          </div>
          <span className="text-base font-display font-semibold text-foreground">
            facegreet<span className="text-primary">.uz</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isAdmin && (
            <Link to="/admin">
              <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground hover:text-foreground">
                <Settings className="w-4 h-4" />
                Admin
              </Button>
            </Link>
          )}
          {!user && !isLoadingAuth && (
            <Button variant="outline" size="sm" className="gap-1.5" onClick={handleSignIn}>
              <LogIn className="w-4 h-4" />
              Sign In
            </Button>
          )}
          {user && (
            <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground hover:text-foreground" onClick={handleSignOut}>
              <LogOut className="w-4 h-4" />
              Sign Out
            </Button>
          )}

        </div>
      </nav>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-20 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-medium mb-8">
          <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
          Office Face Recognition System
        </div>

        <h1 className="text-5xl md:text-6xl font-display font-medium text-foreground leading-tight mb-5 max-w-2xl">
          A smarter way to<br />
          <span className="text-primary">welcome your team</span>
        </h1>

        <p className="text-muted-foreground text-lg leading-relaxed max-w-md mb-10">
          Display promo videos at your office entrance and automatically greet recognized employees with a personalized welcome.
        </p>

        {/* Trial Banner */}
        {user && (
          <div className="w-full max-w-md mb-6">
            <TrialBanner />
          </div>
        )}

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row gap-3 mb-20">
          <Link to="/display">
            <Button size="lg" className="gap-2 px-8 shadow-lg shadow-primary/20">
              <Monitor className="w-5 h-5" />
              Launch Display
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
          {isAdmin && (
            <Link to="/admin">
              <Button size="lg" variant="outline" className="gap-2 px-8">
                <Settings className="w-4 h-4" />
                Admin Panel
              </Button>
            </Link>
          )}
        </div>

        {/* Feature cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl w-full">
          {features.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="bg-card border border-border rounded-2xl p-6 text-left hover:border-primary/30 hover:shadow-md transition-all duration-200">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                <Icon className="w-5 h-5 text-primary" />
              </div>
              <h3 className="font-semibold text-sm text-foreground mb-1.5">{title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center py-5 text-xs text-muted-foreground border-t border-border/50">
        facegreet.uz — Office Face Recognition Platform
      </footer>
    </div>
  );
}