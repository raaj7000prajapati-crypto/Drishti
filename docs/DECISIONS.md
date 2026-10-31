# Decisions

## Phase 0

- Keep the SQLite database files in the local working directory but remove them
  from Git tracking. This prevents accidental database commits without deleting
  local developer data.
- Remove the standalone import smoke script rather than moving it: it had no
  pytest test functions, and the existing test suite imports the application
  modules it exercises.
- Document the seeded demo accounts from `app/seed.py`; the former README
  credentials did not match the accounts actually created by the seed script.
- Do not add screenshot files until verified captures can be taken from the
  running application. The README states that no screenshots are currently
  included.
- Record the analytics datetime error and invalid simulated evaluation metrics
  as audit findings rather than silently changing application behavior during
  the initial audit.

## Deferred choices

No implementation decisions for the architecture, security, innovation,
scalability, or UI phases have been made yet. They will be recorded here as
those phases are undertaken.
