import { useState, useEffect } from "react";
import { useCompany } from "@/lib/CompanyContext";
import { base44 } from "@/api/base44Client";
import { Plus, Trash2, Loader2, AlertTriangle, Megaphone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

const priorityColor = { urgent: "destructive", normal: "secondary", low: "outline" };

export default function AnnouncementManager() {
  const { activeCompany } = useCompany();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", body: "", priority: "normal", is_active: true, expires_at: "" });

  useEffect(() => {
    if (!activeCompany) return;
    base44.entities.Announcement.filter({ company_id: activeCompany.id }, "-created_date", 50).then((a) => { setItems(a); setLoading(false); });
  }, [activeCompany]);

  const save = async () => {
    const data = { ...form, company_id: activeCompany.id };
    if (!data.expires_at) delete data.expires_at;
    const created = await base44.entities.Announcement.create(data);
    setItems((p) => [created, ...p]);
    setOpen(false);
    setForm({ title: "", body: "", priority: "normal", is_active: true, expires_at: "" });
  };

  const remove = async (id) => {
    await base44.entities.Announcement.delete(id);
    setItems((p) => p.filter((a) => a.id !== id));
  };

  const toggle = async (item) => {
    const updated = await base44.entities.Announcement.update(item.id, { is_active: !item.is_active });
    setItems((p) => p.map((a) => (a.id === item.id ? updated : a)));
  };

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="animate-spin w-6 h-6 text-muted-foreground" /></div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-semibold">Announcements</h2>
          <p className="text-sm text-muted-foreground">Company-wide messages shown on every greeting</p>
        </div>
        <Button onClick={() => setOpen(true)} className="gap-2"><Plus className="w-4 h-4" /> Add Announcement</Button>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">No announcements yet.</div>
      ) : (
        <div className="space-y-2">
          {items.map((a) => (
            <div key={a.id} className={`bg-card border rounded-xl px-5 py-4 flex items-center justify-between gap-4 ${!a.is_active ? "opacity-50" : ""}`}>
              <div className="flex items-start gap-3 min-w-0">
                {a.priority === "urgent"
                  ? <AlertTriangle className="w-5 h-5 text-destructive mt-0.5 flex-shrink-0" />
                  : <Megaphone className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />}
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium truncate">{a.title}</p>
                    <Badge variant={priorityColor[a.priority] || "secondary"}>{a.priority}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground truncate">{a.body}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <Switch checked={a.is_active} onCheckedChange={() => toggle(a)} />
                <Button variant="ghost" size="icon" className="text-destructive" onClick={() => remove(a.id)}>
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Announcement</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <Label>Title</Label>
              <Input className="mt-1" value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} placeholder="e.g. Office closed Friday" />
            </div>
            <div>
              <Label>Message</Label>
              <Textarea className="mt-1" value={form.body} onChange={(e) => setForm((p) => ({ ...p, body: e.target.value }))} placeholder="Details..." rows={3} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Priority</Label>
                <Select value={form.priority} onValueChange={(v) => setForm((p) => ({ ...p, priority: v }))}>
                  <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="normal">Normal</SelectItem>
                    <SelectItem value="urgent">Urgent</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Expires at (optional)</Label>
                <Input className="mt-1" type="datetime-local" value={form.expires_at} onChange={(e) => setForm((p) => ({ ...p, expires_at: e.target.value }))} />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={save} disabled={!form.title || !form.body}>Save</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}