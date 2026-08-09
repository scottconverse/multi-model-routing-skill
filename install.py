#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Scott Converse
"""Install the multi-model-routing skill into one or more agent harnesses.

Copies this repo's skill files into each target's skills directory, creates the
per-machine local-notes.md from the template if missing, and never overwrites
an existing local-notes.md (that file holds your hardware and account facts).

Usage:
    python3 install.py                 # auto-detect and install everywhere found
    python3 install.py --app claude    # just Claude Code / Cowork
    python3 install.py --app antigravity
    python3 install.py --project .     # into ./.claude/skills for one project
    python3 install.py --list          # show what would happen, change nothing
    python3 install.py --uninstall     # remove it, preserving your local-notes.md
"""
import argparse
import os
import pathlib
import shutil
import sys

SKILL_NAME = "multi-model-routing"
SRC = pathlib.Path(__file__).resolve().parent

# Files that make up the installed skill. local-notes.md is deliberately absent:
# it is per-machine and generated from the .example, never shipped.
PAYLOAD = [
    "SKILL.md",
    "README.md",
    "LICENSE",
    "install.py",                      # so an install can remove itself
    "docs/MANUAL.md",                  # the human doc belongs WITH the install
    "scripts/call_local.sh",
    "tests/test_call_local.py",        # lets a user verify their own install
    "tests/test_install.py",
    "references/codex.md",
    "references/cross-agent.md",
    "references/local-backends.md",
    "references/local-notes.example.md",
]

# Tracked files deliberately NOT shipped, listed so the drift test can tell
# "decided against" apart from "forgotten". These document the repo for people
# working ON it; they are noise inside an install.
NOT_SHIPPED = [
    "CHANGELOG.md",                    # repo history, not skill behaviour
    "CONTRIBUTING.md",                 # for contributors, not users
    "docs/DISCUSSIONS_SEED.md",        # GitHub Discussions material
    "docs/index.html",                 # the landing page, published via Pages
    "docs/.nojekyll",                  # Pages build hint
    ".gitignore",                      # repo hygiene; an install is not a repo
    ".gitattributes",                  # ditto -- LF pinning matters in the repo
    ".github/workflows/test.yml",      # CI belongs to the repo, not an install
]

# Directories that mark a working copy under version control. Uninstalling one
# of these would take the history with it, and the documented Claude Code
# install IS the git checkout, so the SKILL.md guard alone does not catch it.
VCS_MARKERS = (".git", ".hg", ".svn")

TARGETS = {
    "claude": pathlib.Path.home() / ".claude" / "skills",
    "antigravity": pathlib.Path.home() / ".gemini" / "config" / "skills",
}


def detect():
    """A harness counts as present only if its skills directory's parent exists."""
    found = []
    for name, skills_dir in TARGETS.items():
        if skills_dir.exists() or skills_dir.parent.exists():
            found.append(name)
    return found


def install(dest_root, dry_run=False):
    dest = dest_root / SKILL_NAME
    actions = []
    for rel in PAYLOAD:
        src = SRC / rel
        if not src.is_file():
            actions.append(f"  MISSING in source, skipped: {rel}")
            continue
        tgt = dest / rel
        actions.append(f"  {'would copy' if dry_run else 'copied'}: {rel}")
        if not dry_run:
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, tgt)
            if rel.endswith(".sh"):
                os.chmod(tgt, 0o755)

    # Prune anything left from an older version, so a file renamed between
    # releases stops lingering where the agent might still read it. Never
    # touches local-notes.md (yours).
    #
    # NEVER prune inside a working copy. The documented personal install IS the
    # git checkout, and everything tracked-but-not-in-PAYLOAD lives there:
    # .gitignore, .gitattributes, .github/workflows/, docs/index.html, the
    # changelog. Skipping only paths under .git/ was not enough -- those files
    # sit beside it, not inside it. Pruning is for copied installs; in a
    # checkout, git already does this job.
    if dest.exists():
        checkout = next((m for m in VCS_MARKERS if (dest / m).exists()), None)
        if checkout:
            actions.append(f"  skipped pruning: {checkout}/ is present, so this is a"
                           " working copy and git manages stale files here")
        else:
            keep = {(dest / rel).resolve() for rel in PAYLOAD}
            keep.add((dest / "references" / "local-notes.md").resolve())
            for path in sorted(dest.rglob("*")):
                if not path.is_file():
                    continue
                if path.resolve() in keep:
                    continue
                actions.append(f"  {'would prune' if dry_run else 'pruned'} stale: "
                               f"{path.relative_to(dest).as_posix()}")
                if not dry_run:
                    path.unlink()

    notes = dest / "references" / "local-notes.md"
    tmpl = dest / "references" / "local-notes.example.md"
    if notes.exists():
        actions.append("  local-notes.md already exists - left untouched (it's yours)")
    elif dry_run:
        actions.append("  would create local-notes.md from the template")
    else:
        if tmpl.is_file():
            shutil.copy2(tmpl, notes)
            actions.append("  created local-notes.md from the template")

    return dest, actions


