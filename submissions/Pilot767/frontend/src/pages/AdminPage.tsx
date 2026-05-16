import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  addFounder,
  createPerson,
  deleteFounder,
  deletePerson,
  deleteVideo,
  fetchAnalytics,
  fetchFounders,
  fetchGreetingSettings,
  fetchHealth,
  fetchPeople,
  fetchVideos,
  fetchVisits,
  FOUNDERS_MAX,
  patchFounder,
  postTelegramTest,
  previewGreetingText,
  previewVipTemplates,
  saveGreetingSettings,
  testGreeting,
  updatePersonBirthday,
  updatePersonVip,
  uploadVideo,
  type Analytics,
  type Founder,
  type GreetingSettings,
  type Person,
  type Video,
  type Visit,
} from '../services/api';

const ADMIN_MENU = [
  { id: 'overview', label: 'Tizim holati', short: 'Holat' },
  { id: 'greetings', label: 'Ekran matnlari', short: 'Matnlar' },
  { id: 'people', label: 'Odamlar', short: 'Yuzlar' },
  { id: 'founders', label: 'Asoschilar', short: 'Asoschi' },
  { id: 'videos', label: 'Videolar', short: 'Video' },
  { id: 'analytics', label: 'Statistika', short: 'Stat' },
  { id: 'visits', label: 'Tashriflar', short: 'Jurnal' },
] as const;

type AdminSectionId = (typeof ADMIN_MENU)[number]['id'];

const GREETING_DEFAULTS: GreetingSettings = {
  title_template: 'Salom, {ism}!',
  subtitle_template: 'Rocusga xush kelibsiz!',
  use_smart_rules: false,
  birthday_title_template: "Tug'ilgan kuningiz bilan, {ism}!",
  birthday_subtitle_template: '{tashkilot} jamoasi sizni tabriklaydi!',
  vip_title_template: 'Hurmatli mehmon, {ism}!',
  vip_subtitle_template: '{tashkilot} jamoasi sizni qutlaydi — xush kelibsiz!',
  vip_title_repeat_template: '',
  vip_subtitle_repeat_template: '',
};

function FounderRepeatEditor({
  founder,
  onSaved,
  setMsg,
}: {
  founder: Founder;
  onSaved: () => void;
  setMsg: (s: string) => void;
}) {
  const [title, setTitle] = useState(founder.welcome_title_repeat ?? '');
  const [subtitle, setSubtitle] = useState(founder.welcome_subtitle_repeat ?? '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTitle(founder.welcome_title_repeat ?? '');
    setSubtitle(founder.welcome_subtitle_repeat ?? '');
  }, [founder.id, founder.welcome_title_repeat, founder.welcome_subtitle_repeat]);

  const save = () => {
    setSaving(true);
    setMsg('');
    patchFounder(founder.id, {
      welcome_title_repeat: title.trim() || null,
      welcome_subtitle_repeat: subtitle.trim() || null,
    })
      .then(() => {
        setMsg('Qayta kirish matnlari saqlandi');
        return onSaved();
      })
      .catch((e) => setMsg(e instanceof Error ? e.message : 'Xato'))
      .finally(() => setSaving(false));
  };

  return (
    <div className="mt-3 w-full rounded-lg border border-amber-500/20 bg-black/30 p-3">
      <p className="mb-2 text-[11px] font-medium text-amber-200/90">
        Shu kunda 2-chi va keyingi kirishlar (UTC kun; bo‘sh qatorlar = birinchi kirish matni ishlatiladi)
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        <input
          className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-xs focus:border-amber-500/40 focus:outline-none"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Qayta: yuqori qator"
        />
        <input
          className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-xs focus:border-amber-500/40 focus:outline-none"
          value={subtitle}
          onChange={(e) => setSubtitle(e.target.value)}
          placeholder="Qayta: pastki qator"
        />
      </div>
      <button
        type="button"
        disabled={saving}
        onClick={() => void save()}
        className="mt-2 rounded-lg bg-amber-700/80 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-600 disabled:opacity-50"
      >
        {saving ? 'Saqlanmoqda…' : 'Qayta matnlarni saqlash'}
      </button>
    </div>
  );
}

