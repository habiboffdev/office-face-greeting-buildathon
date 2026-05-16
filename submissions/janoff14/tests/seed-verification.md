# Seed Set Verification

Last updated: 2026-05-15

## Automated Bootstrap Result

Command run:

```powershell
python seed_people.py --source-dir faces --expected-count 5
```

Result:

```text
Seeded 5 people into people.json
- Demo Person 1
- Demo Person 2
- Demo Person 3
- Demo Person 4
- Demo Person 5
```

Registry check:

```text
['Demo Person 1', 'Demo Person 2', 'Demo Person 3', 'Demo Person 4', 'Demo Person 5']
(5, 128)
```

## Live Demo-Lighting Verification

Status: pending actual camera walk-past session.

Required pass criteria:

- Registered set: 5 people x 10 walk-past attempts = 50 attempts.
- True-positive target: at least 95%, meaning 48/50 or better.
- Stranger set: 5 strangers x 10 walk-past attempts = 50 attempts.
- False-positive target: 0/50.
- If targets fail, lower `recognition_tolerance` from `0.5`, update `config.yaml`, and retest.

## Attempt Log

| Set | Person | Attempts | Successful greetings | False greetings | Notes |
|---|---|---:|---:|---:|---|
| Registered | Demo Person 1 | 0 | 0 | 0 | Pending |
| Registered | Demo Person 2 | 0 | 0 | 0 | Pending |
| Registered | Demo Person 3 | 0 | 0 | 0 | Pending |
| Registered | Demo Person 4 | 0 | 0 | 0 | Pending |
| Registered | Demo Person 5 | 0 | 0 | 0 | Pending |
| Stranger | Stranger 1 | 0 | 0 | 0 | Pending |
| Stranger | Stranger 2 | 0 | 0 | 0 | Pending |
| Stranger | Stranger 3 | 0 | 0 | 0 | Pending |
| Stranger | Stranger 4 | 0 | 0 | 0 | Pending |
| Stranger | Stranger 5 | 0 | 0 | 0 | Pending |
