import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "";
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || "";

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.warn("[VisionGate] Supabase credentials missing – falling back to local-only mode.");
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
