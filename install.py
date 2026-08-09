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


def uninstall(dest_root, dry_run=False):
    """Remove the installed skill, preserving the user's local-notes.md.

    Refuses to delete a directory that doesn't look like this skill, so a
    mistyped --project can't take out something unrelated.
    """
    dest = dest_root / SKILL_NAME
    actions = []
    if not dest.exists():
        return dest, ["  not installed here — nothing to do"]

    if not (dest / "SKILL.md").is_file():
        return dest, ["  REFUSED: no SKILL.md here, so this isn't the skill. "
                      "Nothing deleted."]

    notes = dest / "references" / "local-notes.md"
    if notes.is_file():
        keep = dest_root / f"{SKILL_NAME}.local-notes.backup.md"
        actions.append(f"  {'would preserve' if dry_run else 'preserved'} your notes -> {keep}")
        if not dry_run:
            shutil.copy2(notes, keep)
    else:
        actions.append("  no local-notes.md to preserve")

    actions.append(f"  {'would remove' if dry_run else 'removed'}: {dest}")
    if not dry_run:
        shutil.rmtree(dest)
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
        print("\nUninstalled. Nothing else was installed anywhere — no config "
              "edits, no services, no registry entries.")
        print("Any MCP servers you registered are separate and stay put; remove "
              "them with your agent's own tooling if you want them gone.")
    else:
        print("\nDone. The folder name must stay 'multi-model-routing' — that's "
              "what SKILL.md's name: field expects.")
        print("Start a new agent session to pick it up.")


if __name__ == "__main__":
    main()
