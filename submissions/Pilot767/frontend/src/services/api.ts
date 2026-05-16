const API = '/api';

export interface Person {
  id: number;
  full_name: string;
  image_path: string;
  total_visits: number;
  last_seen_at: string | null;
  is_vip: boolean;
  birthday: string | null;
  created_at: string;
}

export interface Video {
  id: number;
  filename: string;
  title: string | null;
  url: string;
}

export interface Visit {
  id: number;
  person_id: number;
  full_name: string;
  visited_at: string;
}

export interface Analytics {
  visitors_today: number;
  visits_this_week: number;
  recent_visitors: { full_name: string; visited_at: string }[];
  frequent_visitors: { full_name: string; total_visits: number }[];
  peak_hours: { hour: string; count: number }[];
}

export interface WelcomePayload {
  type: 'welcome';
  person_id: number;
  full_name: string;
  greeting: string;
  subtitle?: string;
  is_vip: boolean;
  is_birthday?: boolean;
  is_founder?: boolean;
  founder_image_url?: string;
  /** Asoschi: UTC kun bo‘yicha bugungi tashriflar (1 = birinchi, 2+ = qayta) */
  founder_visits_today?: number;
  /** VIP (va boshqalar): bugungi tashrif tartibi — badge uchun */
  visits_today?: number;
}

function parseApiError(body: unknown, fallback: string): string {
  if (!body || typeof body !== 'object') return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg: string }).msg);
        }
        return JSON.stringify(item);
      })
      .join('; ');
  }
  return fallback;
}

async function readApiError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return parseApiError(body, fallback);
  } catch {
    if (res.status === 0 || res.status >= 500) {
      return 'Backend ishlamayapti. Avval backend ni ishga tushiring (port 8000).';
    }
    return fallback;
  }
}

export async function fetchPeople(): Promise<Person[]> {
  const r = await fetch(`${API}/people`);
  if (!r.ok) throw new Error(await readApiError(r, 'Odamlar ro‘yxati yuklanmadi'));
  return r.json();
}

export async function fetchVideos(): Promise<Video[]> {
  const r = await fetch(`${API}/videos`);
  if (!r.ok) throw new Error(await readApiError(r, 'Videolar yuklanmadi'));
  return r.json();
}

export async function fetchVisits(): Promise<Visit[]> {
  const r = await fetch(`${API}/people/visits`);
  if (!r.ok) throw new Error(await readApiError(r, 'Tashriflar yuklanmadi'));
  return r.json();
}

export async function fetchAnalytics(): Promise<Analytics> {
  const r = await fetch(`${API}/analytics/summary`);
  if (!r.ok) throw new Error(await readApiError(r, 'Statistika yuklanmadi'));
  return r.json();
}

export async function createPerson(form: FormData): Promise<Person> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000);
  let r: Response;
  try {
    r = await fetch(`${API}/people`, { method: 'POST', body: form, signal: controller.signal });
  } catch (e) {
    clearTimeout(timeout);
    if (e instanceof Error && e.name === 'AbortError') {
      throw new Error('Vaqt tugadi (90s). Backend sekin — qayta urinib ko‘ring.');
    }
    throw new Error(
      'Serverga ulanib bo‘lmadi. Backend ishlayaptimi? (uvicorn main:app --port 8000)',
    );
  }
  clearTimeout(timeout);
  if (!r.ok) {
    const msg = await readApiError(r, 'Odam qo‘shilmadi');
    if (msg.toLowerCase().includes('no face')) {
      throw new Error('Rasmda yuz topilmadi. Yuz aniq va old tomonda bo‘lgan rasm tanlang (JPG/PNG).');
    }
    if (msg.toLowerCase().includes('invalid image')) {
      throw new Error('Faqat JPG, PNG yoki WEBP rasm qabul qilinadi (telefon HEIC emas).');
    }
    throw new Error(msg);
  }
  return r.json();
}

export async function deletePerson(id: number): Promise<void> {
  const r = await fetch(`${API}/people/${id}`, { method: 'DELETE' });
  if (!r.ok) throw new Error(await readApiError(r, 'O‘chirib bo‘lmadi'));
}

export interface Founder {
  id: number;
  person_id: number;
  full_name: string;
  hero_image_path: string;
  hero_image_url: string;
  welcome_title: string;
  welcome_subtitle: string;
  welcome_title_repeat?: string | null;
  welcome_subtitle_repeat?: string | null;
  sort_order: number;
  created_at: string;
}

/** Backend bilan mos (FOUNDERS_MAX) */
export const FOUNDERS_MAX = 31;

export async function fetchFounders(): Promise<Founder[]> {
  const r = await fetch(`${API}/founders`);
  if (!r.ok) throw new Error(await readApiError(r, 'Asoschilar yuklanmadi'));
  return r.json();
}

export async function addFounder(form: FormData): Promise<Founder> {
  const r = await fetch(`${API}/founders`, { method: 'POST', body: form });
  if (!r.ok) throw new Error(await readApiError(r, 'Qo‘shilmadi'));
  return r.json();
}