export function AdminPage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [founders, setFounders] = useState<Founder[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [visits, setVisits] = useState<Visit[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [health, setHealth] = useState<{
    camera_active: boolean;
    camera_error: string | null;
    telegram?: { enabled: boolean };
  } | null>(null);
  const [name, setName] = useState('');
  const [birthday, setBirthday] = useState('');
  const [newPersonVip, setNewPersonVip] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState('');
  const [adding, setAdding] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [greetingSettings, setGreetingSettings] = useState<GreetingSettings>(GREETING_DEFAULTS);
  const [previewName, setPreviewName] = useState('Alisher Karimov');
  const [savingGreeting, setSavingGreeting] = useState(false);
  const [greetingTab, setGreetingTab] = useState<'main' | 'birthday' | 'vip'>('main');

  const [addingFounder, setAddingFounder] = useState(false);
  const [founderPersonId, setFounderPersonId] = useState('');
  const [founderTitle, setFounderTitle] = useState('{tashkilot}ga xush kelibsiz!');
  const [founderSubtitle, setFounderSubtitle] = useState('{ism} — diip.uz asoschisi');
  const [founderTitleRepeat, setFounderTitleRepeat] = useState('');
  const [founderSubtitleRepeat, setFounderSubtitleRepeat] = useState('');
  const [founderSort, setFounderSort] = useState('0');
  const [founderHeroFile, setFounderHeroFile] = useState<File | null>(null);
  const founderHeroRef = useRef<HTMLInputElement>(null);
  const [activeSection, setActiveSection] = useState<AdminSectionId>('overview');
  const [menuOpen, setMenuOpen] = useState(false);

  const activeMenu = ADMIN_MENU.find((m) => m.id === activeSection)!;

  const reload = async () => {
    const [p, f, v, vi, a, h, g] = await Promise.all([
      fetchPeople(),
      fetchFounders().catch(() => []),
      fetchVideos(),
      fetchVisits(),
      fetchAnalytics(),
      fetchHealth(),
      fetchGreetingSettings().catch(() => null),
    ]);
    setPeople(p);
    setFounders(f);
    setVideos(v);
    setVisits(vi);
    setAnalytics(a);
    setHealth(h);
    if (g) setGreetingSettings({ ...GREETING_DEFAULTS, ...g });
  };

  const preview = previewGreetingText(
    greetingSettings.title_template,
    greetingSettings.subtitle_template,
    previewName,
  );
  const birthdayPreview = previewGreetingText(
    greetingSettings.birthday_title_template,
    greetingSettings.birthday_subtitle_template,
    previewName,
  );
  const vipPreviewFirst = previewVipTemplates(greetingSettings, previewName, false);
  const vipPreviewRepeat = previewVipTemplates(greetingSettings, previewName, true);

  const saveGreeting = async () => {
    setSavingGreeting(true);
    setMsg('');
    try {
      const saved = await saveGreetingSettings(greetingSettings);
      setGreetingSettings(saved);
      setMsg('Saqlandi: ekrandagi xabar yangilandi');
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Saqlanmadi');
    } finally {
      setSavingGreeting(false);
    }
  };

  useEffect(() => {
    reload().catch(console.error);
  }, []);

  const submitAddPerson = async () => {
    if (!name.trim()) {
      setMsg('Ism-familiyani kiriting.');
      return;
    }
    if (!file) {
      setMsg('Rasm tanlang (yuz aniq korinsin).');
      return;
    }
    setMsg('');
    setAdding(true);
    try {
      const fd = new FormData();
      fd.append('full_name', name.trim());
      if (birthday) fd.append('birthday', birthday);
      fd.append('is_vip', newPersonVip ? 'true' : 'false');
      fd.append('image', file);
      const person = await createPerson(fd);
      setName('');
      setBirthday('');
      setNewPersonVip(false);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setMsg(`Qoshildi: ${person.full_name}`);
      try {
        await reload();
      } catch {
        setMsg(`Qoshildi: ${person.full_name} (F5 bosing)`);
      }
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Xato yuz berdi');
    } finally {
      setAdding(false);
    }
  };

  const onAddPerson = (e: FormEvent) => {
    e.preventDefault();
    void submitAddPerson();
  };

  const onUploadVideo = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      await uploadVideo(f);
      setMsg('Video yuklandi');
      await reload();
    } catch {
      setMsg('Video yuklanmadi');
    }
    e.target.value = '';
  };

  const backendDown = health?.camera_error === 'Backend ochiq (port 8000)';
  const msgIsOk =
    msg.startsWith('Qoshildi') ||
    msg.startsWith('Saqlandi') ||
    msg.startsWith('Telegram: test') ||
    msg.startsWith('Display:') ||
    msg.startsWith('Tug‘ilgan kun saqlandi') ||
    msg.startsWith('Asoschi');

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-indigo-950/35 to-slate-950 text-slate-100">
      <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/95 backdrop-blur-md">
        <div className="flex items-center justify-between gap-3 px-4 py-3 sm:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              className="rounded-lg border border-white/10 p-2 text-slate-300 hover:bg-white/5 lg:hidden"
              aria-label="Menyu"
              onClick={() => setMenuOpen((o) => !o)}
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                {menuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-base font-semibold sm:text-lg">Rocus — Admin</h1>
              <p className="truncate text-xs text-slate-500">{activeMenu.label}</p>
            </div>
          </div>
          <Link
            to="/display"
            className="shrink-0 rounded-lg bg-cyan-600 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-500 sm:px-4"
          >
            Display
          </Link>
        </div>
        <div className="flex gap-1 overflow-x-auto border-t border-white/5 px-2 py-2 lg:hidden">
          {ADMIN_MENU.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => {
                setActiveSection(m.id);
                setMenuOpen(false);
              }}
              className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                activeSection === m.id
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white/5 text-slate-400 hover:text-slate-200'
              }`}
            >
              {m.short}
            </button>
          ))}
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl">
        <aside
          className={`${
            menuOpen ? 'translate-x-0' : '-translate-x-full'
          } fixed inset-y-0 left-0 z-40 w-64 border-r border-white/10 bg-slate-950/98 p-4 pt-20 transition-transform duration-200 lg:static lg:z-0 lg:translate-x-0 lg:pt-6`}
        >
          <p className="mb-3 hidden px-1 text-[10px] font-semibold uppercase tracking-widest text-slate-600 lg:block">
            Bo‘limlar
          </p>
          <nav className="space-y-1">
            {ADMIN_MENU.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => {
                  setActiveSection(m.id);
                  setMenuOpen(false);
                }}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition ${
                  activeSection === m.id
                    ? 'bg-indigo-600/90 text-white shadow-md shadow-indigo-900/40'
                    : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'
                }`}
              >
                <span
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-xs font-bold ${
                    activeSection === m.id ? 'bg-white/20' : 'bg-white/5 text-slate-500'
                  }`}
                >
                  {ADMIN_MENU.findIndex((x) => x.id === m.id) + 1}
                </span>
                <span className="truncate">{m.label}</span>
              </button>
            ))}
          </nav>
        </aside>
        {menuOpen ? (
          <button
            type="button"
            className="fixed inset-0 z-30 bg-black/50 lg:hidden"
            aria-label="Menyuni yopish"
            onClick={() => setMenuOpen(false)}
          />
        ) : null}

        <main className="min-w-0 flex-1 space-y-6 px-4 py-6 sm:px-6">
        {backendDown && (
          <p className="rounded-xl border border-red-500/35 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            Backend ishlamayapti. Terminal: <code className="text-red-100">cd backend</code> →{' '}
            <code className="text-red-100">uvicorn main:app --host 127.0.0.1 --port 8000</code>
          </p>
        )}

        {msg && (
          <p
            className={`rounded-xl border px-4 py-3 text-sm ${
              msgIsOk
                ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-200'
                : 'border-amber-500/35 bg-amber-500/10 text-amber-100'
            }`}
          >
            {msg}
          </p>
        )}

        {activeSection === 'overview' && (
        <AdminSection
          step={1}
          title="Tizim holati"
          hint="Kamera, Telegram va qisqa raqamlar"
        >
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Card title="Bugun tashrif" value={String(analytics?.visitors_today ?? 0)} />
            <Card title="Haftalik" value={String(analytics?.visits_this_week ?? 0)} />
            <Card title="Yuzlar" value={String(people.length)} />
            <Card title="Asoschilar" value={String(founders.length)} sub={`/ ${FOUNDERS_MAX}`} />
            <Card
              title="Kamera"
              value={health?.camera_active ? 'Yoniq' : 'Ochiq / xato'}
              sub={health?.camera_error ?? undefined}
            />
          </div>
          <div className="mt-4 rounded-xl border border-white/10 bg-black/25 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  Telegram
                </p>
                <p className="mt-1 text-base font-semibold text-slate-100">
                  {health?.telegram?.enabled ? 'Yoniq' : 'Ochiq (token yo‘q)'}
                </p>
                <p className="mt-1 max-w-xl text-xs text-slate-500">
                  {health?.telegram?.enabled
                    ? 'Har bir tanilgan tashrif kanalga yuboriladi (.env).'
                    : 'backend/.env — TELEGRAM_BOT_TOKEN va TELEGRAM_CHAT_ID'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="rounded-lg bg-sky-600 px-3 py-2 text-xs font-medium text-white hover:bg-sky-500"
                  onClick={() =>
                    postTelegramTest()
                      .then((d) => {
                        if (d.ok) setMsg('Telegram: test xabar yuborildi — kanalni tekshiring.');
                        else
                          setMsg(
                            `Telegram xato: ${d.hint || ''} ${d.error || ''}`.trim() ||
                              JSON.stringify(d),
                          );
                      })
                      .catch((e) =>
                        setMsg(e instanceof Error ? e.message : 'Telegram test ishlamadi'),
                      )
                  }
                >
                  Test xabar
                </button>
                <a
                  className="rounded-lg border border-white/15 px-3 py-2 text-xs text-slate-300 hover:bg-white/5"
                  href="http://127.0.0.1:8000/api/health/telegram-debug"
                  target="_blank"
                  rel="noreferrer"
                >
                  Token (getMe)
                </a>
              </div>
            </div>
            <p className="mt-3 text-[11px] text-slate-600">
              Shaxsiy kanal: bot — kanal administratori, «Post messages» yoqilgan. 404 bo‘lsa
              backendni qayta ishga tushiring; havola <code className="text-slate-400">:8000</code>
            </p>
          </div>
        </AdminSection>
        )}

        {activeSection === 'greetings' && (
        <AdminSection
          step={2}
          title="Display — ekrandagi salom"
          hint="Oddiy shablonlar yoki «Aqlli salom»: hafta/oy yo‘qlik + tong–kech. Avval «Aqlli salom»ni yoqing."
        >
          <div className="mb-4 flex gap-1 rounded-lg border border-white/10 bg-black/30 p-1">
            <button
              type="button"
              onClick={() => setGreetingTab('main')}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
                greetingTab === 'main'
                  ? 'bg-orange-600/90 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Oddiy salom
            </button>
            <button
              type="button"
              onClick={() => setGreetingTab('birthday')}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
                greetingTab === 'birthday'
                  ? 'bg-pink-600/80 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Tug‘ilgan kun
            </button>
            <button
              type="button"
              onClick={() => setGreetingTab('vip')}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
                greetingTab === 'vip'
                  ? 'bg-amber-700/90 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              VIP / mehmon
            </button>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-3">
              {greetingTab === 'main' ? (
                <>
                  <Field label="Yuqori qator (katta)">
                    <input
                      className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm focus:border-orange-500/50 focus:outline-none"
                      value={greetingSettings.title_template}
                      onChange={(e) =>
                        setGreetingSettings((s) => ({ ...s, title_template: e.target.value }))
                      }
                      placeholder="Salom, {ism}!"
                    />
                  </Field>
                  <Field label="Pastki qator">
                    <input
                      className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm focus:border-orange-500/50 focus:outline-none"
                      value={greetingSettings.subtitle_template}
                      onChange={(e) =>
                        setGreetingSettings((s) => ({ ...s, subtitle_template: e.target.value }))
                      }
                      placeholder="Rocusga xush kelibsiz!"
                    />
                  </Field>
                  <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-400">
                    <input
                      type="checkbox"
                      checked={greetingSettings.use_smart_rules}
                      onChange={(e) =>
                        setGreetingSettings((s) => ({ ...s, use_smart_rules: e.target.checked }))
                      }
                      className="rounded border-white/20"
                    />
                    Aqlli salom: 7+ kun yo‘q → haftalik xabar; 30+ kun → oylik; soat → tong / kun / kech / tun.
                  </label>
                </>
              ) : greetingTab === 'birthday' ? (
                <>
                  <Field label="Tabrik — yuqori">
                    <input
                      className="w-full rounded-lg border border-pink-500/20 bg-black/40 px-3 py-2 text-sm focus:border-pink-500/40 focus:outline-none"
                      value={greetingSettings.birthday_title_template}
                      onChange={(e) =>
                        setGreetingSettings((s) => ({
                          ...s,
                          birthday_title_template: e.target.value,
                        }))
                      }
                    />
                  </Field>
                  <Field label="Tabrik — pastki">
                    <input
                      className="w-full rounded-lg border border-pink-500/20 bg-black/40 px-3 py-2 text-sm focus:border-pink-500/40 focus:outline-none"
                      value={greetingSettings.birthday_subtitle_template}
                      onChange={(e) =>
                        setGreetingSettings((s) => ({
                          ...s,
                          birthday_subtitle_template: e.target.value,
                        }))
                      }
                    />
                  </Field>
                  <p className="text-xs text-slate-500">
                    Faqat tug‘ilgan kuni + birinchi kirish kunida chiqadi.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-xs text-amber-200/90">
                    Ro‘yxatda odamga <strong className="text-amber-100">VIP</strong> belgisini
                    qo‘ysangiz, oddiy va aqlli salom o‘rniga shu matnlar chiqadi (tug‘ilgan kun
                    ustunligi saqlanadi).
                  </p>
                  <Field label="VIP — birinchi kirish (bugun, UTC)">
                    <input
                      className="w-full rounded-lg border border-amber-500/25 bg-black/40 px-3 py-2 text-sm focus:border-amber-500/50 focus:outline-none"
                      value={greetingSettings.vip_title_template}
                      onChange={(e) =>
                        setGreetingSettings((s) => ({ ...s, vip_title_template: e.target.value }))
                      }
                      placeholder="Hurmatli mehmon, {ism}!"
                    />
                  </Field>
                  <Field label="VIP — pastki qator">
                    <input
                      className="w-full rounded-lg border border-amber-500/25 bg-black/40 px-3 py-2 text-sm focus:border-amber-500/50 focus:outline-none"
                      value={greetingSettings.vip_subtitle_template}
                      onChange={(e) =>
                        setGreetingSettings((s) => ({
                          ...s,
                          vip_subtitle_template: e.target.value,
                        }))
                      }
                    />
                  </Field>
                  <Field label="VIP — qayta kirish: yuqori (ixtiyoriy)">
                    <input
                      className="w-full rounded-lg border border-amber-500/25 bg-black/40 px-3 py-2 text-sm focus:border-amber-500/50 focus:outline-none"
                      value={greetingSettings.vip_title_repeat_template}
                      onChange={(e) =>
                        setGreetingSettings((s) => ({
                          ...s,
                          vip_title_repeat_template: e.target.value,
                        }))
                      }
                      placeholder="Bo‘sh qoldirsangiz — birinchi VIP matni"
                    />
                  </Field>
                  <Field label="VIP — qayta kirish: pastki (ixtiyoriy)">
                    <input
                      className="w-full rounded-lg border border-amber-500/25 bg-black/40 px-3 py-2 text-sm focus:border-amber-500/50 focus:outline-none"
                      value={greetingSettings.vip_subtitle_repeat_template}
                      onChange={(e) =>
                        setGreetingSettings((s) => ({
                          ...s,
                          vip_subtitle_repeat_template: e.target.value,
                        }))
                      }
                      placeholder="Masalan: Yana xush kelibsiz, {ism_qisqa}!"
                    />
                  </Field>
                </>
              )}

              <Field label="Namuna ism (ko‘rish va test)">
                <input
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm focus:border-orange-500/50 focus:outline-none"
                  value={previewName}
                  onChange={(e) => setPreviewName(e.target.value)}
                />
              </Field>
              <p className="text-xs text-slate-600">
                Placeholderlar:{' '}
                <code className="text-orange-300/90">{'{ism}'}</code>,{' '}
                <code className="text-orange-300/90">{'{ism_qisqa}'}</code>,{' '}
                <code className="text-orange-300/90">{'{tashkilot}'}</code>
              </p>
              <button
                type="button"
                disabled={savingGreeting}
                onClick={() => void saveGreeting()}
                className="w-full rounded-xl bg-orange-600 py-3 text-sm font-semibold text-white hover:bg-orange-500 disabled:opacity-50"
              >
                {savingGreeting ? 'Saqlanmoqda...' : 'Barcha matnlarni saqlash'}
              </button>
            </div>

            <div className="rounded-xl border border-white/10 bg-gradient-to-b from-slate-900/80 to-slate-950/90 p-5">
              <p className="text-center text-[10px] uppercase tracking-widest text-slate-500">
                Ko‘rinish
              </p>
              <div className="mt-4 text-center">
                <p className="text-xs text-slate-500">Oddiy</p>
                <p className="mt-2 text-xl font-bold text-white sm:text-2xl">{preview.title}</p>
                <p className="mt-2 text-sm text-orange-300 sm:text-base">{preview.subtitle}</p>
              </div>
              <div className="mt-6 rounded-lg border border-pink-500/25 bg-pink-950/20 p-4 text-center">
                <p className="text-[10px] uppercase tracking-widest text-pink-400/90">
                  Tug‘ilgan kun
                </p>
                <p className="mt-2 font-semibold text-white">{birthdayPreview.title}</p>
                <p className="mt-1 text-sm text-pink-200/90">{birthdayPreview.subtitle}</p>
              </div>
              <div className="mt-6 rounded-lg border border-amber-500/30 bg-amber-950/25 p-4 text-center">
                <p className="text-[10px] uppercase tracking-widest text-amber-300/90">VIP — birinchi</p>
                <p className="mt-2 font-semibold text-white">{vipPreviewFirst.title}</p>
                <p className="mt-1 text-sm text-amber-200/90">{vipPreviewFirst.subtitle}</p>
                <p className="mt-4 text-[10px] uppercase tracking-widest text-amber-400/80">
                  VIP — shu kunda qayta
                </p>
                <p className="mt-2 font-semibold text-white">{vipPreviewRepeat.title}</p>
                <p className="mt-1 text-sm text-amber-200/90">{vipPreviewRepeat.subtitle}</p>
              </div>
              {people[0] && (
                <div className="mt-4 flex flex-col gap-2 border-t border-white/10 pt-4">
                  <button
                    type="button"
                    className="text-center text-xs text-pink-300 underline hover:text-pink-200"
                    onClick={() =>
                      testGreeting(people[0].id, {
                        previewBirthday: true,
                        sampleName: previewName,
                      }).then(() =>
                        setMsg(
                          `Display: tabrik (${previewName.trim() || people[0].full_name})`,
                        ),
                      )
                    }
                  >
                    Tabrikni displayda sinash
                  </button>
                  <button
                    type="button"
                    className="text-center text-xs text-cyan-400 underline hover:text-cyan-300"
                    onClick={() =>
                      testGreeting(people[0].id).then(() =>
                        setMsg(`Display: oddiy salom — ${people[0].full_name}`),
                      )
                    }
                  >
                    Oddiy salom — {people[0].full_name}
                  </button>
                  {people.find((p) => p.is_vip) ? (
                    <>
                      <button
                        type="button"
                        className="text-center text-xs text-amber-300 underline hover:text-amber-200"
                        onClick={() => {
                          const p = people.find((x) => x.is_vip)!;
                          return testGreeting(p.id).then(() =>
                            setMsg(`Display: VIP (birinchi) — ${p.full_name}`),
                          );
                        }}
                      >
                        VIP test — {people.find((p) => p.is_vip)!.full_name}
                      </button>
                      <button
                        type="button"
                        className="text-center text-xs text-amber-200/90 underline hover:text-amber-100"
                        onClick={() => {
                          const p = people.find((x) => x.is_vip)!;
                          return testGreeting(p.id, { vipPreviewRepeat: true }).then(() =>
                            setMsg(`Display: VIP (qayta kirish) — ${p.full_name}`),
                          );
                        }}
                      >
                        VIP qayta kirish shabloni
                      </button>
                    </>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        </AdminSection>
        )}

        {activeSection === 'people' && (
        <AdminSection
          step={3}
          title="Odamlar"
          hint="Yangi yuz qo‘shish va ro‘yxatni boshqarish"
        >
          <form onSubmit={onAddPerson} className="mb-8 rounded-xl border border-indigo-500/25 bg-indigo-950/20 p-4">
            <p className="mb-3 text-sm font-medium text-indigo-200">Yangi odam</p>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Ism-familiya">
                <input
                  id="person-name"
                  required
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm focus:border-indigo-500/50 focus:outline-none"
                  placeholder="Sardor Karimov"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </Field>
              <Field label="Tug‘ilgan kun (ixtiyoriy)">
                <input
                  id="person-birthday"
                  type="date"
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm focus:border-indigo-500/50 focus:outline-none"
                  value={birthday}
                  onChange={(e) => setBirthday(e.target.value)}
                />
              </Field>
              <div>
                <span className="mb-1 block text-xs text-slate-500">Rasm</span>
                <label
                  htmlFor="person-photo"
                  className="flex min-h-[44px] cursor-pointer items-center justify-center rounded-lg border-2 border-dashed border-indigo-400/50 bg-black/30 px-3 py-2 text-sm text-slate-400 hover:bg-black/40"
                >
                  {file ? file.name : 'JPG / PNG tanlang'}
                </label>
                <input
                  id="person-photo"
                  ref={fileInputRef}
                  required
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp"
                  className="sr-only"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
            </div>
            <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm text-amber-200/85">
              <input
                type="checkbox"
                checked={newPersonVip}
                onChange={(e) => setNewPersonVip(e.target.checked)}
                className="rounded border-white/20"
              />
              VIP mehmon (rahbar, xorijiy mehmon — alohida ekran salomi)
            </label>
            <button
              type="button"
              disabled={adding}
              onClick={() => void submitAddPerson()}
              className="mt-4 w-full rounded-xl bg-indigo-600 py-3 text-sm font-bold text-white hover:bg-indigo-500 disabled:opacity-60"
            >
              {adding ? 'Yuz tekshirilmoqda…' : 'Odam qo‘shish'}
            </button>
          </form>

          <ul className="space-y-2">
            {people.map((p) => (
              <PersonListItem key={p.id} person={p} onReload={reload} setMsg={setMsg} />
            ))}
            {people.length === 0 && (
              <li className="py-8 text-center text-sm text-slate-500">Hali hech kim yo‘q</li>
            )}
          </ul>
        </AdminSection>
        )}

        {activeSection === 'founders' && (
        <AdminSection
          step={4}
          title="Asoschilar (founders)"
          hint={`Maksimal ${FOUNDERS_MAX} ta. Avval «Odamlar»da yuzini ro‘yxatga qo‘shing — bu yerda ekranda chiqadigan hero rasm va maxsus salom.`}
        >
          <form
            className="mb-8 rounded-xl border border-amber-500/25 bg-amber-950/15 p-4"
            onSubmit={(e) => {
              e.preventDefault();
              void (async () => {
                if (!founderPersonId || !founderHeroFile) {
                  setMsg('Odam tanlang va hero rasm yuklang.');
                  return;
                }
                if (founders.length >= FOUNDERS_MAX) {
                  setMsg(`Limit: ${FOUNDERS_MAX} asoschi.`);
                  return;
                }
                setAddingFounder(true);
                setMsg('');
                try {
                  const fd = new FormData();
                  fd.append('person_id', founderPersonId);
                  fd.append('welcome_title', founderTitle.trim());
                  fd.append('welcome_subtitle', founderSubtitle.trim());
                  if (founderTitleRepeat.trim()) {
                    fd.append('welcome_title_repeat', founderTitleRepeat.trim());
                  }
                  if (founderSubtitleRepeat.trim()) {
                    fd.append('welcome_subtitle_repeat', founderSubtitleRepeat.trim());
                  }
                  fd.append('sort_order', founderSort.trim() || '0');
                  fd.append('hero_image', founderHeroFile);
                  await addFounder(fd);
                  setFounderPersonId('');
                  setFounderHeroFile(null);
                  setFounderTitleRepeat('');
                  setFounderSubtitleRepeat('');
                  if (founderHeroRef.current) founderHeroRef.current.value = '';
                  setMsg('Asoschi qo‘shildi');
                  await reload();
                } catch (err) {
                  setMsg(err instanceof Error ? err.message : 'Xato');
                } finally {
                  setAddingFounder(false);
                }
              })();
            }}
          >
            <p className="mb-3 text-sm font-medium text-amber-100/90">Yangi asoschi</p>
            <div className="grid gap-3 lg:grid-cols-2">
              <Field label="Ro‘yxatdagi odam">
                <select
                  required
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm focus:border-amber-500/40 focus:outline-none"
                  value={founderPersonId}
                  onChange={(e) => setFounderPersonId(e.target.value)}
                >
                  <option value="">— tanlang —</option>
                  {people
                    .filter((p) => !founders.some((f) => f.person_id === p.id))
                    .map((p) => (
                      <option key={p.id} value={String(p.id)}>
                        {p.full_name} (id {p.id})
                      </option>
                    ))}
                </select>
              </Field>
              <Field label="Ro‘yxat tartibi (faqat admin, ixtiyoriy)">
                <input
                  type="number"
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm focus:border-amber-500/40 focus:outline-none"
                  value={founderSort}
                  onChange={(e) => setFounderSort(e.target.value)}
                  title="Kichik raqam = ro‘yxatda yuqorida. Ekran salomiga ta’sir qilmaydi."
                />
              </Field>
              <Field label="Yuqori qator (katta matn)">
                <input
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm focus:border-amber-500/40 focus:outline-none"
                  value={founderTitle}
                  onChange={(e) => setFounderTitle(e.target.value)}
                  placeholder="{tashkilot}ga xush kelibsiz!"
                />
              </Field>
              <Field label="Pastki qator (masalan lavozim)">
                <input
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm focus:border-amber-500/40 focus:outline-none"
                  value={founderSubtitle}
                  onChange={(e) => setFounderSubtitle(e.target.value)}
                  placeholder="{ism} — diip.uz asoschisi"
                />
              </Field>
              <Field label="Qayta kirish: yuqori qator (ixtiyoriy)">
                <input
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm focus:border-amber-500/40 focus:outline-none"
                  value={founderTitleRepeat}
                  onChange={(e) => setFounderTitleRepeat(e.target.value)}
                  placeholder="Birinchi matn bilan bir xil qoldirish uchun bo‘sh qoldiring"
                />
              </Field>
              <Field label="Qayta kirish: pastki qator (ixtiyoriy)">
                <input
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm focus:border-amber-500/40 focus:outline-none"
                  value={founderSubtitleRepeat}
                  onChange={(e) => setFounderSubtitleRepeat(e.target.value)}
                  placeholder="Masalan: yana xush kelibsiz, {ism}!"
                />
              </Field>
              <div className="lg:col-span-2">
                <span className="mb-1 block text-xs text-slate-500">
                  Ekranda chiqadigan portret (hero rasm, yuz bilan bir xil bo‘lishi shart emas)
                </span>
                <label className="flex min-h-[44px] cursor-pointer items-center justify-center rounded-lg border-2 border-dashed border-amber-400/40 bg-black/30 px-3 py-2 text-sm text-slate-400 hover:bg-black/40">
                  {founderHeroFile ? founderHeroFile.name : 'JPG / PNG — hero rasm'}
                  <input
                    ref={founderHeroRef}
                    type="file"
                    accept=".jpg,.jpeg,.png,.webp"
                    className="sr-only"
                    onChange={(e) => setFounderHeroFile(e.target.files?.[0] ?? null)}
                  />
                </label>
              </div>
            </div>
            <p className="mt-2 text-[11px] text-slate-500">
              Shablon: <code className="text-amber-200/80">{'{ism}'}</code>,{' '}
              <code className="text-amber-200/80">{'{ism_qisqa}'}</code>,{' '}
              <code className="text-amber-200/80">{'{tashkilot}'}</code>
              <br />
              «Ro‘yxat tartibi» faqat shu sahifadagi ro‘yxatni tartiblash uchun; displayda navbat kamera
              bo‘yicha.
            </p>
            <button
              type="submit"
              disabled={addingFounder || founders.length >= FOUNDERS_MAX}
              className="mt-4 w-full rounded-xl bg-amber-600 py-3 text-sm font-bold text-white hover:bg-amber-500 disabled:opacity-50"
            >
              {addingFounder
                ? 'Saqlanmoqda…'
                : founders.length >= FOUNDERS_MAX
                  ? 'Limit to‘ldi'
                  : 'Asoschini saqlash'}
            </button>
          </form>

          <ul className="space-y-3">
            {founders.map((f) => (
              <li
                key={f.id}
                className="flex flex-col gap-2 rounded-xl border border-white/10 bg-black/25 px-4 py-3 text-sm"
              >
                <div className="flex flex-wrap items-center gap-4">
                <img
                  src={f.hero_image_url}
                  alt=""
                  className="h-16 w-16 rounded-xl object-cover ring-1 ring-amber-400/30"
                />
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-100">{f.full_name}</p>
                  <p className="truncate text-xs text-slate-500">{f.welcome_title}</p>
                  <p className="truncate text-xs text-amber-200/80">{f.welcome_subtitle}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  <button
                    type="button"
                    className="text-cyan-400 hover:underline"
                    onClick={() =>
                      testGreeting(f.person_id).then(() =>
                        setMsg(`Display: asoschi (birinchi) — ${f.full_name}`),
                      )
                    }
                  >
                    Test birinchi
                  </button>
                  <button
                    type="button"
                    className="text-cyan-300 hover:underline"
                    onClick={() =>
                      testGreeting(f.person_id, { founderPreviewRepeat: true }).then(() =>
                        setMsg(`Display: asoschi (qayta kirish) — ${f.full_name}`),
                      )
                    }
                  >
                    Test qayta
                  </button>
                  <button
                    type="button"
                    className="text-red-400 hover:underline"
                    onClick={() =>
                      deleteFounder(f.id)
                        .then(() => {
                          setMsg('Asoschi olib tashlandi');
                          return reload();
                        })
                        .catch((e) => setMsg(e instanceof Error ? e.message : 'Xato'))
                    }
                  >
                    O‘chirish
                  </button>
                </div>
                </div>
                <FounderRepeatEditor founder={f} onSaved={() => void reload()} setMsg={setMsg} />
              </li>
            ))}
            {founders.length === 0 && (
              <li className="py-6 text-center text-sm text-slate-500">Hali asoschi yo‘q</li>
            )}
          </ul>
        </AdminSection>
        )}

        {activeSection === 'videos' && (
        <AdminSection step={5} title="Videolar" hint="Display aylanishi (MP4)">
          <label className="mb-4 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-white/20 px-4 py-2 text-sm hover:bg-white/5">
            MP4 yuklash
            <input type="file" accept="video/mp4" className="hidden" onChange={onUploadVideo} />
          </label>
          <ul className="divide-y divide-white/5 rounded-xl border border-white/10 bg-black/20">
            {videos.map((v) => (
              <li
                key={v.id}
                className="flex items-center justify-between gap-2 px-4 py-3 text-sm"
              >
                <span className="truncate">{v.title || v.filename}</span>
                <button
                  type="button"
                  className="shrink-0 text-red-400 hover:underline"
                  onClick={() => deleteVideo(v.id).then(reload)}
                >
                  O‘chirish
                </button>
              </li>
            ))}
            {videos.length === 0 && (
              <li className="px-4 py-8 text-center text-slate-500">Video yo‘q</li>
            )}
          </ul>
        </AdminSection>
        )}

        {activeSection === 'analytics' && analytics && analytics.peak_hours.length > 0 && (
          <AdminSection step={6} title="Band soatlar" hint="Haftalik taqsimot">
            <div className="h-52 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analytics.peak_hours}>
                  <XAxis dataKey="hour" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#22d3ee" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </AdminSection>
        )}

        {activeSection === 'analytics' && analytics && analytics.peak_hours.length === 0 && (
          <p className="rounded-xl border border-white/10 bg-black/20 px-4 py-8 text-center text-sm text-slate-500">
            Hali band soatlar uchun ma&apos;lumot yo&apos;q.
          </p>
        )}

        {activeSection === 'visits' && (
        <AdminSection step={7} title="Oxirgi tashriflar" hint="Oxirgi yozuvlar">
          <div className="overflow-x-auto rounded-xl border border-white/10">
            <table className="w-full min-w-[280px] text-left text-sm">
              <thead className="border-b border-white/10 bg-black/30 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Ism</th>
                  <th className="px-4 py-3 font-medium">Vaqt</th>
                </tr>
              </thead>
              <tbody>
                {visits.map((v) => (
                  <tr key={v.id} className="border-b border-white/5 last:border-0">
                    <td className="px-4 py-2.5">{v.full_name}</td>
                    <td className="px-4 py-2.5 text-slate-500">
                      {new Date(v.visited_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
                {visits.length === 0 && (
                  <tr>
                    <td colSpan={2} className="px-4 py-8 text-center text-slate-500">
                      Tashrif yo‘q
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </AdminSection>
        )}
        </main>
      </div>
    </div>
  );
}

function AdminSection({
  step,
  title,
  hint,
  children,
}: {
  step: number;
  title: string;
  hint: string;
  children: ReactNode;
}) {
  return (
    <section className="scroll-mt-20 rounded-2xl border border-white/10 bg-white/[0.03] p-5 shadow-lg shadow-black/20 sm:p-6">
      <div className="mb-5 flex flex-wrap items-baseline gap-2 border-b border-white/10 pb-4">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/10 text-xs font-bold text-slate-300">
          {step}
        </span>
        <div>
          <h2 className="text-base font-semibold text-slate-100 sm:text-lg">{title}</h2>
          <p className="text-xs text-slate-500">{hint}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs text-slate-500">{label}</label>
      {children}
    </div>
  );
}

function PersonListItem({
  person,
  onReload,
  setMsg,
}: {
  person: Person;
  onReload: () => Promise<void>;
  setMsg: (m: string) => void;
}) {
  const [bday, setBday] = useState(person.birthday?.slice(0, 10) ?? '');

  useEffect(() => {
    setBday(person.birthday?.slice(0, 10) ?? '');
  }, [person.birthday, person.id]);

  const saveBirthday = async () => {
    try {
      const updated = await updatePersonBirthday(person.id, bday || null);
      setBday(updated.birthday?.slice(0, 10) ?? '');
      setMsg(`Tug‘ilgan kun saqlandi: ${person.full_name}`);
      await onReload();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Saqlanmadi');
    }
  };

  return (
    <li className="rounded-xl border border-white/10 bg-black/25 px-4 py-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="font-medium text-slate-100">{person.full_name}</span>
          {person.is_vip ? (
            <span className="ml-1.5 rounded-md bg-amber-600/50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-100">
              VIP
            </span>
          ) : null}
          <span className="ml-2 text-slate-500">{person.total_visits} tashrif</span>
        </div>
        <div className="flex flex-wrap gap-3 text-xs">
          <button
            type="button"
            className="text-cyan-400 hover:underline"
            onClick={() => testGreeting(person.id).then(() => setMsg(`Test: ${person.full_name}`))}
          >
            Display test
          </button>
          {person.is_vip ? (
            <button
              type="button"
              className="text-amber-300 hover:underline"
              onClick={() =>
                testGreeting(person.id, { vipPreviewRepeat: true }).then(() =>
                  setMsg(`VIP qayta shablon: ${person.full_name}`),
                )
              }
            >
              VIP qayta
            </button>
          ) : null}
          {bday && (
            <button
              type="button"
              className="text-pink-400 hover:underline"
              onClick={() =>
                testGreeting(person.id, { simulateBirthday: true }).then(() =>
                  setMsg(`Tabrik test: ${person.full_name}`),
                )
              }
            >
              Tabrik
            </button>
          )}
          <button
            type="button"
            className="text-red-400 hover:underline"
            onClick={() => deletePerson(person.id).then(onReload)}
          >
            O‘chirish
          </button>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-white/5 pt-3">
        <span className="text-xs text-slate-500">Tug‘ilgan kun</span>
        <input
          type="date"
          className="rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs"
          value={bday}
          onChange={(e) => setBday(e.target.value)}
        />
        <button
          type="button"
          className="rounded-md bg-white/10 px-2 py-1 text-xs hover:bg-white/15"
          onClick={() => void saveBirthday()}
        >
          Saqlash
        </button>
        <label className="flex cursor-pointer items-center gap-1.5 text-xs text-amber-200/90">
          <input
            type="checkbox"
            checked={person.is_vip}
            onChange={(e) => {
              const v = e.target.checked;
              void updatePersonVip(person.id, v)
                .then(() => onReload())
                .then(() =>
                  setMsg(
                    v ? `VIP yoqildi: ${person.full_name}` : `VIP o‘chirildi: ${person.full_name}`,
                  ),
                )
                .catch((err) => setMsg(err instanceof Error ? err.message : 'Xato'));
            }}
            className="rounded border-white/20"
          />
          VIP salom
        </label>
      </div>
    </li>
  );
}

function Card({ title, value, sub }: { title: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-gradient-to-br from-white/[0.08] to-transparent p-4">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{title}</p>
      <p className="mt-1 text-xl font-semibold sm:text-2xl">{value}</p>
      {sub && <p className="mt-1 line-clamp-2 text-xs text-amber-400/90">{sub}</p>}
    </div>
  );
}
