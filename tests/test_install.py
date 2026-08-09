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

# ── install must never prune inside a VCS working copy ───────────────────────
# The documented Claude Code install IS the git checkout. Pruning there deleted
# every tracked file not in PAYLOAD -- .gitignore, .gitattributes,
# .github/workflows/, docs/index.html, CHANGELOG -- because the VCS skip only
# covered paths INSIDE .git/. Pruning exists to clean stale files out of a
# copied install; in a checkout git already does that job.
if have_git():
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td)
        run("--project", str(t))
        d = t / ".claude" / "skills" / SKILL
        subprocess.run(["git", "init", "-q"], cwd=d, capture_output=True, timeout=60)
        # files a real checkout has that PAYLOAD does not list
        (d / ".gitignore").write_text("references/local-notes.md\n", encoding="utf-8")
        (d / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
        (d / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
        (d / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        (d / ".github" / "workflows" / "test.yml").write_text("name: test\n", encoding="utf-8")

        r = run("--project", str(t))          # reinstall over the checkout

        check("install into a checkout keeps .gitignore", (d / ".gitignore").is_file())
        check("install into a checkout keeps .gitattributes", (d / ".gitattributes").is_file())
        check("install into a checkout keeps CHANGELOG.md", (d / "CHANGELOG.md").is_file())
        check("install into a checkout keeps .github/workflows",
              (d / ".github" / "workflows" / "test.yml").is_file())
        check("install into a checkout says it skipped pruning",
              "prun" in (r.stdout + r.stderr).lower())
        force_rmtree(d)

# ── printed output must survive a legacy console codepage ────────────────────
# cp437 is the historic cmd.exe default and has no em dash. An em dash in a
# print() raised UnicodeEncodeError mid-install, after files had been copied,
# leaving a partial install. cp1252 hides it: that codepage HAS the character.
#
# SCOPE, deliberately: the rule is "printed strings are ASCII", NOT "files are
# ASCII". Comments never reach a stream, so they are exempt and are skipped
# below. Seven non-ASCII characters remain in comments across install.py and
# call_local.sh and that is fine. Do not "finish the job" on them — it hardens
# nothing, and widening this check would make it fail for a reason that cannot
# hurt anyone.
src = (ROOT / "install.py").read_text(encoding="utf-8")
printed = []
for line in src.splitlines():
    s = line.strip()
    if s.startswith("#"):
        continue                      # comments are never printed
    if "print(" in s or "actions.append(" in s or "sys.exit(" in s or 'return dest, [' in s:
        printed.append(line)
bad = []
for line in printed:
    try:
        line.encode("cp437")
    except UnicodeEncodeError as e:
        bad.append(f"{e.object[e.start:e.end]!r} in: {line.strip()[:60]}")
check("printed strings are cp437-safe", not bad, "; ".join(bad[:3]))

# ── payload drift guard ──────────────────────────────────────────────────────
# PAYLOAD is hand-maintained, so a new reference doc could silently fail to
# ship. That is the same drift that left the 0.3.0 and 0.3.1 docs behind the
# work, one layer down. Every tracked file must be shipped or explicitly
# excluded — "forgotten" is no longer a state this repo can be in.
sys.path.insert(0, str(ROOT))
import install as installer  # noqa: E402

SHIPPED = set(installer.PAYLOAD)
EXCLUDED = set(getattr(installer, "NOT_SHIPPED", []))

# No extension filter: the guard's set must be the SAME set prune operates on,
# or the two drift apart and the guard stops meaning anything. Every tracked
# file is named in one list or the other -- .gitignore, .gitattributes,
# docs/index.html, docs/.nojekyll and the workflow included.
tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, timeout=60).stdout.split()
# Untracked-but-not-ignored files count too. git ls-files sees only what is
# already staged or committed, so a brand-new reference doc stayed invisible to
# this guard until someone ran `git add` -- CI caught it, but only a step later
# than the author needed. --others --exclude-standard closes that gap while
# still respecting .gitignore, so local-notes.md and __pycache__ stay exempt.
untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                           cwd=ROOT, capture_output=True, text=True,
                           timeout=60).stdout.split()
unaccounted = sorted((set(tracked) | set(untracked)) - SHIPPED - EXCLUDED)
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
