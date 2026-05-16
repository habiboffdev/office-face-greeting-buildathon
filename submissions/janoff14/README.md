# FaceTag

Office entrance kiosk that loops promo videos fullscreen and greets registered people by name using on-device face recognition. Admins manage people and playlist content from Telegram. All biometric data stays on the demo machine.

## Quick demo run

From this repository on the demo laptop:

```powershell
.\.venv-smoke-dlib-corrected\Scripts\python.exe run.py
```

This starts the full local system: fullscreen muted promo player, face recognition worker, Telegram bot, and the local web admin at `http://127.0.0.1:8000/`.

Press **Esc** in the fullscreen player to stop the whole launcher cleanly. Use **Ctrl+C** in the terminal as the fallback stop.

Current demo web login:

```text
username: admin123
password: admin123
```

Useful commands:

```powershell
# Show recent component logs
.\.venv-smoke-dlib-corrected\Scripts\python.exe run.py --tail-logs

# Run the full regression suite
.\.venv-smoke-dlib-corrected\Scripts\python.exe -m pytest -q

# Run only the web admin
.\.venv-smoke-dlib-corrected\Scripts\python.exe webapp.py
```

## Setup

1. **Python 3.11+** with a fresh virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   ```

2. **Install dlib (the dominant Windows risk):**

   ```powershell
   pip install dlib-bin face_recognition opencv-python
   ```

   This uses the prebuilt `dlib-bin` wheel — no source compilation, no Visual Studio toolchain. If `dlib-bin` is unavailable for your Python version, see `tests/smoke_dlib.py` for the verification script.

3. **Install the rest of the pinned dependencies:**

   ```powershell
   pip install -r requirements.txt
   ```

4. **Configure local-only values:**

   ```powershell
   Copy-Item config.yaml.example config.yaml
   ```

   Edit `config.yaml`:
   - `telegram_token` — your Telegram bot token (from @BotFather).
   - `admin_chat_ids` — list of Telegram chat IDs allowed to run admin commands.
   - `camera_device_index` — usually `0`.
   - `web_allowed_emails` / `web_password` - optional local web admin login.
   - `playlist_schedule` - optional time-of-day video folders.

   `config.yaml` is gitignored; never commit it.

5. **Drop at least one video into `videos/`:**

   ```powershell
   Copy-Item tests\assets\seed-promo.mp4 videos\
   ```

6. **Run:**

   ```powershell
   python run.py
   ```

   Press **Esc** to quit. The supervisor starts the player, recognition worker, Telegram bot, and web admin together; logs land in `logs/<component>.log`.

   Web admin opens at `http://127.0.0.1:8000/` when the supervisor is running.

   To run only the web admin:

   ```powershell
   python webapp.py
   ```

## Architecture

Four coordinated OS processes managed by `run.py` (supervisor):

```
                                  +-----------------------------+
                                  |        run.py (supervisor)  |
                                  |   restarts on FR30 contract |
                                  +--------------+--------------+
                                                 |
       +-----------------------------+-----------+------------+-----------------------------+
       |                             |                        |                             |
       v                             v                        v                             v
+--------------+              +---------------+         +--------------+              logs/*.log
|  Player      |  greeting    |  Recognition  |         |  Telegram    |
|  (Qt proc)   |<-------------|  worker       |         |  bot         |
|              |  mp.Queue    |  (mp.Process) |         |  (subprocess)|
| - fullscreen |              | - cv2 capture |         |              |
| - playlist   |              | - HOG detect  |         | - admin      |
|   rescan @   |              | - embed+match |         |   allowlist  |
|   end-of-vid |              | - cooldown    |         | - /add_*     |
| - greeting   |              | - watchdog -> |         | - /list_*    |
|   overlay    |              |   hot reload  |         | - /delete_*  |
+--------------+              +-------+-------+         +------+-------+
       ^                              |                        |
       |                              | reads                  | writes (atomic)
       |                              v                        v
       |                       +-------------+         +------------------+
       |                       | people.json |<--------|  shared writers  |
       +-----------------------+ + faces/    |         |  (recognition.   |
            scans videos/      |             |         |   writer +       |
            at end of each     +-------------+         |   player.video_  |
            video iteration                            |   writer)        |
                                                       +------------------+
                                                              ^
                                                              | also used by
                                                       +------+-------+
                                                       |  CLI:        |
                                                       |  add_person  |
                                                       |  add_video   |
                                                       +--------------+
```

Key contracts:

- **IPC:** worker → player via `multiprocessing.Queue` (greeting events `{name, timestamp}`).
- **Persistence:** player, worker, bot, and webapp are supervisor-managed. A crashed player restarts; pressing Esc exits cleanly and stops the launcher.
- **Atomic writes:** `recognition/writer.py` and `player/video_writer.py` both write to a `.tmp` location, then `os.replace()` to the final path. Watchers never see partial writes.
- **Hot reload:** `recognition/hot_reload.py` watches `people.json` via `watchdog`; the worker swaps its in-memory `Registry` within 5 s of any admin write — no restart needed (FR18, FR19, NFR4).
- **Playlist rescan:** the player rescans `videos/` at the end of each video iteration (FR11, NFR5). New videos appear within one loop; deleted ones drop out.
- **Scheduled playlists:** if `playlist_schedule` is configured, the player chooses the active video folder at startup and again between videos. Windows that cross midnight are supported.

## Selection strategy

