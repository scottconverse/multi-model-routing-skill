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
    "scripts/call_local.sh",
    "tests/test_call_local.py",
    "references/codex.md",
    "references/cross-agent.md",
    "references/local-backends.md",
    "references/local-notes.example.md",
]

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

    notes = dest / "references" / "local-notes.md"
    tmpl = dest / "references" / "local-notes.example.md"
    if notes.exists():
        actions.append("  local-notes.md already exists — left untouched (it's yours)")
    elif dry_run:
        actions.append("  would create local-notes.md from the template")
    else:
        if tmpl.is_file():
            shutil.copy2(tmpl, notes)
            actions.append("  created local-notes.md from the template")

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
        dest, actions = install(root, dry_run=args.list)
        print(f"\n{name}: {dest}")
        for a in actions:
            print(a)

    if args.list:
        print("\n(--list: nothing was changed)")
    else:
        print("\nDone. The folder name must stay 'multi-model-routing' — that's "
              "what SKILL.md's name: field expects.")
        print("Start a new agent session to pick it up.")


if __name__ == "__main__":
    main()
