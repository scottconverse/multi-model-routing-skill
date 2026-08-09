# SPDX-License-Identifier: MIT
"""Tests for install.py — install, uninstall, and the payload drift guard.

Every case here exists because of a real defect. Run:
    python3 tests/test_install.py
"""
import os
import pathlib
import re
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
skipped = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    # ASCII only. The em dash that used to sit here is absent from cp437, the
    # historic cmd.exe codepage -- and it sat in the FAILURE branch, so the
    # harness raised UnicodeEncodeError on precisely the run that had bad news
    # to deliver, replacing the name of the broken check with a traceback about
    # character encoding. Same defect install.py was fixed for; it survived
    # here because the guard enforcing the rule read install.py BY NAME.
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  - {detail}" if detail and not cond else ""))


def skip(name, why):
    """Record a check that could not run, and say so.

    A skipped check must never be indistinguishable from a passing one. The
    payload drift guard silently vanished in installed copies and the suite
    still printed a clean PASS, one check shorter, with nothing to notice.
    """
    skipped.append(name)
    print(f"  SKIP {name} - {why}")


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
# below. Non-ASCII characters remain in comments across install.py and
# call_local.sh and that is fine. Do not "finish the job" on them - it hardens
# nothing, and widening this check would make it fail for a reason that cannot
# hurt anyone.
#
# EVERY shipped .py, never one by name. Reading only install.py was the bug:
# the test harness itself printed em dashes in its own failure branch for two
# releases, so a real failure on cmd.exe surfaced as UnicodeEncodeError instead
# of the name of the broken check. Fourth outing for the by-name habit, after
# the exec-bit guard, shellcheck and NOT_SHIPPED. Enumerate from the repo, and
# fall back to PAYLOAD so an installed copy still checks what it shipped.
py_files = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT,
                          capture_output=True, text=True, timeout=60)
if py_files.returncode == 0 and py_files.stdout.split():
    scan = py_files.stdout.split()
else:
    # No git - an installed copy. Walk the tree instead; still enumerated,
    # never a hand-kept list of names.
    scan = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.py")
                  if "__pycache__" not in p.parts)
PRINTS = ("print(", "actions.append(", "sys.exit(", "return dest, [")
bad = []
for rel in scan:
    f = ROOT / rel
    if not f.is_file():
        continue
    for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if s.startswith("#"):
            continue                  # comments are never printed
        if not any(tok in s for tok in PRINTS):
            continue
        try:
            line.encode("cp437")
        except UnicodeEncodeError as e:
            bad.append(f"{rel}:{n} {e.object[e.start:e.end]!r}")
check(f"printed strings are cp437-safe across all {len(scan)} shipped .py files",
      not bad, "; ".join(bad[:4]))

# ── payload drift guard ──────────────────────────────────────────────────────
# PAYLOAD is hand-maintained, so a new reference doc could silently fail to
# ship. That is the same drift that left the 0.3.0 and 0.3.1 docs behind the
# work, one layer down. Every tracked file must be shipped or explicitly
# excluded — "forgotten" is no longer a state this repo can be in.
sys.path.insert(0, str(ROOT))
import install as installer  # noqa: E402

SHIPPED = set(installer.PAYLOAD)

# No extension filter: the guard's set must be the SAME set prune operates on,
# or the two drift apart and the guard stops meaning anything. Every tracked
# file is named in one list or the other -- .gitignore, .gitattributes,
# docs/index.html, docs/.nojekyll and the workflow included.
def why_not_the_repo():
    """None when ROOT is this repo's own checkout, else the reason it isn't.

    Two separate failure modes, and only checking for the first left the
    second failing loudly:

    1. NO git. `git ls-files` outside a repository exits 128 with EMPTY
       stdout. Ignoring the return code turned "git cannot answer" into
       "nothing is unaccounted for", so the guard printed ok in every
       installed copy -- exactly where tests/ ships, for users to verify their
       own install.
    2. The WRONG git. Installed under a user's own project (`--project`, which
       install.py documents), git succeeds and enumerates THEIR repo. The
       guard then failed, naming `references/local-notes.md` -- the file the
       installer had just created for them on purpose -- as unaccounted for.
       A false alarm on the verification path is worse than a silent pass.

    So test identity, not availability. This is repo-development machinery; it
    runs only in the repo.
    """
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT,
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return "not a git checkout, so git cannot enumerate the repo"
    top = pathlib.Path(r.stdout.strip()).resolve()
    if top != ROOT.resolve():
        return f"this is an install inside a different repository ({top})"
    return None


