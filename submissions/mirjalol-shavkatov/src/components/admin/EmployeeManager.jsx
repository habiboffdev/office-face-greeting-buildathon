import { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import { Plus, Trash2, Edit2, User, CheckCircle2, AlertCircle, Search, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import EmployeeForm from "./EmployeeForm";
import BulkCSVUpload from "./BulkCSVUpload";
import { useCompany } from "@/lib/CompanyContext";

export default function EmployeeManager() {
  const { activeCompany } = useCompany();
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showBulk, setShowBulk] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (activeCompany) loadEmployees();
  }, [activeCompany]);

  const loadEmployees = async () => {
    setLoading(true);
    const data = await base44.entities.Employee.filter({ company_id: activeCompany.id }, "-created_date", 100);
    setEmployees(data);
    setLoading(false);
  };

  const handleDelete = async (id) => {
    if (!confirm("Remove this employee from the recognition system?")) return;
    await base44.entities.Employee.delete(id);
    setEmployees((prev) => prev.filter((e) => e.id !== id));
  };

  const handleToggleActive = async (employee) => {
    await base44.entities.Employee.update(employee.id, { is_active: !employee.is_active });
    setEmployees((prev) =>
      prev.map((e) => (e.id === employee.id ? { ...e, is_active: !e.is_active } : e))
    );
  };

  const handleFormSave = () => {
    setShowForm(false);
    setEditingEmployee(null);
    loadEmployees();
  };

  const filtered = employees.filter((e) =>
    e.name?.toLowerCase().includes(search.toLowerCase())
  );

  if (showForm || editingEmployee) {
    return (
      <EmployeeForm
        employee={editingEmployee}
        companyId={activeCompany?.id}
        onSave={handleFormSave}
        onCancel={() => { setShowForm(false); setEditingEmployee(null); }}
      />
    );
  }

  if (showBulk) {
    return (
      <BulkCSVUpload
        companyId={activeCompany?.id}
        onDone={() => { setShowBulk(false); loadEmployees(); }}
        onCancel={() => setShowBulk(false)}
      />
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold font-display">Employees</h2>
          <p className="text-sm text-muted-foreground mt-0.5">{employees.length} people in system</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowBulk(true)} className="gap-2">
            <Upload className="w-4 h-4" />
            Bulk Upload
          </Button>
          <Button onClick={() => setShowForm(true)} className="gap-2">
            <Plus className="w-4 h-4" />
            Add Employee
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-6 max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search by name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array(6).fill(0).map((_, i) => (
            <div key={i} className="h-32 rounded-xl bg-muted animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <User className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="font-medium">{search ? "No employees match your search" : "No employees yet"}</p>
          <p className="text-sm mt-1">{search ? "Try a different name" : "Add employees to start face recognition"}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((emp) => (
            <div
              key={emp.id}
              className={`bg-card border rounded-xl p-4 flex items-center gap-4 transition-all ${
                emp.is_active ? "border-border" : "border-border opacity-50"
              }`}
            >
              {/* Avatar */}
              <div className="relative flex-shrink-0">
                <div className="w-14 h-14 rounded-full overflow-hidden bg-muted border border-border">
                  {emp.photo_url ? (
                    <img src={emp.photo_url} alt={emp.name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <User className="w-6 h-6 text-muted-foreground" />
                    </div>
                  )}
                </div>
                {emp.face_descriptor && emp.face_descriptor.length > 0 ? (
                  <div className="absolute -bottom-0.5 -right-0.5 w-5 h-5 rounded-full bg-green-500 border-2 border-card flex items-center justify-center">
                    <CheckCircle2 className="w-3 h-3 text-white" />
                  </div>
                ) : (
                  <div className="absolute -bottom-0.5 -right-0.5 w-5 h-5 rounded-full bg-yellow-500 border-2 border-card flex items-center justify-center">
                    <AlertCircle className="w-3 h-3 text-white" />
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm truncate">{emp.name}</p>
                {emp.position && (
                  <p className="text-xs text-muted-foreground truncate">{emp.position}</p>
                )}
                <div className="flex items-center gap-1 mt-1.5">
                  <Badge
                    variant="secondary"
                    className={`text-xs px-1.5 py-0 ${emp.is_active ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground"}`}
                  >
                    {emp.is_active ? "Active" : "Inactive"}
                  </Badge>
                  {(!emp.face_descriptor || emp.face_descriptor.length === 0) && (
                    <Badge variant="secondary" className="text-xs px-1.5 py-0 bg-yellow-100 text-yellow-700">
                      No face data
                    </Badge>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex flex-col gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7"
                  onClick={() => setEditingEmployee(emp)}
                >
                  <Edit2 className="w-3.5 h-3.5" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7 text-destructive hover:text-destructive"
                  onClick={() => handleDelete(emp.id)}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}