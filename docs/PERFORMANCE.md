# Local API load-test report

## Latest two-worker re-run

The measured run completed on **2026-10-31** against an isolated SQLite
database containing **5,000 synthetic complaints**. Locust ramped to 100 users
at 20 users/second and ran for 60 seconds against **two Uvicorn workers**. The
workload used an 80/20 mix of dashboard aggregates and 50-row complaint-list
requests.

| Metric | Measured result |
|---|---:|
| Concurrent users | 100 |
| Uvicorn workers | 2 |
| Run duration | 60 seconds |
| Total requests | 11,004 |
| Failed requests | 7 (0.06%) |
| Average throughput (11,004 requests / 60 seconds) | 183.40 requests/second |
| Locust-reported request rate at shutdown | 184.54 requests/second |
| Overall p50 response time | 6 ms |
| Overall p95 response time | 240 ms |
| Overall maximum observed response time | 16,165 ms |

| Endpoint | Requests | Failures | p50 | p95 |
|---|---:|---:|---:|---:|
| Dashboard aggregates | 8,805 | 4 | 5 ms | 240 ms |
| Complaint list (50) | 2,199 | 3 | 8 ms | 150 ms |

Locust reported seven `ConnectionAbortedError(10053)` failures. It exited with
status 1 because of those request failures; they are included above, not
discarded. Average throughput is computed from the observed request count and
configured run duration. Percentiles and the shutdown request rate are the
values reported by Locust.

No Redis server was available during this run, so both workers used the
development in-memory fallback. This measures the two-worker API/SQLite
workload, but **does not measure Redis-backed cross-worker cache hits or
lockout sharing**. Docker was unavailable in the environment, so Redis
Compose health and integration behavior were not exercised here.

## Original single-worker baseline

The earlier run used the same date, database size, 100-user ramp, 60-second
duration, and workload, but one Uvicorn process.

| Metric | Measured result |
|---|---:|
| Concurrent users | 100 |
| Uvicorn workers | 1 |
| Total requests | 12,940 |
| Failed requests | 0 (0%) |
| Average throughput (12,940 requests / 60 seconds) | 215.67 requests/second |
| Locust-reported request rate at shutdown | 253.51 requests/second |
| Overall p50 response time | 9 ms |
| Overall p95 response time | 130 ms |
| Overall maximum observed response time | 515 ms |

| Endpoint | Requests | p50 | p95 |
|---|---:|---:|---:|
| Dashboard aggregates | 10,320 | 8 ms | 82 ms |
| Complaint list (50) | 2,620 | 22 ms | 290 ms |

These are real results from the earlier Locust CSV output. The average
throughput is computed from the observed request count and configured run
duration; the second rate is Locust's reported Requests/s value at shutdown.
Percentiles are approximate as reported by Locust.

## Test environment and limits

- Windows 11 build 26300, Python 3.14.7, Locust 2.47.0
- Intel Core Ultra 5 225H, 14 logical processors, 15.5 GB RAM
- Local Uvicorn, SQLite database, localhost HTTP; no TLS or network
  latency was included
- The 10-second dashboard cache was enabled. In the two-worker run it was
  process-local because Redis was unavailable; in the original run it was
  process-local by design. The
  100 virtual users shared one temporary administrator token and repeated the
  same dashboard filters, so these results do not model cache behavior across
  many distinct user identities.
- All complaint descriptions and accounts were generated synthetic load-test
  data. The seeded administrator is test-only.

These are local smoke-test results, **not** a production capacity estimate.
They do not exercise PostgreSQL, Redis-backed shared state, sustained data
growth, realistic client networks, or a full browser-rendering workload. The
two-worker run observed connection-aborted failures and a 16-second maximum
response, so it warrants a repeat with Redis and the production database
before drawing capacity conclusions.

## Reproduction outline

Use an isolated SQLite database with `perf` in its filename. Do not point the
seeder at a development or production database.

```powershell
$env:DATABASE_URL = "sqlite:///C:/temp/drishti-perf-local.db"
$env:DRISHTI_PERF_TEST = "1"
alembic upgrade head
python scripts/performance/seed_5000.py
```

Start the API against that same database, log in with the seeder-created
administrator to obtain a short-lived access token, and start two workers:

```powershell
python -m uvicorn app.main:app --workers 2 --host 127.0.0.1 --port 8000
```

In another terminal, run:

```powershell
$env:LOAD_TEST_TOKEN = "<temporary access token>"
locust -f scripts/performance/locustfile.py --headless `
  -u 100 -r 20 --run-time 60s `
  --host http://127.0.0.1:8000 `
  --csv drishti-load --csv-full-history
```

Keep the token and generated database local; do not check them into source
control. The seeder refuses to run unless `DRISHTI_PERF_TEST=1`, the database
is SQLite, and the database filename contains `perf`.
