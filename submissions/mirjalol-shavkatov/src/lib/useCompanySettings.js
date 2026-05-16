import { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";

// Cache per company_id
const cache = {};
const listeners = {};

export function useCompanySettings(companyId) {
  const [settings, setSettings] = useState(companyId ? cache[companyId] : null);

  useEffect(() => {
    if (!companyId) return;

    if (cache[companyId]) {
      setSettings(cache[companyId]);
      return;
    }

    base44.entities.CompanySettings.filter({ company_id: companyId }).then((all) => {
      const s = all[0] || { brand_color: "#D4AF37", logo_url: null, company_name: "", debug_mode: false };
      cache[companyId] = s;
      if (listeners[companyId]) {
        listeners[companyId].forEach((fn) => fn(s));
      }
    });

    if (!listeners[companyId]) listeners[companyId] = new Set();
    const handler = (s) => setSettings(s);
    listeners[companyId].add(handler);
    return () => listeners[companyId].delete(handler);
  }, [companyId]);

  return settings || { brand_color: "#D4AF37", logo_url: null, company_name: "", language: "en", debug_mode: false };
}