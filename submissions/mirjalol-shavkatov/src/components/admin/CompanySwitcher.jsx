import { useState } from "react";
import { useCompany } from "@/lib/CompanyContext";
import { Building2, Plus, ChevronDown, Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function CompanySwitcher() {
  const { companies, activeCompany, switchCompany, createCompany } = useCompany();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    await createCompany(newName.trim());
    setCreating(false);
    setNewName("");
    setShowCreate(false);
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="gap-2 max-w-48">
            <Building2 className="w-4 h-4 flex-shrink-0" />
            <span className="truncate">{activeCompany?.name || "Select Company"}</span>
            <ChevronDown className="w-3 h-3 flex-shrink-0 opacity-60" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          {companies.map((c) => (
            <DropdownMenuItem
              key={c.id}
              onClick={() => switchCompany(c)}
              className="flex items-center justify-between"
            >
              <span className="truncate">{c.name}</span>
              {activeCompany?.id === c.id && <Check className="w-4 h-4 text-primary ml-2 flex-shrink-0" />}
            </DropdownMenuItem>
          ))}
          {companies.length > 0 && <DropdownMenuSeparator />}
          <DropdownMenuItem onClick={() => setShowCreate(true)} className="gap-2 text-primary">
            <Plus className="w-4 h-4" />
            New Company
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Company</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <Label>Company Name</Label>
              <Input
                className="mt-1"
                placeholder="Acme Corp"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                autoFocus
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button onClick={handleCreate} disabled={creating || !newName.trim()}>
                {creating && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                Create
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}