def git_files(*args):
    r = subprocess.run(["git", "ls-files", *args], cwd=ROOT,
                       capture_output=True, text=True, timeout=60)
    return r.stdout.split() if r.returncode == 0 else None


not_the_repo = why_not_the_repo()
tracked = git_files() if not not_the_repo else None
# Untracked-but-not-ignored files count too. git ls-files sees only what is
# already staged or committed, so a brand-new reference doc stayed invisible to
# this guard until someone ran `git add` -- CI caught it, but only a step later
# than the author needed. --others --exclude-standard closes that gap while
# still respecting .gitignore, so local-notes.md and __pycache__ stay exempt.
untracked = git_files("--others", "--exclude-standard") if not not_the_repo else None

if tracked is None or untracked is None:
    # Name every check that did not run, one skip() each. The label used to
    # carry a hardcoded "(3 checks)" when only 2 were lost -- a literal count
    # is the same fossil class as a dated filename or a sed line range, and it
    # put a false number inside the machinery added for honesty. Counting
    # itself cannot drift.
    for missed in ("every tracked file is shipped or explicitly excluded",
                   "a second file in docs/audits/ does not break the guard"):
        skip(missed, not_the_repo or "git could not enumerate the repo")
else:
    # Use install.py's own matcher, so the guard and the exclusion list
    # cannot drift apart about what "excluded" means.
    unaccounted = sorted(f for f in (set(tracked) | set(untracked))
                         if f not in SHIPPED and not installer.is_excluded(f))
    check("every tracked file is shipped or explicitly excluded", not unaccounted,
          f"add to PAYLOAD or NOT_SHIPPED: {unaccounted}")

    # Prove the directory form actually holds when a second file lands there --
    # the failure mode a literal filename entry would have had.
    audits = ROOT / "docs" / "audits"
    if audits.is_dir():
        probe = audits / "audit-lite-probe-9999-12-31.md"
        probe.write_text("probe\n", encoding="utf-8")
        try:
            loose = git_files("--others", "--exclude-standard") or []
            leftover = [f for f in loose
                        if f not in SHIPPED and not installer.is_excluded(f)]
            check("a second file in docs/audits/ does not break the guard",
                  not leftover, f"{leftover}")
        finally:
            probe.unlink()
    else:
        skip("a second file in docs/audits/ does not break the guard",
             "docs/audits/ is not present here")

overlap = sorted(f for f in SHIPPED if installer.is_excluded(f))
check("no file is both shipped and excluded", not overlap, f"{overlap}")

# Exclusions must be patterns, not names. A literal filename means the next
# file added beside it fails this guard and forces an unrelated edit -- the
# by-name habit that has already cost this repo four times.
literal_files = [e for e in installer.NOT_SHIPPED
                 if not e.endswith("/") and "/" in e and e.count("/") >= 2]
check("no exclusion names a file inside a nested directory", not literal_files,
      f"prefer a trailing-slash directory entry: {literal_files}")

# Depth was the wrong property to test. It caught the dated audit report only
# because that report happened to sit two directories down; the identical
# fossil at docs/ or the repo root sailed through (measured). What actually
# makes an entry a fossil is the date in it, at any depth. CHANGELOG.md and
# .gitignore are legitimate literal names, which is why this tests for the
# date rather than banning literals outright.
dated = [e for e in installer.NOT_SHIPPED if re.search(r"\d{4}-\d{2}-\d{2}", e)]
check("no exclusion entry carries a date", not dated,
      f"exclude the directory instead: {dated}")

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
# Skips are reported in the tally, never swallowed. This suite used to print a
# clean "PASS: 21" in an installed copy and "PASS: 22" in the repo, with
# nothing to say which check had gone missing or why.
tail = f" ({len(skipped)} skipped: {'; '.join(skipped)})" if skipped else ""
if bad:
    print(f"FAIL: {len(bad)}/{len(results)} - {'; '.join(bad)}{tail}")
    sys.exit(1)
print(f"PASS: {len(results)} install.py checks{tail}")
