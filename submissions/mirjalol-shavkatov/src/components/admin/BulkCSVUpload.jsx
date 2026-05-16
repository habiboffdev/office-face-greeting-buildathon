import { useState, useRef } from "react";
import { base44 } from "@/api/base44Client";
import { Upload, Download, CheckCircle2, XCircle, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const TEMPLATE_HEADERS = ["name", "position", "department", "birth_date", "greeting_message"];
const TEMPLATE_EXAMPLE = ["John Smith", "Software Engineer", "Engineering", "1990-05-15", "Welcome, John!"];

function downloadTemplate() {
  const csv = [TEMPLATE_HEADERS.join(","), TEMPLATE_EXAMPLE.join(",")].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "employees_template.csv";
  a.click();
  URL.revokeObjectURL(url);
}

function parseCSV(text) {
  const lines = text.trim().split("\n").filter(Boolean);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((h) => h.trim().toLowerCase().replace(/"/g, ""));
  return lines.slice(1).map((line) => {
    const values = line.split(",").map((v) => v.trim().replace(/"/g, ""));
    const row = {};
    headers.forEach((h, i) => { row[h] = values[i] || ""; });
    return row;
  });
}

export default function BulkCSVUpload({ onDone, onCancel, companyId }) {
  const [rows, setRows] = useState([]);
  const [results, setResults] = useState(null); // { success, failed }
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const handleFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const parsed = parseCSV(ev.target.result);
      setRows(parsed);
      setResults(null);
    };
    reader.readAsText(file);
  };

  const handleImport = async () => {
    setUploading(true);
    const success = [];
    const failed = [];

    for (const row of rows) {
      if (!row.name?.trim()) { failed.push({ name: "(blank)", reason: "Name is required" }); continue; }
      try {
        await base44.entities.Employee.create({
          name: row.name.trim(),
          position: row.position || "",
          department: row.department || "",
          birth_date: row.birth_date || "",
          greeting_message: row.greeting_message || "",
          is_active: true,
          company_id: companyId,
        });
        success.push(row.name);
      } catch (err) {
        failed.push({ name: row.name, reason: err.message || "Unknown error" });
      }
    }

    setUploading(false);
    setResults({ success, failed });
  };

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold font-display">Bulk CSV Upload</h2>
          <p className="text-sm text-muted-foreground mt-0.5">Import multiple employees at once</p>
        </div>
        <button onClick={onCancel} className="text-muted-foreground hover:text-foreground">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Step 1: Download template */}
      <div className="rounded-xl border border-border p-4 mb-4">
        <p className="text-sm font-medium mb-2">1. Download the CSV template</p>
        <Button variant="outline" size="sm" onClick={downloadTemplate} className="gap-2">
          <Download className="w-4 h-4" />
          Download Template
        </Button>
        <p className="text-xs text-muted-foreground mt-2">
          Columns: <code className="bg-muted px-1 rounded">name</code>, <code className="bg-muted px-1 rounded">position</code>, <code className="bg-muted px-1 rounded">department</code>, <code className="bg-muted px-1 rounded">birth_date</code> (YYYY-MM-DD), <code className="bg-muted px-1 rounded">greeting_message</code>
        </p>
      </div>

      {/* Step 2: Upload CSV */}
      <div className="rounded-xl border border-dashed border-border p-6 mb-4 text-center cursor-pointer hover:bg-muted/40 transition-colors"
        onClick={() => fileRef.current?.click()}>
        <Upload className="w-8 h-8 mx-auto mb-2 text-muted-foreground opacity-60" />
        <p className="text-sm font-medium">2. Upload your filled CSV</p>
        <p className="text-xs text-muted-foreground mt-1">Click to browse</p>
        <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleFile} />
      </div>

      {/* Preview */}
      {rows.length > 0 && !results && (
        <div className="mb-4">
          <p className="text-sm font-medium mb-2">{rows.length} employees ready to import:</p>
          <div className="max-h-48 overflow-y-auto rounded-lg border border-border divide-y divide-border">
            {rows.map((r, i) => (
              <div key={i} className="px-4 py-2 text-sm flex items-center justify-between">
                <span className="font-medium">{r.name || <span className="text-destructive italic">blank name</span>}</span>
                <span className="text-muted-foreground text-xs">{[r.position, r.department].filter(Boolean).join(" · ")}</span>
              </div>
            ))}
          </div>
          <Button className="mt-4 gap-2 w-full" onClick={handleImport} disabled={uploading}>
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {uploading ? "Importing..." : `Import ${rows.length} Employees`}
          </Button>
        </div>
      )}

      {/* Results */}
      {results && (
        <div className="space-y-3 mb-4">
          {results.success.length > 0 && (
            <div className="rounded-xl bg-green-50 border border-green-200 p-4">
              <div className="flex items-center gap-2 text-green-700 font-medium text-sm mb-1">
                <CheckCircle2 className="w-4 h-4" />
                {results.success.length} imported successfully
              </div>
              <p className="text-xs text-green-600">{results.success.join(", ")}</p>
            </div>
          )}
          {results.failed.length > 0 && (
            <div className="rounded-xl bg-red-50 border border-red-200 p-4">
              <div className="flex items-center gap-2 text-red-700 font-medium text-sm mb-1">
                <XCircle className="w-4 h-4" />
                {results.failed.length} failed
              </div>
              {results.failed.map((f, i) => (
                <p key={i} className="text-xs text-red-600">{f.name}: {f.reason}</p>
              ))}
            </div>
          )}
          <Button onClick={onDone} className="w-full">Done — View Employees</Button>
        </div>
      )}

      {!rows.length && !results && (
        <Button variant="outline" onClick={onCancel} className="w-full">Cancel</Button>
      )}
    </div>
  );
}