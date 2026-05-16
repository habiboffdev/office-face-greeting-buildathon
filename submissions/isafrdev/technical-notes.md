# Technical Notes - VisionGate AI

## Architecture
The project follows a modular React architecture with a focus on real-time interactions. It uses a custom `RecognitionEngine` component that wraps `face-api.js` for local inference.

## Face Detection & Recognition
- **Engine**: `face-api.js` using the TinyFaceDetector for performance.
- **Descriptors**: 128-dimensional face descriptors are generated and compared using Euclidean distance.
- **Local Storage**: For speed, identified face descriptors are cached locally in IndexedDB after being fetched from Supabase.

## Database & Storage
- **Supabase**: Used as the primary source of truth for employee data, attendance logs, and media playlists.
- **Real-time**: Leverages Supabase Realtime to sync settings and playlist changes instantly to the Kiosk.

## Overlay Logic
The `GreetingOverlay` component uses `framer-motion` for smooth transitions. It intelligently selects greeting text based on:
1. Time of day (Morning/Day/Evening).
2. Special events (Birthdays).
3. Last interaction time (Hourly check-ins).

## Future Improvements
- **Offline Mode**: Full support for offline recognition when the internet is unavailable.
- **Advanced Emotion Analysis**: Tailoring greetings even more closely to detected emotional states.
- **Performance**: Shifting face recognition to a Web Worker to keep the UI thread completely free.
