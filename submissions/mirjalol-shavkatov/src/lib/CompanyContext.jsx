import { createContext, useContext, useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";

const CompanyContext = createContext(null);

export function CompanyProvider({ children }) {
  const [user, setUser] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [activeCompany, setActiveCompanyState] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    init();
  }, []);

  const init = async () => {
    try {
      const me = await base44.auth.me();
      setUser(me);

      // Load all companies this admin created (by their email)
      const all = await base44.entities.Company.filter({ owner_email: me.email });
      setCompanies(all);

      // Restore last active company
      let active = null;
      if (me.active_company_id) {
        active = all.find((c) => c.id === me.active_company_id) || null;
      }
      if (!active && all.length > 0) {
        active = all[0];
      }
      setActiveCompanyState(active);
    } catch {
      // not logged in
    }
    setLoading(false);
  };

  const switchCompany = async (company) => {
    setActiveCompanyState(company);
    await base44.auth.updateMe({ active_company_id: company.id });
  };

  const createCompany = async (name) => {
    const me = user || (await base44.auth.me());
    const company = await base44.entities.Company.create({ name, owner_email: me.email });
    setCompanies((prev) => [...prev, company]);
    await switchCompany(company);
    return company;
  };

  return (
    <CompanyContext.Provider value={{ user, companies, activeCompany, loading, switchCompany, createCompany, reload: init }}>
      {children}
    </CompanyContext.Provider>
  );
}

export function useCompany() {
  return useContext(CompanyContext);
}