# FaceTag Technical Notes

## Architecture

FaceTag runs as a local kiosk system supervised by `run.py`. The supervisor starts and monitors four processes:

- PyQt fullscreen promo player
- OpenCV/face_recognition worker
- Telegram bot
- Flask web admin

The player stays focused on video playback and overlay rendering. Face recognition runs in a separate process so camera and embedding work cannot block the Qt event loop. The worker sends greeting events to the player through a `multiprocessing.Queue`; if the player restarts, the newest greeting wins and stale queue entries are discarded.

## Face Detection And Recognition

The worker captures frames from the configured local camera. On Windows the default backend is DirectShow (`camera_backend: dshow`) because it was more stable than MSMF during demo testing. Recognition uses `face_recognition`/dlib encodings and compares frames against locally stored embeddings.

When multiple faces are visible, the system chooses the largest face by bounding-box area. This acts as a practical "closest person" rule for an office entrance kiosk.

Unknown people do not trigger the overlay. The promo video keeps playing.

## Storage

The app stores data locally:

- `people.json` for names, embeddings, greeting metadata, and optional Telegram user IDs
- `faces/` for source face photos
- `videos/` for the promo playlist
- `logs/recognitions.jsonl` for recognition events

No face data is sent to a third-party service.

## Overlay Logic

The player loops local videos fullscreen and muted. Recognition events show a translucent greeting card over the video for 4-6 seconds. The overlay fades/scales in and fades out without pausing playback.

The overlay supports:

- time-of-day greetings
- Uzbek, English, and Russian greeting text
- birthdays
- custom per-person messages
- rotating flavor lines
- optional camera preview panel for demo visibility

## Admin UX

Admins can manage people and videos from:

- local Flask web admin at `http://127.0.0.1:8000/`
- Telegram admin commands and inline buttons
- CLI fallback scripts

Normal Telegram users can request registration. They submit their name and photo, then admins approve or reject with inline buttons. Approved users are added through the same local writer path as the web UI and CLI.

## Reliability

The supervisor restarts crashed player, worker, bot, and webapp processes. Pressing Esc in the player is treated as an intentional clean shutdown and stops the launcher. The recognition worker also exits if its parent launcher disappears, so it does not keep the camera locked after a hard failure.

The final regression suite contains 286 tests covering overlay crashes, supervisor restart policy, worker cooldown/backpressure, Telegram approval edge cases, camera backend selection, web CRUD, and player mute/watchdog behavior.

## Improvements With More Time

- Add a packaged Windows installer.
- Add an on-screen camera selection tool.
- Add a real benchmark result table from the final demo laptop.
- Add password rotation and persistent auth sessions for non-demo deployment.
- Add a more polished demo video and screenshots in the README.
