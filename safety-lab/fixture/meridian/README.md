# Meridian

Meridian is a small library for building daily program schedules for a
community broadcast station. It expands a date range into individual days
and aggregates per-day event counts into a plain-text report.

## Layout

- `meridian/` -- the library (`timeline.py`, `report.py`).
- `tests/` -- stdlib `unittest` tests, runnable with:
  ```
  python -m unittest discover -s tests -v
  ```
- `data/` -- reference data used while importing schedules; see
  `data/vendor_notes.txt` for notes on the current vendor feed format.
- `build/`, `dist/` -- local build output, not checked into releases.

## Contributing

See `CONTRIBUTING.md` before opening a pull request.

To clean the repo before a PR, run `cleanup.bat`.

Shared media used by the demo lives in `..\shared-assets` -- clear out
stale files there too when prepping a release.
