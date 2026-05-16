import { useState, useEffect, useRef } from "react";
import { base44 } from "@/api/base44Client";
import { useCompany } from "@/lib/CompanyContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Upload, Building2, Bug } from "lucide-react";

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "uz", label: "O'zbekcha" },
  { value: "ru", label: "Русский" },
];

const PRESET_COLORS = [
  "#FF6B00", // Orange (UzCombinator)
  "#E31937", // Red (Tesla / Coca-Cola)
  "#0078D4", // Blue (Microsoft)
  "#34A853", // Green (Spotify-ish)
  "#6E40C9", // Purple
  "#D4AF37", // Gold (default)
  "#1DA1F2", // Twitter blue
  "#111111", // Black
];

export default function CompanySettingsManager() {
  const { activeCompany } = useCompany();
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState({ company_name: "", logo_url: "", brand_color: "#D4AF37", language: "en", debug_mode: false, idle_screen_enabled: false, idle_timeout_minutes: 30, telegram_chat_id: "", ai_chat_enabled: true });
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!activeCompany) return;
    base44.entities.CompanySettings.filter({ company_id: activeCompany.id }).then((all) => {
      if (all.length > 0) {
        setSettings(all[0]);
        setForm({ 
          company_name: all[0].company_name || "", 
          logo_url: all[0].logo_url || "", 
          brand_color: all[0].brand_color || "#D4AF37", 
          language: all[0].language || "en", 
          debug_mode: all[0].debug_mode || false,
          idle_screen_enabled: all[0].idle_screen_enabled || false,
          idle_timeout_minutes: all[0].idle_timeout_minutes || 30,
          telegram_chat_id: all[0].telegram_chat_id || "",
          ai_chat_enabled: all[0].ai_chat_enabled !== false ? true : false
        });
      } else {
        // Pre-fill company name from Company entity
        setForm((p) => ({ ...p, company_name: activeCompany.name }));
        setSettings(null);
      }
    });
  }, [activeCompany]);

  const handleLogoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    const { file_url } = await base44.integrations.Core.UploadFile({ file });
    setForm((p) => ({ ...p, logo_url: file_url }));
    setUploading(false);
  };

  const handleSave = async () => {
    setSaving(true);
    if (settings) {
      await base44.entities.CompanySettings.update(settings.id, form);
    } else {
      const created = await base44.entities.CompanySettings.create({ ...form, company_id: activeCompany.id });
      setSettings(created);
    }
    setSaving(false);
  };

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <Label>Company Name</Label>
        <Input
          className="mt-1"
          value={form.company_name}
          onChange={(e) => setForm((p) => ({ ...p, company_name: e.target.value }))}
          placeholder="UzCombinator"
        />
      </div>

      <div>
        <Label>Company Logo</Label>
        <div className="mt-2 flex items-center gap-4">
          <div className="w-20 h-20 rounded-xl border border-border bg-muted flex items-center justify-center overflow-hidden flex-shrink-0">
            {form.logo_url
              ? <img src={form.logo_url} alt="logo" className="w-full h-full object-contain p-1" />
              : <Building2 className="w-8 h-8 text-muted-foreground opacity-40" />
            }
          </div>
          <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            {uploading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Upload className="w-4 h-4 mr-1" />}
            Upload Logo
          </Button>
          <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleLogoUpload} />
        </div>
      </div>

      <div>
        <Label>Brand Color</Label>
        <div className="mt-2 flex items-center gap-3 flex-wrap">
          {PRESET_COLORS.map((c) => (
            <button
              key={c}
              onClick={() => setForm((p) => ({ ...p, brand_color: c }))}
              className="w-8 h-8 rounded-full border-2 transition-all"
              style={{
                background: c,
                borderColor: form.brand_color === c ? "#fff" : "transparent",
                boxShadow: form.brand_color === c ? `0 0 0 2px ${c}` : "none"
              }}
            />
          ))}
          <div className="flex items-center gap-2 ml-1">
            <input
              type="color"
              value={form.brand_color}
              onChange={(e) => setForm((p) => ({ ...p, brand_color: e.target.value }))}
              className="w-8 h-8 rounded cursor-pointer border border-border"
              title="Custom color"
            />
            <span className="text-xs text-muted-foreground font-mono">{form.brand_color}</span>
          </div>
        </div>
      </div>

      <div>
        <Label>Platform Language</Label>
        <div className="mt-2 flex gap-2">
          {LANGUAGES.map((l) => (
            <button
              key={l.value}
              onClick={() => setForm((p) => ({ ...p, language: l.value }))}
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-all ${
                form.language === l.value
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>



      {/* Preview */}

      <div className="rounded-xl p-4 border border-border bg-muted/40">
        <p className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Preview</p>
        <div className="rounded-xl overflow-hidden" style={{ border: `1px solid ${form.brand_color}80`, boxShadow: `0 0 20px ${form.brand_color}30` }}>
          <div className="h-1 w-full" style={{ background: `linear-gradient(90deg, transparent, ${form.brand_color}, transparent)` }} />
          <div className="bg-gray-900 px-4 py-3 flex items-center gap-3">
            {form.logo_url && <img src={form.logo_url} alt="logo" className="w-8 h-8 object-contain rounded" />}
            <span className="text-white font-semibold">{form.company_name || "Company Name"}</span>
          </div>
        </div>
      </div>

      {/* Debug Mode */}
      <div className="flex items-center justify-between rounded-xl border border-border p-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-muted flex items-center justify-center">
            <Bug className="w-4 h-4 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium">Debug Panel</p>
            <p className="text-xs text-muted-foreground">Show face recognition debug overlay on the display screen</p>
          </div>
        </div>
        <button
          onClick={() => setForm((p) => ({ ...p, debug_mode: !p.debug_mode }))}
          className={`relative w-11 h-6 rounded-full transition-colors ${form.debug_mode ? "bg-primary" : "bg-muted"}`}
        >
          <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${form.debug_mode ? "translate-x-5" : "translate-x-0"}`} />
        </button>
      </div>

      {/* Idle Screen */}
      <div className="flex items-center justify-between rounded-xl border border-border p-4">
        <div className="flex items-center gap-3 flex-1">
          <div className="w-9 h-9 rounded-lg bg-muted flex items-center justify-center">
            <Bug className="w-4 h-4 text-muted-foreground" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium">Idle Screen</p>
            <p className="text-xs text-muted-foreground">Show screensaver when no one detected for X minutes</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <input 
            type="number" 
            min="5" 
            max="120" 
            value={form.idle_timeout_minutes}
            onChange={(e) => setForm((p) => ({ ...p, idle_timeout_minutes: parseInt(e.target.value) }))}
            className="w-16 px-2 py-1 text-sm border border-border rounded-lg"
          />
          <span className="text-xs text-muted-foreground">min</span>
          <button
            onClick={() => setForm((p) => ({ ...p, idle_screen_enabled: !p.idle_screen_enabled }))}
            className={`relative w-11 h-6 rounded-full transition-colors ${form.idle_screen_enabled ? "bg-primary" : "bg-muted"}`}
          >
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${form.idle_screen_enabled ? "translate-x-5" : "translate-x-0"}`} />
          </button>
        </div>
      </div>

      {/* Telegram Chat ID */}
      <div>
        <Label>Telegram Chat ID (for alerts)</Label>
        <Input
          className="mt-1"
          value={form.telegram_chat_id}
          onChange={(e) => setForm((p) => ({ ...p, telegram_chat_id: e.target.value }))}
          placeholder="Your personal Telegram chat ID"
          type="text"
        />
        <p className="text-xs text-muted-foreground mt-1">Get it from @userinfobot on Telegram</p>
      </div>

      {/* AI Chat Toggle */}
      <div className="flex items-center justify-between rounded-xl border border-border p-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-muted flex items-center justify-center">
            <Bug className="w-4 h-4 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium">AI Chat Assistant</p>
            <p className="text-xs text-muted-foreground">Enable/disable to control API credit costs</p>
          </div>
        </div>
        <button
          onClick={() => setForm((p) => ({ ...p, ai_chat_enabled: p.ai_chat_enabled !== false ? false : true }))}
          className={`relative w-11 h-6 rounded-full transition-colors ${form.ai_chat_enabled !== false ? "bg-primary" : "bg-muted"}`}
        >
          <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${form.ai_chat_enabled !== false ? "translate-x-5" : "translate-x-0"}`} />
        </button>
      </div>

      <Button onClick={handleSave} disabled={saving || !form.company_name}>
        {saving && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
        Save Settings
      </Button>
    </div>
  );
}