export async function patchFounder(
  id: number,
  body: {
    welcome_title?: string;
    welcome_subtitle?: string;
    welcome_title_repeat?: string | null;
    welcome_subtitle_repeat?: string | null;
    sort_order?: number;
  },
): Promise<Founder> {
  const r = await fetch(`${API}/founders/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await readApiError(r, 'Saqlanmadi'));
  return r.json();
}

export async function deleteFounder(id: number): Promise<void> {
  const r = await fetch(`${API}/founders/${id}`, { method: 'DELETE' });
  if (!r.ok) throw new Error(await readApiError(r, 'O‘chirilmadi'));
}

export async function testGreeting(
  id: number,
  options?: {
    simulateBirthday?: boolean;
    /** Admin: displayda tabrik shablonini sana shartsiz ko‘rsatish */
    previewBirthday?: boolean;
    /** previewBirthday bilan: matnlarda shu ism (masalan namuna ism maydoni) */
    sampleName?: string;
    /** Asoschi: «shu kunda qayta kirish» shablonini sinash (bugun 1 tashrif bo‘lsa ham) */
    founderPreviewRepeat?: boolean;
    /** VIP: qayta kirish shablonini sinash */
    vipPreviewRepeat?: boolean;
  },
): Promise<void> {
  const params = new URLSearchParams();
  if (options?.simulateBirthday) params.set('simulate_birthday', 'true');
  if (options?.previewBirthday) params.set('preview_birthday', 'true');
  if (options?.sampleName?.trim()) params.set('sample_name', options.sampleName.trim());
  if (options?.founderPreviewRepeat) params.set('founder_preview_repeat', 'true');
  if (options?.vipPreviewRepeat) params.set('vip_preview_repeat', 'true');
  const q = params.toString();
  const r = await fetch(`${API}/people/${id}/test-greeting${q ? `?${q}` : ''}`, {
    method: 'POST',
  });
  if (!r.ok) throw new Error(await readApiError(r, 'Test ishlamadi'));
}

export async function updatePersonBirthday(
  id: number,
  birthday: string | null,
): Promise<Person> {
  const r = await fetch(`${API}/people/${id}/birthday`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      birthday: birthday && birthday.trim() !== '' ? birthday.trim().slice(0, 10) : null,
    }),
  });
  if (!r.ok) throw new Error(await readApiError(r, 'Tug‘ilgan kun saqlanmadi'));
  return r.json();
}

export async function uploadVideo(file: File): Promise<Video> {
  const fd = new FormData();
  fd.append('file', file);
  let r: Response;
  try {
    r = await fetch(`${API}/videos`, { method: 'POST', body: fd });
  } catch {
    throw new Error('Serverga ulanib bo‘lmadi. Backend ishga tushiring.');
  }
  if (!r.ok) throw new Error(await readApiError(r, 'Video yuklanmadi'));
  return r.json();
}

export async function deleteVideo(id: number): Promise<void> {
  const r = await fetch(`${API}/videos/${id}`, { method: 'DELETE' });
  if (!r.ok) throw new Error(await readApiError(r, 'Video o‘chirilmadi'));
}

export async function updatePersonVip(id: number, is_vip: boolean): Promise<Person> {
  const r = await fetch(`${API}/people/${id}/vip`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_vip }),
  });
  if (!r.ok) throw new Error(await readApiError(r, 'VIP saqlanmadi'));
  return r.json();
}

export interface GreetingSettings {
  title_template: string;
  subtitle_template: string;
  use_smart_rules: boolean;
  birthday_title_template: string;
  birthday_subtitle_template: string;
  vip_title_template: string;
  vip_subtitle_template: string;
  vip_title_repeat_template: string;
  vip_subtitle_repeat_template: string;
}

export function previewGreetingText(
  titleTemplate: string,
  subtitleTemplate: string,
  fullName: string,
): { title: string; subtitle: string } {
  const first = fullName.trim().split(/\s+/)[0] || fullName;
  const map: Record<string, string> = {
    '{ism}': fullName,
    '{name}': fullName,
    '{full_name}': fullName,
    '{ism_qisqa}': first,
    '{first_name}': first,
    '{tashkilot}': 'Rocus',
    '{org}': 'Rocus',
  };
  let title = titleTemplate;
  let subtitle = subtitleTemplate;
  for (const [key, val] of Object.entries(map)) {
    title = title.split(key).join(val);
    subtitle = subtitle.split(key).join(val);
  }
  return { title, subtitle };
}

export function previewVipTemplates(
  settings: GreetingSettings,
  fullName: string,
  repeat: boolean,
): { title: string; subtitle: string } {
  const t = repeat
    ? settings.vip_title_repeat_template?.trim() || settings.vip_title_template
    : settings.vip_title_template;
  const s = repeat
    ? settings.vip_subtitle_repeat_template?.trim() || settings.vip_subtitle_template
    : settings.vip_subtitle_template;
  return previewGreetingText(t, s, fullName);
}

export async function fetchGreetingSettings(): Promise<GreetingSettings> {
  const r = await fetch(`${API}/settings/greeting`);
  if (!r.ok) throw new Error(await readApiError(r, 'Xabar sozlamalari yuklanmadi'));
  return r.json();
}

export async function saveGreetingSettings(settings: GreetingSettings): Promise<GreetingSettings> {
  const r = await fetch(`${API}/settings/greeting`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!r.ok) throw new Error(await readApiError(r, 'Saqlab bo‘lmadi'));
  return r.json();
}

export async function postTelegramTest(): Promise<{
  ok?: boolean;
  error?: string;
  hint?: string;
  message?: string;
  telegram?: unknown;
  http_status?: number;
}> {
  const r = await fetch(`${API}/health/telegram-test`, { method: 'POST' });
  return r.json();
}

export async function fetchTelegramDebug(): Promise<unknown> {
  const res = await fetch(`${API}/health/telegram-debug`);
  if (!res.ok) throw new Error('Telegram debug yuklanmadi');
  return res.json();
}

export async function fetchHealth(): Promise<{
  camera_active: boolean;
  camera_error: string | null;
  status?: string;
  telegram?: { enabled: boolean };
}> {
  try {
    const r = await fetch(`${API}/health`);
    if (!r.ok) return { camera_active: false, camera_error: 'Backend javob bermadi' };
    return r.json();
  } catch {
    return { camera_active: false, camera_error: 'Backend o‘chiq (port 8000)' };
  }
}
