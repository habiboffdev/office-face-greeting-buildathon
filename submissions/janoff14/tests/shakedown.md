# 60-minute stability shakedown log

Fill in during a real run on the demo machine. Story 4.4 acceptance.

## Run metadata

- **Date:**
- **Machine:** (model / OS build)
- **Camera:** (model / connection)
- **Resolution:** (display + camera)
- **Start time:**
- **End time:**
- **Duration:** (target ≥ 60 min)

## Memory (NFR8 — growth ≤ 100 MB combined)

Capture with:

```powershell
Get-Process python | Select-Object Id, ProcessName, @{Name="WS_MB";Expression={[math]::Round($_.WorkingSet64 / 1MB, 1)}}
```

| Process | Start WS (MB) | End WS (MB) | Delta (MB) |
| ------- | ------------- | ----------- | ---------- |
| supervisor (player) |  |  |  |
| recognition worker  |  |  |  |
| bot subprocess      |  |  |  |
| **Total**           |  |  |  |

Pass criterion: total delta ≤ 100 MB.

## Walk-pasts (NFR9 / NFR10)

- Registered walk-pasts attempted:
- Greetings observed:
- TPR for the session: (greetings / attempts)
- False positives observed (stranger triggered greeting): (target: 0)

## Admin actions during run

- [ ] `/add_person` — name added, greeted on next walk-past (FR18, hot reload ≤ 5 s).
- [ ] `/add_video` — file appeared in playlist by end of next iteration (FR21, NFR5).

## Playback inspection (NFR2, NFR11)

Three random 30-second windows watched during the run. Any stutter, skip, or freeze?

| Window | Approx wall time | Observation |
| ------ | ---------------- | ----------- |
| 1      |                  |             |
| 2      |                  |             |
| 3      |                  |             |

## Frame-persistence spot audit (NFR14)

After the run, list any non-log image artifacts in the repo:

```powershell
Get-ChildItem -Recurse -Include *.jpg,*.png logs, videos | Where-Object { $_.Name -notmatch '\.tmp' }
```

Expected output: nothing under `logs/`; only the legitimate playlist videos under `videos/`.

Result:

## Component restarts within FR30 contract (acceptable)

| Time | Component | Reason / observation |
| ---- | --------- | -------------------- |
|      |           |                      |

(Empty table is the happy path.)

## Anomalies / notes

Anything weird that didn't fit a box above:

## Verdict

- [ ] PASS — meets all AC.
- [ ] FAIL — see anomalies; investigate before AR17 cutoff (hour 20).
