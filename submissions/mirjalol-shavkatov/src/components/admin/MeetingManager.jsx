import { useState, useEffect } from "react";
import { useCompany } from "@/lib/CompanyContext";
import { base44 } from "@/api/base44Client";
import { Plus, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { format } from "date-fns";

export default function MeetingManager() {
  const { activeCompany } = useCompany();
  const [meetings, setMeetings] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", employee_id: "", start_time: "", end_time: "", location: "" });

  useEffect(() => {
    if (!activeCompany) return;
    Promise.all([
      base44.entities.Meeting.filter({ company_id: activeCompany.id }, "-start_time", 100),
      base44.entities.Employee.filter({ company_id: activeCompany.id, is_active: true })
    ]).then(([m, e]) => { setMeetings(m); setEmployees(e); setLoading(false); });
  }, [activeCompany]);

  const save = async () => {
    const created = await base44.entities.Meeting.create({ ...form, company_id: activeCompany.id });
    setMeetings((p) => [created, ...p]);
    setOpen(false);
    setForm({ title: "", employee_id: "", start_time: "", end_time: "", location: "" });
  };

  const remove = async (id) => {
    await base44.entities.Meeting.delete(id);
    setMeetings((p) => p.filter((m) => m.id !== id));
  };

  const empName = (id) => employees.find((e) => e.id === id)?.name || id;

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="animate-spin w-6 h-6 text-muted-foreground" /></div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-semibold">Meetings</h2>
          <p className="text-sm text-muted-foreground">Shown on greeting overlay when employee is recognized</p>
        </div>
        <Button onClick={() => setOpen(true)} className="gap-2"><Plus className="w-4 h-4" /> Add Meeting</Button>
      </div>

      {meetings.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">No meetings yet.</div>
      ) : (
        <div className="space-y-2">
          {meetings.map((m) => (
            <div key={m.id} className="bg-card border border-border rounded-xl px-5 py-4 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="font-medium truncate">{m.title}</p>
                <p className="text-sm text-muted-foreground">
                  {empName(m.employee_id)} · {m.start_time ? format(new Date(m.start_time), "MMM d, h:mm a") : "—"}
                  {m.location ? ` · ${m.location}` : ""}
                </p>
              </div>
              <Button variant="ghost" size="icon" className="text-destructive" onClick={() => remove(m.id)}>
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Meeting</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <Label>Title</Label>
              <Input className="mt-1" value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} placeholder="e.g. Quarterly Review" />
            </div>
            <div>
              <Label>Employee</Label>
              <Select value={form.employee_id} onValueChange={(v) => setForm((p) => ({ ...p, employee_id: v }))}>
                <SelectTrigger className="mt-1"><SelectValue placeholder="Select employee" /></SelectTrigger>
                <SelectContent>
                  {employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Start</Label>
                <Input className="mt-1" type="datetime-local" value={form.start_time} onChange={(e) => setForm((p) => ({ ...p, start_time: e.target.value }))} />
              </div>
              <div>
                <Label>End</Label>
                <Input className="mt-1" type="datetime-local" value={form.end_time} onChange={(e) => setForm((p) => ({ ...p, end_time: e.target.value }))} />
              </div>
            </div>
            <div>
              <Label>Location (optional)</Label>
              <Input className="mt-1" value={form.location} onChange={(e) => setForm((p) => ({ ...p, location: e.target.value }))} placeholder="e.g. Room 3B" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={save} disabled={!form.title || !form.employee_id || !form.start_time || !form.end_time}>Save</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}