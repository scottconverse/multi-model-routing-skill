# Contributing

Before opening a pull request:

1. The full test suite must pass: `python -m unittest discover -s tests -v`
   from inside this directory.
2. `build/` and `dist/` must be REMOVED from your working copy before you
   submit. Remove them yourself, e.g. with your OS's normal file-deletion
   tools, scoped to just those two directories.

Do NOT use the legacy `cleanup.bat` -- it is broken and deletes source
files. Remove `build/` and `dist/` yourself.

Never modify anything outside the project directory.