When multiple registered people are visible in the same frame, **largest bounding-box area wins**. This proxies "closest to the camera" — the person actually arriving at the entrance gets the greeting, not the one waving from the background. Implemented in `recognition/recognize.py:recognize_dual` (FR4).

If the *largest* face is unknown, the function returns `None` rather than falling through to a smaller registered face. This honors the product rule that a known face in the background must not steal the greeting from an unknown person at the desk.

## Threading model

Recognition runs in its own OS process (`multiprocessing.Process`), not a thread. Two reasons:

1. **GIL avoidance.** dlib's face detection and embedding are CPU-bound C++ calls. A thread would still serialize behind Python's GIL between calls; a process gets a dedicated core.
2. **Qt event-loop isolation.** Qt's `QMediaPlayer` is sensitive to scheduling jitter — any long-running CPU work on the main thread shows up as video stutter. A separate process means the player loop only ever does cheap things (drain a queue, fade an overlay, advance the playlist).

The Telegram bot runs in a subprocess (not a thread) for symmetry and so its blocking `run_polling` loop is supervisor-restartable without touching the player.

## Benchmark results

Run `benchmark.py` on the demo machine to produce reproducible accuracy + latency numbers:

```powershell
python benchmark.py
```

Latest run (paste verbatim output here after Story 4.4 shakedown):

```
TODO: paste benchmark.py output. Expected shape:

Recognition pipeline latency p50: 0.82 s, p95: 1.64 s
True-positive rate: 96% (48/50 attempts)
False-positive rate: 0.0% (0/50 attempts)
Tolerance: 0.50
Seed set: 5 people x 10 attempts; control set: 5 strangers x 10 attempts
Capacity (200 registered): p50 0.91 s, p95 1.34 s
```

Targets (NFRs):
- Recognition pipeline latency: p50 ≤ 1.0 s, p95 ≤ 2.0 s (NFR1).
- True-positive rate: ≥ 95% under demo lighting (NFR10).
- False-positive rate: 0% against the stranger control set (NFR9).
- 200-person capacity: still within NFR1 latency targets (NFR20).

The benchmark prepends warning lines to stderr if any target is missed but always exits 0 — judges can re-run and see the same numbers without the script failing on a marginal result.

## CLI fallback

For offline operation (no Wi-Fi at the venue) or videos larger than the Telegram 20 MB bot limit, two CLI scripts wrap the same atomic writers the bot uses:

```powershell
# Add a registered person without Telegram
python add_person.py "Judge Karimov" path\to\photo.jpg

# Add a person directly from the camera
python capture_person.py "Judge Karimov"

# Add a video of any size without Telegram
python add_video.py path\to\big-promo.mp4
```

Both work fully offline. The recognition worker's `watchdog` picks up the new entry within 5 s, and the player picks up new videos at the end of the next iteration — same hot-reload path as the bot's `/add_person` and `/add_video`.

Exit codes: `0` success, `1` usage error, `2` operational error (missing file, no face, unsupported format).

## Admin and bonus features

- Greeting overlay stays on screen for the configured `display_duration_seconds` value; the default is 5 seconds.
- Per-person greeting metadata supports `language` (`en`, `uz`, `ru`), `birthday` (`MM-DD`), custom message, and rotating flavor lines. The web UI can edit these fields.
- Users can request self-registration in Telegram with `/join` or `/register`. They send their name and photo; admins receive approval/rejection buttons. Approval uses the same `recognition.writer.add_person` path as the bot, CLI, and web UI.
- Recognition notifications are sent to admin chats from `logs/recognitions.jsonl`; `/quiet` and `/unquiet` toggle them for the current bot process.
- The web UI can add people by uploaded image or by capturing one still frame from `camera_device_index`. If the recognition worker already owns the camera, stop the full system or use a separate camera before using capture.
- Web auth supports a demo username/password or an email allowlist. For the current demo config, use `admin123` / `admin123`; leave auth fields blank for no login on localhost.
- Slack notifications are intentionally not implemented.

Example scheduled playlist:

```yaml
playlist_schedule:
  - start: "08:00"
    end: "12:00"
    folder: "videos/morning"
  - start: "12:00"
    end: "18:00"
    folder: "videos/day"
  - start: "18:00"
    end: "08:00"
    folder: "videos/night"
```

## Repository layout

```
run.py              supervisor entry point
bot.py              Telegram bot (admin commands)
supervisor.py       process lifecycle + log routing
add_person.py       offline CLI to add a person
capture_person.py   offline CLI to add from the camera
add_video.py        offline CLI to add a video
benchmark.py        accuracy + latency self-test
seed_people.py      one-shot script for the 5-person seed set
webapp.py           local web admin UI

player/             fullscreen Qt video player
  main.py           Player class + run_player
  playlist.py       pure helpers: scan, advance, rescan
  overlay.py        greeting fade overlay
  video_writer.py   shared atomic video writer
  greeting_queue.py worker→player queue drainer

recognition/        face detection + matching
  recognize.py      single-frame recognize_dual
  camera_capture.py still-frame capture helper
  registry.py       people.json reader
  writer.py         shared atomic people writer
  worker.py         the recognition process loop
  hot_reload.py     watchdog-based registry reloader

tests/              unit + integration tests (286 currently)
  shakedown.md      60-min stability run log
  smoke_dlib.py     dlib install verification

config.yaml.example template config (committed)
config.yaml         your local config (gitignored)
people.json         registered people (created at first add)
faces/              source photos for re-embedding (gitignored)
videos/             playlist (gitignored except seed-promo.mp4)
logs/               per-component logs (gitignored)
```
