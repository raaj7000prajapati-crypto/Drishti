# Local API load-test report

## Result

The measured run completed on **2026-10-31** against an isolated SQLite
database containing **5,000 synthetic complaints**. Locust ramped to 100 users
at 20 users/second and ran for 60 seconds. The workload used an 80/20 mix of
dashboard aggregates and 50-row complaint-list requests.

| Metric | Measured result |
|---|---:|
| Concurrent users | 100 |
| Run duration | 60 seconds |
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

These are real results from the Locust CSV output, not projected or simulated
values. The average throughput is computed from the observed request count and
configured run duration; the second rate is Locust's reported Requests/s value
at shutdown. Percentiles are approximate as reported by Locust.

## Test environment and limits

- Windows 11 build 26300, Python 3.14.7, Locust 2.47.0
- Intel Core Ultra 5 225H, 14 logical processors, 15.5 GB RAM
- One local Uvicorn process, SQLite database, localhost HTTP; no TLS or network
  latency was included
- The 10-second dashboard cache was enabled. It is process-local, and the
  100 virtual users shared one temporary administrator token and repeated the
  same dashboard filters, so these results do not model cache behavior across
  many distinct user identities.
- All complaint descriptions and accounts were generated synthetic load-test
  data. The seeded administrator is test-only.

This is a local smoke-test baseline, **not** a production capacity estimate.
It does not exercise PostgreSQL, multiple API workers, distributed cache
coherence, sustained data growth, realistic client networks, or a full
browser-rendering workload. In particular, complaint-list latency was higher
than dashboard latency at p95 and should be measured again against the
production database and deployment topology.

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
administrator to obtain a short-lived access token, and run:

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
