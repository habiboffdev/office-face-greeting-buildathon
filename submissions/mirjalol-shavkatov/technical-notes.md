# FaceGreet.uz Technical Architecture

## Executive Summary

FaceGreet is a facial recognition-based employee greeting system deployed on Base44 (a Backend-as-a-Service platform). It combines real-time face detection (client-side), personalized greeting generation (LLM-powered), and operational alerts (Telegram integration) to create a seamless office arrival experience.

**Key differentiators:**
- Runs on minimal hardware (cheap camera + CPU server, no GPU required)
- Multilingual support (EN, UZ, RU) with Uzbekistan holidays built-in
- Sub-second recognition latency
- Cost: ~$20/month operational expenses
- Designed for mid-market (50–500 employees)

---

## System Components

### 1. Frontend (React + Vite)

**Pages:**
- `/` (Home) — Landing page with navigation + quick start
- `/display` — Kiosk display (fullscreen video + camera overlay)
- `/admin` — Admin dashboard (employees, videos, analytics, settings)
- `/analytics` — Attendance trends, department breakdown, peak hours

**Core Components:**

| Component | Purpose |
|-----------|---------|
| `FaceScanner` | Real-time face detection using face-api.js; outputs descriptors |
| `GreetingOverlay` | Displays employee info + greeting; triggers confetti on birthdays |
| `VideoPlayer` | Auto-playing video playlist with seamless transitions |
| `IdleScreen` | Branded screensaver (customizable company colors) |
| `EmployeeManager` | Admin CRUD for employees + bulk CSV import |
| `VideoManager` | Admin CRUD for playlist videos |
| `CompanySettingsManager` | Configure language, colors, debug mode, Telegram ID, AI toggles |
| `WhosInDashboard` | Real-time attendance grid (employees currently "in") |
| `AIChat` | Floating AI assistant (context-aware help about the platform) |
| `AdminGuard` | Route protection (redirects non-admins to login) |

**Libraries:**
- **face-api.js** — Face detection & descriptor extraction (pre-trained TensorFlow models)
- **Framer Motion** — Smooth greeting entry/exit animations
- **Recharts** — Analytics dashboards (line charts, bar charts, pie charts)
- **React Router** — SPA navigation
- **TailwindCSS + shadcn/ui** — Responsive, accessible UI components
- **React Query** — Data fetching + caching (invalidates on entity updates)

**Face Detection Flow:**
```
Camera Feed (video element)
    ↓
FaceScanner.detectFace() [~100ms]
    ↓
face-api.detectAllFaces() + computeFaceDescriptors()
    ↓
Compare against Employee face_descriptor array [<1ms]
    ↓
If confidence > 0.6, find best match [Euclidean distance]
    ↓
onPersonRecognized() callback → handleRecognitionAlert (backend)
```

**Key Implementation Details:**
- Face descriptor = 128-point vector (face-api outputs)
- Distance threshold: 0.6 (Euclidean; lower = closer match)
- Cooldown: 30 seconds between alerts (prevent duplicate greetings)
- Camera selection: Allows user to pick from multiple cameras on system

---

### 2. Backend (Deno + Base44)

**Serverless Functions:**

#### `generateSmartGreetings`
- **Trigger:** Daily at 00:00 UTC (scheduled automation)
- **Frequency:** Once per day
- **API Cost:** 1 Gemini Flash call per employee
- **Output:** SmartGreeting records (valid 24h)

**Algorithm:**
1. Fetch all active employees
2. For each employee:
   - Query RecognitionLog for last 7 days
   - Check if today is birthday (Employee.birth_date)
   - Check if today is holiday (HolidayDate)
   - Determine greeting context:
     - **Birthday** → "Happy Birthday, [Name]! 🎉"
     - **Holiday** → "Happy [Holiday]! [Name]"
     - **Long absent** (>14 days) → "Welcome back, [Name]! Long time no see!"
     - **Frequent visitor** (3+ times this week) → "Great to see you again, [Name]!"
     - **Time-based** → "Good morning/afternoon/evening, [Name]!"
   - Call Gemini Flash LLM with context
   - Store SmartGreeting with type + text
3. Clean up expired greetings (older than yesterday)

**Code Snippet:**
```deno
const base44 = createClientFromRequest(req);
const employees = await base44.asServiceRole.entities.Employee.filter({ is_active: true });

for (const emp of employees) {
  const greeting = await generateGreetingForEmployee(emp); // LLM call
  await base44.asServiceRole.entities.SmartGreeting.create(greeting);
}
```

