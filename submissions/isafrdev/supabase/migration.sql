-- ============================================
-- VisionGate AI — Supabase Database Schema
-- ============================================

-- People (Xodimlar bazasi)
CREATE TABLE IF NOT EXISTS people (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  role TEXT DEFAULT '',
  language TEXT DEFAULT 'uz',
  custom_message TEXT,
  birthday DATE,
  cooldown_minutes INTEGER DEFAULT 10,
  greeting_mode TEXT DEFAULT 'cooldown',
  voice_enabled BOOLEAN DEFAULT true,
  embeddings JSONB DEFAULT '[]'::jsonb,
  avatar TEXT,
  is_blacklisted BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Recognition Logs (Aniqlash loglari)
CREATE TABLE IF NOT EXISTS recognition_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id UUID REFERENCES people(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  confidence REAL DEFAULT 0,
  timestamp BIGINT NOT NULL,
  expression TEXT,
  snapshot TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for fast log queries
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON recognition_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_person ON recognition_logs(person_id);

-- Settings (Tizim sozlamalari)
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- Row Level Security (RLS)
-- ============================================
ALTER TABLE people ENABLE ROW LEVEL SECURITY;
ALTER TABLE recognition_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;

-- Allow public read/write for now (kiosk mode — no auth)
CREATE POLICY "Allow all for people" ON people FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for logs" ON recognition_logs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for settings" ON settings FOR ALL USING (true) WITH CHECK (true);
