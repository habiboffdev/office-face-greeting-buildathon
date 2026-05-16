# FaceGreet.uz [https://facegreet.uz/]

**AI-powered facial recognition system for personalized employee greetings and office attendance tracking.**

FaceGreet transforms office entry into a memorable, personalized experience using real-time face detection and AI-generated dynamic greetings. Built for Uzbekistan, it supports multilingual content, local holidays, and Telegram integration for instant alerts.

---

## Features

- **Real-time Face Recognition** — Identifies employees as they pass by a camera
- **Personalized AI Greetings** — Dynamic, context-aware greetings (birthdays, time-of-day, long absences)
- **Multilingual Support** — English, Uzbek (O'zbekcha), Russian
- **Video Playlist Display** — Auto-playing background media with seamless transitions
- **Attendance Analytics** — Track arrivals, departures, dwell time, department-level insights
- **Telegram Alerts** — Real-time notifications and daily summaries sent directly to Telegram
- **Admin Dashboard** — Manage employees, videos, announcements, meetings, and company settings
- **Idle Screensaver** — Branded idle screen when no activity detected
- **Holiday Support** — Built-in Uzbek holidays + custom holiday management

---

## Tech Stack

**Frontend:**
- React 18 + Vite
- TailwindCSS + shadcn/ui components
- face-api.js (face detection & recognition)
- Framer Motion (animations)
- Recharts (analytics dashboards)
- React Router (navigation)

**Backend:**
- Deno (serverless functions)
- Base44 Platform (authentication, database, API management)
- Telegram Bot API (alert delivery)
- Google Gemini Flash LLM (greeting generation)

**Database:**
- Base44 Entities (Employee, RecognitionLog, SmartGreeting, CompanySettings, Video, Announcement, Meeting, HolidayDate)

**Deployment:**
- Base44 Cloud (frontend + backend)
- GitHub (source control)

---

## Installation & Setup

### Prerequisites
- Node.js 18+ and npm
- Git
- Base44 account (free tier available at [base44.com](https://base44.com))
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))

### Local Development

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd facegreet.uz
   npm install
   ```

2. **Set up environment variables:**
   Create `.env.local` in the project root:
   ```
   VITE_BASE44_APP_ID=<your-app-id>
   TELEGRAM_BOT_TOKEN=<your-telegram-token>
   ```
   Get your app ID from Base44 dashboard → Settings → App ID.

3. **Start development server:**
   ```bash
   npm run dev
   ```
   Open [http://localhost:5173](http://localhost:5173)

4. **First-time setup (Admin):**
   - Login with admin credentials
   - Go to Admin dashboard
   - Run the onboarding wizard (set company name, logo, colors)
   - Add employees with face photos
   - Add videos to the playlist
   - Set Telegram chat ID for alerts

### Production Deployment

FaceGreet deploys directly on Base44:
1. Push code to GitHub
2. Base44 auto-builds and deploys on every commit
3. Configure custom domain in Base44 dashboard

---

## Usage

### For End Users (Display Mode)
1. Navigate to `/display` on a kiosk/desktop
2. System auto-plays videos from the playlist
3. Camera detects faces in real-time
4. Recognized employees see personalized greeting overlay
5. Unrecognized faces don't interrupt video playback

### For Admins
1. **Employees:** Add/edit employee profiles with photos (face descriptors auto-generated)
2. **Videos:** Upload or link videos to customize the display playlist
3. **Analytics:** View real-time attendance, department breakdown, peak hours
4. **Settings:** Configure language, brand colors, debug mode, idle timeout
5. **Announcements:** Create priority-based messages displayed on recognition
6. **Meetings:** Schedule employee meetings (shown in greeting overlay)
7. **Telegram:** Set chat ID to receive alerts and daily summaries

---

## System Architecture

```
┌─────────────────────┐
│  Display Kiosk      │
│  (Camera + Monitor) │
└──────────┬──────────┘
           │
    ┌──────▼──────┐
    │  FaceScanner│  (face-api.js)
    │  Component  │  Real-time face detection
    └──────┬──────┘
           │
    ┌──────▼─────────────┐
    │ Recognition Engine │
    │ (Face descriptor   │
    │  comparison)       │
    └──────┬─────────────┘
           │
    ┌──────▼──────────────────┐
    │  Base44 Backend         │
    │  - Entity queries       │
    │  - Recognition logs     │
    │  - Smart greetings      │
    └──────┬──────────────────┘
           │
    ┌──────┴─────────┬──────────────┐
    │                │              │
┌───▼────┐  ┌───────▼────┐  ┌─────▼─────┐
│Database │  │ Telegram   │  │ Gemini LLM│
│(Entities)│  │ Bot API    │  │(Greetings)│
└────────┘  └────────────┘  └───────────┘
```

### Key Flows

**Recognition Flow:**
1. FaceScanner detects face in camera feed
2. Extracts 128-point face descriptor
3. Compares against all employee descriptors
4. If match confidence > 80%, triggers `handleRecognitionAlert`
5. Creates RecognitionLog entry
6. GreetingOverlay renders for 5 seconds with:
   - Employee name + photo
   - Personalized greeting (from SmartGreeting)
   - Birthday indicator (if applicable)
   - Upcoming meetings
   - Top announcement (if active)

**Daily Greeting Generation:**
1. `generateSmartGreetings` runs daily at midnight UTC
2. Fetches all active employees
3. Analyzes RecognitionLog for visit patterns
4. Queries HolidayDate for today
5. Generates context-aware greetings (Gemini Flash LLM)
6. Stores in SmartGreeting table with expiry = tomorrow midnight
7. Purges expired greetings

**Telegram Alert Flow:**
1. Recognition triggered → `handleRecognitionAlert` calls `sendTelegramAlert`
2. For birthdays: Special "Happy Birthday!" format
3. For regular arrivals: "Person X arrived at HH:MM"
4. Daily summary: Sent by `dailyBirthdayCheck` at 8 AM UTC
5. Format: "10 arrivals today, 2 birthdays, 1 meeting scheduled"

---

## Data Model

### Core Entities

**Employee**
- `name`: Full name
- `position`: Job title
- `department`: Department name
- `photo_url`: Face photo (publicly visible)
- `face_descriptor`: 128-point vector (face-api.js format)
- `greeting_message`: Custom override greeting
- `birth_date`: For birthday detection
- `is_active`: Soft delete flag

**RecognitionLog**
- `employee_id`: Reference to Employee
- `employee_name`: Denormalized (fast queries)
- `department`: Denormalized
- `is_birthday`: Boolean flag for special handling
- `created_date`: Auto-timestamp (arrival time)

**SmartGreeting**
- `employee_id`: Reference to Employee
- `greeting_text`: AI-generated or custom message
- `greeting_type`: welcome | long_time_no_see | frequent_visitor | morning | afternoon | evening
- `generated_date`: Date created
- `valid_until`: Expiry timestamp (next day midnight)

**CompanySettings**
- `company_name`: Display name on kiosk
- `logo_url`: Brand logo
- `brand_color`: Primary hex color
- `language`: en | uz | ru
- `debug_mode`: Show face recognition overlay
- `idle_screen_enabled`: Enable screensaver
- `idle_timeout_minutes`: Inactivity timeout
- `telegram_chat_id`: Admin's Telegram ID
- `ai_chat_enabled`: Toggle AI assistant

**Video**
- `title`: Video name
- `video_url`: Playback URL
- `order`: Playlist position
- `is_active`: Include in rotation
- `duration_seconds`: For analytics

**Announcement**
- `title`: Headline
- `body`: Full text
- `is_active`: Currently displayed
- `expires_at`: Optional auto-hide
- `priority`: low | normal | urgent (visual styling)

**Meeting**
- `title`: Meeting name
- `employee_id`: Employee attending
- `start_time`: Meeting start (ISO datetime)
- `end_time`: Meeting end (ISO datetime)
- `location`: Room/location

**HolidayDate**
- `date`: Holiday date (YYYY-MM-DD)
- `name`: Holiday name (e.g., "Independence Day")
- `is_custom`: User-created vs. system-defined

---

## Backend Functions

All functions are serverless Deno scripts deployed on Base44.

### `generateSmartGreetings`
- **Trigger:** Daily at 00:00 UTC (scheduled automation)
- **Purpose:** Generate daily greetings for all active employees
- **Logic:** Analyzes visit patterns, birthdays, holidays; calls Gemini Flash LLM
- **Output:** Creates SmartGreeting records; cleans up expired entries

### `dailyBirthdayCheck`
- **Trigger:** Daily at 08:00 UTC (scheduled automation)
- **Purpose:** Send daily birthday + arrival summary to Telegram
- **Logic:** Queries RecognitionLog for today; formats message
- **Output:** Telegram alert via `sendTelegramAlert`

### `handleRecognitionAlert`
- **Trigger:** On face recognition (from FaceScanner component)
- **Purpose:** Process arrival, create logs, send Telegram notification
- **Logic:** Creates RecognitionLog; fetches SmartGreeting; sends alert
- **Output:** RecognitionLog entry + Telegram notification

### `sendTelegramAlert`
- **Trigger:** Called by other functions
- **Purpose:** Deliver messages to Telegram via Bot API
- **Logic:** Formats message; calls Telegram endpoint
- **Output:** Telegram message to admin's chat

---

## Security & Privacy

**Data Protection:**
- Role-based access control (RBAC): Admin-only endpoints for employee management
- Recognition logs visible to admins only
- Face descriptors stored server-side (not client-side)
- Employee photos are public (kiosk display)

**Camera & Privacy:**
- No video recording (only real-time face detection)
- Face frames discarded after descriptor extraction
- GDPR-compliant (no personal data logged beyond name/timestamp)

**API Security:**
- All backend functions authenticated via Base44 auth
- Telegram alerts verified via token-based requests
- Secrets (TELEGRAM_BOT_TOKEN) stored in Base44 environment variables

---

## Performance Considerations

**Recognition Latency:**
- Face detection: ~100–200ms per frame (GPU-accelerated on supported devices)
- Descriptor comparison: <1ms (128-point vector math)
- End-to-end: ~300ms from detection to overlay render

**Scalability:**
- Single camera per kiosk (no multi-camera support yet)
- Supports 500+ employees without performance degradation
- SmartGreeting caching reduces daily LLM calls to 1 per employee

**Resource Usage:**
- CPU: ~20–30% (face detection)
- Memory: ~150–200MB (model + frame buffers)
- Network: <100KB/request (logs + greetings)
- Optimal on modern desktops/laptops; avoid low-end Chromebooks

---

## Troubleshooting

**Face not detected:**
- Ensure face is fully visible, well-lit, 1–2m from camera
- Check debug mode in settings to see detection overlay
- Confirm employee photo is high-quality

**Greeting overlay doesn't appear:**
- Verify employee is added and `is_active = true`
- Check SmartGreeting table for today's entries
- Ensure camera feed is recognized (check console logs)

**Telegram alerts not received:**
- Confirm Telegram chat ID is set in CompanySettings
- Verify TELEGRAM_BOT_TOKEN secret is configured
- Test with `sendTelegramAlert` function manually

**Performance lags:**
- Disable debug mode (reduces rendering overhead)
- Close other browser tabs
- Restart the application

---

## Future Roadmap

- [ ] Multi-angle face enrollment (front + side profiles)
- [ ] Emotion detection (mood-based greeting customization)
- [ ] Exit detection & dwell time analytics
- [ ] Mobile admin app (React Native)
- [ ] Integration with BambooHR / ADP for auto-synced employee data
- [ ] Slack/Teams status auto-update ("In Office")
- [ ] Multi-location support with centralized dashboard
- [ ] Custom greeting templates with variable interpolation

---

## Support & Contributing

**Questions?**
- Check the technical documentation (`ARCHITECTURE.md`)
- Review Base44 docs: [base44.com/docs](https://base44.com/docs)
- Open an issue on GitHub

**Contributing:**
- Fork the repository
- Create a feature branch (`git checkout -b feature/amazing-feature`)
- Commit your changes (`git commit -m 'Add amazing feature'`)
- Push to the branch (`git push origin feature/amazing-feature`)
- Open a Pull Request

---

## License

This project is proprietary. All rights reserved © 2026 FaceGreet.uz

---

## Contact

**Developer:** Mirjalol Shavkatov  
**Email:** mirjalol0331@gmail.com  
**Location:** Tashkent, Uzbekistan
