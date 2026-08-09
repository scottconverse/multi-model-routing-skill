# SPDX-License-Identifier: MIT
"""Tests for install.py — install, uninstall, and the payload drift guard.

Every case here exists because of a real defect. Run:
    python3 tests/test_install.py
"""
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.py"
SKILL = "multi-model-routing"


def force_rmtree(p):
    """Remove a tree even when git has marked objects read-only (Windows).

    Clears the read-only bits up front rather than using rmtree's error hook:
    the hook is spelled `onerror` before Python 3.12 and `onexc` after, and CI
    runs 3.11 while this machine runs 3.13. Walking first works on both.
    """
    if not p.exists():
        return
    for root, dirs, files in os.walk(p):
        for name in dirs + files:
            try:
                os.chmod(os.path.join(root, name), stat.S_IWRITE)
            except OSError:
                pass
    shutil.rmtree(p, ignore_errors=True)


def run(*args, cwd=None):
    return subprocess.run([sys.executable, str(INSTALL), *args],
                          capture_output=True, text=True, timeout=180, cwd=cwd)


def have_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=30)
        return True
    except Exception:
        return False


results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  — {detail}" if detail and not cond else ""))


# ── 1.1 uninstall must never destroy a git checkout ──────────────────────────
# The documented Claude Code install IS the git working checkout: it has a
# SKILL.md, so the SKILL.md guard passes and rmtree takes .git with it.
# On POSIX that silently destroys unpushed history; on Windows rmtree dies on
# git's read-only objects and leaves a half-deleted tree plus a traceback.
with tempfile.TemporaryDirectory() as td:
    t = pathlib.Path(td)
    run("--project", str(t))
    d = t / ".claude" / "skills" / SKILL
    if have_git():
        subprocess.run(["git", "init", "-q"], cwd=d, capture_output=True, timeout=60)
        subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True, timeout=60)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "unpushed"], cwd=d, capture_output=True, timeout=60)
        r = run("--project", str(t), "--uninstall")
        check("uninstall refuses a git checkout (dir survives)", d.is_dir())
        check("uninstall refuses a git checkout (.git survives)", (d / ".git").is_dir())
        check("uninstall on a checkout does not traceback", "Traceback" not in (r.stdout + r.stderr))
        check("uninstall on a checkout explains itself",
              "git" in (r.stdout + r.stderr).lower() and r.returncode == 0,
              f"rc={r.returncode}")
        force_rmtree(d)
    else:
        print("  SKIP git-checkout case (no git)")

# ── 1.2 a preserved-notes backup must never be overwritten ───────────────────
# install -> uninstall -> install -> uninstall used to back the freshly
# templated notes over the backup holding every accumulated machine fact.
with tempfile.TemporaryDirectory() as td:
    t = pathlib.Path(td)
    skills = t / ".claude" / "skills"
    d = skills / SKILL

    run("--project", str(t))
    (d / "references" / "local-notes.md").write_text(
        "REAL ACCUMULATED MACHINE FACTS\n", encoding="utf-8")
    run("--project", str(t), "--uninstall")

    run("--project", str(t))          # reinstall -> fresh template notes
    run("--project", str(t), "--uninstall")

    backups = sorted(p for p in skills.glob(f"{SKILL}.local-notes*.md"))
    check("two uninstall cycles leave two backups", len(backups) >= 2,
          f"found {len(backups)}: {[b.name for b in backups]}")
    kept = any("REAL ACCUMULATED" in b.read_text(encoding="utf-8", errors="replace")
               for b in backups)
    check("the real accumulated notes survive a second cycle", kept)

# ── 1.3 an installed copy must be able to uninstall itself ───────────────────
# install.py was absent from PAYLOAD, so an install had no uninstaller in it.
with tempfile.TemporaryDirectory() as td:
    t = pathlib.Path(td)
    run("--project", str(t))
    d = t / ".claude" / "skills" / SKILL
    check("install.py ships with the install", (d / "install.py").is_file())
    if (d / "install.py").is_file():
        # run the INSTALLED copy, with no clone anywhere in sight
        r = subprocess.run([sys.executable, str(d / "install.py"),
                            "--project", str(t), "--uninstall"],
                           capture_output=True, text=True, timeout=180)
        check("an installed copy can uninstall itself", not d.exists(),
              (r.stdout + r.stderr)[-200:])

# ── payload drift guard ──────────────────────────────────────────────────────
# PAYLOAD is hand-maintained, so a new reference doc could silently fail to
# ship. That is the same drift that left the 0.3.0 and 0.3.1 docs behind the
# work, one layer down. Every tracked file must be shipped or explicitly
# excluded — "forgotten" is no longer a state this repo can be in.
sys.path.insert(0, str(ROOT))
import install as installer  # noqa: E402

SHIPPED = set(installer.PAYLOAD)
EXCLUDED = set(getattr(installer, "NOT_SHIPPED", []))

tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, timeout=60).stdout.split()
candidates = [f for f in tracked
              if f.endswith((".md", ".sh", ".py"))
              and not f.startswith((".github/", "docs/notes"))]
unaccounted = sorted(set(candidates) - SHIPPED - EXCLUDED)
check("every tracked file is shipped or explicitly excluded", not unaccounted,
      f"add to PAYLOAD or NOT_SHIPPED: {unaccounted}")

overlap = SHIPPED & EXCLUDED
check("no file is both shipped and excluded", not overlap, f"{sorted(overlap)}")

missing = sorted(rel for rel in installer.PAYLOAD if not (ROOT / rel).is_file())
check("every PAYLOAD entry exists in the repo", not missing, f"{missing}")

# ── install() must prune files left by an older version ──────────────────────
with tempfile.TemporaryDirectory() as td:
    t = pathlib.Path(td)
    run("--project", str(t))
    d = t / ".claude" / "skills" / SKILL
    stale = d / "references" / "renamed-away.md"
    stale.write_text("left over from an older version\n", encoding="utf-8")
    notes = d / "references" / "local-notes.md"
    notes.write_text("MY MACHINE FACTS\n", encoding="utf-8")
    run("--project", str(t))                      # reinstall over the top
    check("reinstalling prunes a stale file", not stale.exists())
    check("pruning never removes local-notes.md", notes.is_file())
    check("pruning preserves local-notes.md content",
          notes.is_file() and "MY MACHINE FACTS" in notes.read_text(encoding="utf-8"))

print()
bad = [n for n, ok, _ in results if not ok]
if bad:
    print(f"FAIL: {len(bad)}/{len(results)} — {'; '.join(bad)}")
    sys.exit(1)
print(f"PASS: {len(results)} install.py checks")
