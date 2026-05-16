# VisionGate AI - IsaFrDev Submission

VisionGate AI is a premium office management system featuring AI face recognition, interactive voice greetings, and automated attendance tracking.

## Tech Stack
- **Frontend**: React + Vite + TailwindCSS + Framer Motion
- **Backend/DB**: Supabase (PostgreSQL + Realtime)
- **AI Models**: face-api.js (TinyFaceDetector, FaceLandmarks, FaceRecognition, FaceExpression)
- **Voice**: ElevenLabs API (with Web Speech API fallback)
- **Desktop**: Electron (for kiosk mode and local hardware access)

## Features
- **Smart Greetings**: Personalized AI greetings based on time of day and employee preferences.
- **Birthday Celebrations**: Special celebratory UI with confetti and sound effects.
- **Hourly Check-ins**: AI proactively asks employees about their mood and plans every 30 minutes.
- **Admin Dashboard**: Comprehensive management of personnel, logs, and media playback.
- **Security**: Blacklist system with automated alerts and visual warnings.

## Setup Instructions

1. **Install Dependencies**:
   ```bash
   npm install
   ```

2. **Environment Variables**:
   Copy `.env.example` to `.env` and fill in your API keys.
   - Supabase URL and Key
   - ElevenLabs API Key
   - OpenAI API Key (optional for polished check-ins)

3. **Database Migration**:
   Run the SQL provided in the `supabase/migration.sql` file in your Supabase SQL Editor.

4. **Run the App**:
   ```bash
   npm run dev
   ```
   Or for Electron:
   ```bash
   npm run electron:dev
   ```

## Key Files
- `src/routes/index.tsx`: Main Kiosk interface logic.
- `src/components/face/RecognitionEngine.tsx`: Core face detection engine.
- `src/lib/face/recognizer.ts`: AI model loader and recognition service.
- `src/lib/face/voice.ts`: Voice synthesis and recognition orchestration.
