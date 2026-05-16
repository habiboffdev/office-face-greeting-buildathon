import { useState } from "react";
import { useCompany } from "@/lib/CompanyContext";
import { Building2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function NoCompanyScreen() {
  const { createCompany } = useCompany();
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    await createCompany(name.trim());
    setCreating(false);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-6">
      <div className="max-w-md w-full text-center">
        <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-6">
          <Building2 className="w-8 h-8 text-primary" />
        </div>
        <h1 className="text-2xl font-display font-semibold mb-2">Set up your company</h1>
        <p className="text-muted-foreground mb-8">
          Create your first company to start managing employees, videos, and greetings.
        </p>
        <div className="text-left space-y-3">
          <Label>Company Name</Label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Acme Corp"
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            autoFocus
          />
          <Button
            className="w-full"
            onClick={handleCreate}
            disabled={creating || !name.trim()}
          >
            {creating && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
            Create Company & Continue
          </Button>
        </div>
      </div>
    </div>
  );
}