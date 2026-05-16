import { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Clock, Send, CheckCircle, ShieldAlert } from "lucide-react";
import { useAuth } from "@/lib/AuthContext";

function getTimeLeft(expiresAt) {
  const diff = new Date(expiresAt) - new Date();
  if (diff <= 0) return null;
  const hours = Math.floor(diff / 1000 / 60 / 60);
  const mins = Math.floor((diff / 1000 / 60) % 60);
  return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
}

export default function TrialBanner() {
  const { user } = useAuth();
  const [timeLeft, setTimeLeft] = useState(null);
  const [trialExpired, setTrialExpired] = useState(false);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [alreadyRequested, setAlreadyRequested] = useState(false);

  useEffect(() => {
    if (!user?.trial_expires_at) return;
    const left = getTimeLeft(user.trial_expires_at);
    if (left) {
      setTimeLeft(left);
      const interval = setInterval(() => {
        const l = getTimeLeft(user.trial_expires_at);
        if (!l) { setTimeLeft(null); setTrialExpired(true); clearInterval(interval); }
        else setTimeLeft(l);
      }, 60000);
      return () => clearInterval(interval);
    } else {
      setTrialExpired(true);
    }
  }, [user]);

  useEffect(() => {
    if (!trialExpired || !user) return;
    // Check if already requested today
    const today = new Date().toISOString().split("T")[0];
    base44.entities.TrialRequest.filter({ user_email: user.email, requested_date: today })
      .then((reqs) => { if (reqs.length > 0) setAlreadyRequested(true); });
  }, [trialExpired, user]);

  const handleSubmit = async () => {
    if (!user) return;
    setSubmitting(true);
    const today = new Date().toISOString().split("T")[0];
    await base44.entities.TrialRequest.create({
      user_email: user.email,
      user_name: user.full_name || user.email,
      message: message.trim(),
      status: "pending",
      requested_date: today,
    });
    setSubmitting(false);
    setSubmitted(true);
    setAlreadyRequested(true);
  };

  // Don't show if no user or permanent admin (no trial_expires_at set)
  if (!user || (!user.trial_expires_at && user.role === "admin")) return null;
  // Don't show if trial is active and role is still admin
  if (!trialExpired && user.role === "admin" && timeLeft) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
        <Clock className="w-4 h-4 text-amber-500 flex-shrink-0" />
        <span>Your free admin trial expires in <strong>{timeLeft}</strong>. Enjoy exploring the platform!</span>
      </div>
    );
  }

  // Trial expired, role is user — show request form
  if (user.role !== "admin") {
    if (submitted || alreadyRequested) {
      return (
        <div className="flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
          <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
          <span>Your access request has been sent. You can submit another request tomorrow.</span>
        </div>
      );
    }
    return (
      <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-3">
        <div className="flex items-center gap-2 text-slate-700">
          <ShieldAlert className="w-4 h-4 text-slate-500" />
          <span className="font-medium text-sm">Your 2-day trial has ended</span>
        </div>
        <p className="text-xs text-slate-500">You now have limited access. Send a request to the admin to regain full access.</p>
        <Textarea
          placeholder="Optional: tell the admin why you need access..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className="text-sm h-20 resize-none"
        />
        <Button size="sm" onClick={handleSubmit} disabled={submitting} className="gap-2">
          <Send className="w-3.5 h-3.5" />
          {submitting ? "Sending..." : "Request Access"}
        </Button>
      </div>
    );
  }

  return null;
}