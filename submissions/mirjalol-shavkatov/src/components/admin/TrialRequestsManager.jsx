import { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CheckCircle, XCircle, Clock, User } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const STATUS_COLORS = {
  pending: "bg-amber-100 text-amber-700 border-amber-200",
  approved: "bg-green-100 text-green-700 border-green-200",
  denied: "bg-red-100 text-red-700 border-red-200",
};

export default function TrialRequestsManager() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const reqs = await base44.entities.TrialRequest.list("-created_date", 50);
    setRequests(reqs);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleApprove = async (req) => {
    // Use backend function (service role) to set role + extend trial
    const users = await base44.entities.User.list();
    const target = users.find(u => u.email === req.user_email);
    if (target) {
      const newExpiry = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();
      await base44.asServiceRole.entities.User.update(target.id, { role: "admin", trial_expires_at: newExpiry });
    }
    await base44.entities.TrialRequest.update(req.id, { status: "approved" });
    load();
  };

  const handleDeny = async (req) => {
    await base44.entities.TrialRequest.update(req.id, { status: "denied" });
    load();
  };

  if (loading) return <div className="text-sm text-muted-foreground p-4">Loading requests...</div>;

  const pending = requests.filter(r => r.status === "pending");
  const others = requests.filter(r => r.status !== "pending");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Access Requests</h2>
        {pending.length > 0 && (
          <Badge className="bg-amber-100 text-amber-700 border-amber-200">{pending.length} pending</Badge>
        )}
      </div>

      {requests.length === 0 && (
        <p className="text-sm text-muted-foreground">No access requests yet.</p>
      )}

      {pending.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Pending</p>
          {pending.map(req => (
            <RequestCard key={req.id} req={req} onApprove={handleApprove} onDeny={handleDeny} />
          ))}
        </div>
      )}

      {others.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">History</p>
          {others.map(req => (
            <RequestCard key={req.id} req={req} />
          ))}
        </div>
      )}
    </div>
  );
}

function RequestCard({ req, onApprove, onDeny }) {
  return (
    <div className="flex items-start gap-3 p-3 border rounded-lg bg-card">
      <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center flex-shrink-0">
        <User className="w-4 h-4 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-sm">{req.user_name}</span>
          <span className="text-xs text-muted-foreground">{req.user_email}</span>
          <Badge className={`text-xs border ${STATUS_COLORS[req.status]}`}>{req.status}</Badge>
        </div>
        {req.message && <p className="text-sm text-muted-foreground mt-1 italic">"{req.message}"</p>}
        <p className="text-xs text-muted-foreground mt-1">
          <Clock className="w-3 h-3 inline mr-1" />
          {req.created_date ? formatDistanceToNow(new Date(req.created_date), { addSuffix: true }) : req.requested_date}
        </p>
      </div>
      {req.status === "pending" && onApprove && (
        <div className="flex gap-1 flex-shrink-0">
          <Button size="sm" variant="ghost" className="h-7 px-2 text-green-600 hover:text-green-700 hover:bg-green-50" onClick={() => onApprove(req)}>
            <CheckCircle className="w-4 h-4" />
          </Button>
          <Button size="sm" variant="ghost" className="h-7 px-2 text-red-500 hover:text-red-600 hover:bg-red-50" onClick={() => onDeny(req)}>
            <XCircle className="w-4 h-4" />
          </Button>
        </div>
      )}
    </div>
  );
}