#### `handleRecognitionAlert`
- **Trigger:** On-demand (called from FaceScanner when face matched)
- **Frequency:** Per recognition (~1–5 per minute during office hours)
- **Output:** RecognitionLog entry + Telegram alert

**Flow:**
1. Receives recognition data (employee_id, timestamp)
2. Creates RecognitionLog entry (for analytics)
3. Fetches SmartGreeting for today
4. Calls `sendTelegramAlert` with formatted message
5. Returns greeting data to frontend (GreetingOverlay renders)

#### `sendTelegramAlert`
- **Trigger:** Called by other functions
- **API Cost:** Free (Telegram Bot API)
- **Output:** Telegram message to admin's chat

**Message Format:**
```
Regular: "👋 [Name] arrived at 09:15 AM"
Birthday: "🎂 Happy Birthday, [Name]! 🎉"
Daily: "📊 Today: 12 arrivals, 2 birthdays, 5 meetings"
```

#### `dailyBirthdayCheck`
- **Trigger:** Daily at 08:00 UTC (scheduled automation)
- **Output:** Single Telegram message with daily summary

**Data:**
- Total arrivals today
- Birthdays today (count)
- Meetings scheduled (count)
- Peak arrival time
- Top department by arrivals

---

### 3. Database (Base44 Entities)

**Entity Design Rationale:**

| Entity | Why This Design |
|--------|-----------------|
| **Employee** | Single source of truth for person; denormalized dept for fast queries |
| **RecognitionLog** | Immutable log of arrivals; indexed by employee_id + created_date for analytics |
| **SmartGreeting** | Daily cache (1 per employee); prevents LLM thrashing on repeated recognitions |
| **CompanySettings** | Singleton (1 per company); controls UI behavior + API toggles |
| **Video** | Playlist ordered by `order` field; soft-delete via `is_active` |
| **Announcement** | Cached in memory; TTL via `expires_at`; priority for styling |
| **Meeting** | Time-based queries for "upcoming meetings" in greeting overlay |
| **HolidayDate** | Yearly reference; queried daily by greeting generator |

**Relationships:**
```
Employee ──┐
           ├── RecognitionLog
           ├── SmartGreeting
           └── Meeting
```

**Row-Level Security (RLS):**
- **Public read:** Employee, Video, Announcement, HolidayDate (displayed to all)
- **Admin write:** Only admins can create/update/delete employees, videos, etc.
- **Admin read:** RecognitionLog, Meeting (attendance data)

---

### 4. Integrations

#### Telegram Bot API
- **Authentication:** Bearer token (TELEGRAM_BOT_TOKEN secret)
- **Endpoint:** `https://api.telegram.org/bot{token}/sendMessage`
- **Payload:** `{ chat_id, text, parse_mode: "HTML" }`
- **Rate Limit:** 30 msgs/second per bot
- **Cost:** Free

#### Google Gemini Flash LLM
- **Model:** `gemini-3-flash` (fastest, cheapest tier)
- **Use Case:** Daily greeting generation
- **Cost:** ~$0.075 per 1M input tokens = ~$3–8/month for 50 employees
- **API:** base44.integrations.Core.InvokeLLM()

#### face-api.js (TensorFlow.js)
- **Models:** Tiny Face Detector + Face Expression Net + Face Recognition Net
- **Download Size:** ~170MB (downloaded once, cached in browser)
- **Latency:** 100–200ms per frame (CPU; GPU: 50ms)
- **Accuracy:** ~95% on well-lit frontal faces; drops to 70% on side profiles

---

## Data Flow Diagrams

### Recognition Flow (Real-time)
```
Camera Feed
    ↓
FaceScanner (React)
    ├─ Load face-api models
    ├─ Detect faces in video
    ├─ Extract 128-point descriptor
    ├─ Compare against Employee.face_descriptor[]
    └─ If match confidence > 0.6:
        ↓
    handleRecognitionAlert (backend)
        ├─ Create RecognitionLog entry
        ├─ Fetch SmartGreeting for today
        └─ Call sendTelegramAlert()
            ↓
        Telegram API
            ↓
        Admin receives: "👋 [Name] arrived at 09:15"
        
        ↓ (return greeting to frontend)
        
    GreetingOverlay (React)
        ├─ Fade in employee photo
        ├─ Display greeting text
        ├─ Show birthday badge (if applicable)
        ├─ List upcoming meetings
        └─ Trigger confetti (if birthday)
        
        ↓ (after 5 seconds)
        
    Fade out, return to video
```