# Records whether each uninstall target was actually removed, so the closing
# message can't claim "Uninstalled" after refusing to touch anything.
REMOVED = []


def uninstall(dest_root, dry_run=False):
    """Remove the installed skill, preserving the user's local-notes.md.

    Refuses to delete a directory that doesn't look like this skill, so a
    mistyped --project can't take out something unrelated.
    """
    dest = dest_root / SKILL_NAME
    actions = []
    if not dest.exists():
        REMOVED.append(False)
        return dest, ["  not installed here - nothing to do"]

    if not (dest / "SKILL.md").is_file():
        REMOVED.append(False)
        return dest, ["  REFUSED: no SKILL.md here, so this isn't the skill. "
                      "Nothing deleted."]

    # The documented personal install is a git clone, so it has BOTH a SKILL.md
    # and a .git. Deleting it would take unpushed history with it — on POSIX
    # silently, on Windows by dying partway through on git's read-only objects
    # and leaving a half-removed tree. Refuse, and say why.
    found_vcs = next((m for m in VCS_MARKERS if (dest / m).exists()), None)
    if found_vcs:
        REMOVED.append(False)
        return dest, [
            f"  REFUSED: {dest}",
            f"  is a version-controlled working copy ({found_vcs}/ is present).",
            "  Removing it would delete your repository history along with the",
            "  skill, including any commits you have not pushed.",
            "",
            "  Nothing was deleted. If you meant to remove it, do that with git",
            "  - or delete the directory yourself once you're sure the history",
            "  is pushed or unwanted.",
        ]

    notes = dest / "references" / "local-notes.md"
    if notes.is_file():
        # Never overwrite an existing backup: install -> uninstall -> install ->
        # uninstall would otherwise put the freshly templated notes on top of
        # the backup holding every machine fact learned so far, which is data
        # loss inside the feature meant to prevent it.
        keep = dest_root / f"{SKILL_NAME}.local-notes.backup.md"
        n = 2
        while keep.exists():
            keep = dest_root / f"{SKILL_NAME}.local-notes.backup.{n}.md"
            n += 1
        actions.append(f"  {'would preserve' if dry_run else 'preserved'} your notes -> {keep}")
        if not dry_run:
            shutil.copy2(notes, keep)
    else:
        actions.append("  no local-notes.md to preserve")

    actions.append(f"  {'would remove' if dry_run else 'removed'}: {dest}")
    if not dry_run:
        shutil.rmtree(dest)
    REMOVED.append(True)
    return dest, actions


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", choices=sorted(TARGETS), action="append",
                    help="install into a specific harness (repeatable)")
    ap.add_argument("--project", metavar="DIR",
                    help="install into DIR/.claude/skills instead of a home directory")
    ap.add_argument("--list", action="store_true",
                    help="show what would happen without changing anything")
    ap.add_argument("--uninstall", action="store_true",
                    help="remove the skill; your local-notes.md is preserved alongside")
    args = ap.parse_args()

    if args.project:
        roots = {"project": pathlib.Path(args.project).resolve() / ".claude" / "skills"}
    else:
        chosen = args.app or detect()
        if not chosen:
            sys.exit("No supported harness found. Looked for ~/.claude and "
                     "~/.gemini/config. Use --project DIR for a project install.")
        roots = {n: TARGETS[n] for n in chosen}

    for name, root in roots.items():
        if args.uninstall:
            dest, actions = uninstall(root, dry_run=args.list)
        else:
            dest, actions = install(root, dry_run=args.list)
        print(f"\n{name}: {dest}")
        for a in actions:
            print(a)

    if args.list:
        print("\n(--list: nothing was changed)")
    elif args.uninstall:
        if any(REMOVED):
            print("\nUninstalled. Nothing else was installed anywhere - no config "
                  "edits, no services, no registry entries.")
            print("Any MCP servers you registered are separate and stay put; remove "
                  "them with your agent's own tooling if you want them gone.")
        else:
            print("\nNothing was removed. See the reason above each target.")
    else:
        print("\nDone. The folder name must stay 'multi-model-routing' - that's "
              "what SKILL.md's name: field expects.")
        print("Start a new agent session to pick it up.")


if __name__ == "__main__":
    main()