### Daily Greeting Generation (Scheduled)
```
Scheduled: 00:00 UTC daily
    ↓
generateSmartGreetings()
    ├─ Fetch all employees
    ├─ For each employee:
    │   ├─ Query last 7 days of RecognitionLog
    │   ├─ Check Employee.birth_date (today?)
    │   ├─ Check HolidayDate (today?)
    │   ├─ Determine context (birthday, holiday, frequent, etc.)
    │   └─ Call Gemini Flash:
    │       Input: "Generate greeting for [Name] in context: [context]"
    │       Output: "Hey [Name], great to see you again!"
    │   └─ Create SmartGreeting(greeting_text, greeting_type, valid_until: tomorrow)
    ├─ Delete expired greetings (older than yesterday)
    └─ Done
```

### Daily Summary (Scheduled)
```
Scheduled: 08:00 UTC daily
    ↓
dailyBirthdayCheck()
    ├─ Query RecognitionLog WHERE created_date = TODAY
    ├─ Query Employee WHERE birth_date = TODAY
    ├─ Query Meeting WHERE start_time BETWEEN 00:00–23:59 TODAY
    ├─ Format:
    │   "📊 Daily Summary:\n"
    │   "✅ 12 arrivals\n"
    │   "🎂 2 birthdays\n"
    │   "📅 5 meetings\n"
    │   "⏰ Peak: 09:00–10:00 (6 arrivals)"
    └─ Call sendTelegramAlert(summary)
```

---

## Deployment Architecture

```
GitHub Repository
    ↓
Base44 CI/CD (auto-deploy on push)
    ├─ Build React → /dist
    ├─ Bundle functions → /functions
    └─ Deploy to Base44 Cloud
        ↓
    Frontend (React SPA)
    ├─ Hosted at: https://facegreet.uz (custom domain)
    ├─ CDN-cached static assets
    └─ Hot reload on code changes
    
    Backend (Deno Functions)
    ├─ Serverless endpoints
    ├─ Auto-scaling
    └─ Scheduled jobs (automations)
    
    Database (Base44 Entities)
    ├─ PostgreSQL-backed
    ├─ Automatic backups
    └─ Row-level security enforcement
```

**Environment Variables:**
- `TELEGRAM_BOT_TOKEN` — Telegram Bot API key (secret)
- `VITE_BASE44_APP_ID` — Public app ID (for frontend SDK initialization)

---

## Performance & Scalability

### Benchmarks (on modern laptop: i7, 8GB RAM)

| Operation | Latency | Notes |
|-----------|---------|-------|
| Face detection | 100–200ms | face-api.js on CPU |
| Descriptor comparison | <1ms | 50 employees max |
| SmartGreeting fetch | 50–100ms | Database query |
| Greeting overlay render | <50ms | React re-render |
| **Total end-to-end** | **~300ms** | Detection → greeting visible |

### Scalability Limits

| Resource | Current | Bottleneck |
|----------|---------|-----------|
| Employees | 500+ | Descriptor comparison is O(n) |
| Daily recognitions | 1000s | No issues (async logging) |
| Concurrent admins | 10+ | UI state management |
| Videos in playlist | 100+ | No issues (sequential playback) |

**To scale beyond 500 employees:** Use k-d tree or FAISS indexing for face descriptor lookups (trade speed for memory).

---

## Security Architecture

### Authentication & Authorization
- Base44 handles user signup/login
- Role-based access control (RBAC):
  - **Admin:** Full access to employee management, analytics, settings
  - **User:** Read-only access to Home + Display pages
  - **Public:** Display page accessible without login (for kiosk mode)

### Data Protection
- API keys stored in Base44 secrets (not in code)
- Row-level security (RLS) enforces data access rules
- Face descriptors are binary vectors (no PII recovery possible)
- Employee photos are public (displayed on kiosk)
- Recognition logs visible to admins only

### Network Security
- HTTPS enforced (Base44 auto-provides SSL)
- Telegram alerts use token-based auth
- No client-side face images stored (processed & discarded)

---

## Implementation Decisions & Trade-offs

### Why face-api.js (client-side) vs. Cloud Vision API?
**Chosen:** face-api.js (TensorFlow.js, client-side)
- ✅ No external API calls (faster, private, offline-capable)
- ✅ Free (no per-call charges)
- ✅ Works on CPU (no GPU required)
- ❌ Accuracy drops on side profiles / poor lighting
- ❌ Initial model download (~170MB)

**Alternative:** Google Cloud Vision API
- ✅ Better accuracy (especially odd angles)
- ❌ ~$1–2 per 1000 requests = high cost
- ❌ Network latency + rate limiting

**Decision:** face-api.js is cost-effective for the use case; facial recognition is designed for frontal faces anyway.

### Why Gemini Flash (not GPT)?
**Chosen:** Gemini Flash
- ✅ Cheapest LLM ($0.075/1M tokens)
- ✅ Fast inference (~2–3s)
- ✅ Good multilingual support (EN, UZ, RU)
- ✅ Integrated with Base44

**Alternative:** GPT-4o
- ❌ 10x more expensive
- ❌ Overkill for greeting generation

### Why SmartGreeting table (caching)?
**Chosen:** Cache greetings daily
- ✅ 1 LLM call per employee per day (not per recognition)
- ✅ Instant greeting retrieval at recognition time
- ❌ Greetings are stale (generated at midnight)

**Alternative:** Generate on-the-fly
- ✅ Always fresh greetings
- ❌ ~50–100 LLM calls per employee per day = expensive

**Decision:** Daily caching is cost-effective for the greeting format; personalization comes from context (birthday, meeting, etc.), not real-time analysis.

### Why Telegram (not Email/SMS)?
**Chosen:** Telegram
- ✅ Free
- ✅ Instant delivery
- ✅ Rich formatting (HTML, emojis)
- ✅ Popular in Central Asia
- ❌ Requires Telegram account

**Alternative:** Email
- ❌ Delayed (10–60s)
- ❌ Less engaging

### Why Base44 (not Firebase/Supabase)?
**Chosen:** Base44
- ✅ All-in-one (frontend hosting + backend + database)
- ✅ No boilerplate (auto-generated SDK)
- ✅ Built-in automations (scheduled jobs)
- ✅ Custom domain support
- ❌ Smaller ecosystem (compared to Firebase)

---

## Testing & Quality Assurance

### Manual Testing Checklist
- [ ] Face detection works at various distances (0.5m, 1m, 2m)
- [ ] Greeting appears within 300ms of detection
- [ ] Unrecognized person doesn't interrupt video
- [ ] Birthday detection triggers correctly
- [ ] Telegram alerts sent (check chat)
- [ ] Admin CRUD operations (add/edit/delete employee)
- [ ] Bulk CSV import works
- [ ] Analytics dashboard updates in real-time
- [ ] Idle screen appears after X minutes
- [ ] AI chat responds to platform questions

### Monitoring & Debugging
- **Debug Panel:** Enable in settings to see face detection overlay
- **Console Logs:** Check browser console for face-api warnings
- **Backend Logs:** View function execution logs in Base44 dashboard
- **Analytics:** Track daily arrivals, errors, peak times

---

## Known Limitations & Future Work

### Current Limitations
1. **Single-angle recognition** — Struggles with side profiles (solve: multi-angle enrollment)
2. **Lighting sensitivity** — Poor recognition in backlighting (solve: camera placement optimization)
3. **No liveness detection** — Can be spoofed with a photo (solve: add blink + head movement check)
4. **No emotion detection** — Greetings are static (solve: integrate emotion API)
5. **Single camera** — Only one recognition feed per kiosk (solve: multi-stream processing)

### Roadmap
- **Q3 2026:** Multi-angle face enrollment (3 photos: front, left, right)
- **Q4 2026:** Emotion detection for mood-based greetings
- **Q1 2027:** Exit detection & dwell time analytics
- **Q2 2027:** Multi-location support (central dashboard)
- **Q3 2027:** BambooHR / ADP integration for auto-synced employee data
- **Q4 2027:** Slack / Teams status auto-update

---

## References

- **face-api.js:** https://github.com/vladmandic/face-api
- **Base44 Docs:** https://base44.com/docs
- **Telegram Bot API:** https://core.telegram.org/bots/api
- **Google Gemini:** https://ai.google.dev
- **TensorFlow.js:** https://www.tensorflow.org/js

---

**Document Version:** 1.0  
**Last Updated:** May 15, 2026  
**Author:** FaceGreet.uz Development Team