# Audit post-mortem — 2026-08-09

On 2026-08-09 this repo went through eight consecutive audit rounds, each one
reviewing the fix commit produced by the previous one. Seventeen findings, all
fixed. The full detail is in the git history (`git log v0.3.5..`); the ten
individual reports were removed because they had grown to **913 lines of
process notes against 117 lines of actual product change**, which is a bad
thing to hand someone cloning a small skill.

Two things are worth keeping.

## 1. A guard narrower than its own name

Six of the seventeen findings were the same defect: a check that encoded **the
example it was written against** rather than **the property it claimed to
enforce**.

- Enumerating files *by name* — the executable-bit guard, shellcheck, the
  `NOT_SHIPPED` list, the cp437 scan. Each went blind the moment a second file
  arrived.
- Testing *depth* (`e.count("/") >= 2`) when the property was *datedness* in a
  filename.
- Testing a *substring* when the property was *a row in a table* — a doc check
  passed because prose above the table happened to mention the flag.
- Matching `subprocess.run` when the property was *"spawns git"* —
  `check_output`, `Popen` and `check_call` all sailed through.

**Practice:** read a check's name back as a specification and ask what else
satisfies it. Enumerate from a source of truth — `git ls-files`, an AST walk,
the parser's own `case` labels — never a hand-kept list, a literal filename, or
a hardcoded count. Prefer parsing to substring search when the question is
structural.

## 2. A check that is green because of where it runs

- The payload drift guard called `git ls-files` and never checked the return
  code. Outside a checkout that exits 128 with empty stdout, so "git cannot
  answer" silently became "nothing is unaccounted for" — and it printed `ok`
  in every installed copy, which is exactly where `tests/` ships for users to
  verify their own install.
- The CI "no CRLF" check grepped the working tree of a fresh checkout, after
  `.gitattributes` had already normalised everything to LF. It could not fail.

**Practice:** ask *where does this run, and where does it ship?* A guard
verified only in CI is unverified where the artifact lands.

## The practice that did the most work

**Watch every new assertion fail on purpose.** Perturb the thing it guards,
confirm it goes red naming the right target, revert. This caught a vacuous
assertion in the same pass that wrote it — the first perturbation run scored
4/5 and named its own bad check.

It is also the reason the later guards are known to fire rather than assumed
to. Two of them are enforced from the parse tree precisely so they cannot
quietly stop working.

## What the sequence got wrong

Each round audited the commit the previous round produced — including that
round's own report. The loop therefore fed on its own output, and by rounds six
and seven it was reviewing commits containing **zero code files**. The exit
condition ("two clean rounds") was met by shrinking the input, not by the code
getting cleaner.

A single whole-state pass over `v0.3.5..HEAD` afterwards found a real guard
hole in minutes that seven scoped rounds had structurally never looked at: a
line changed in one commit and never touched again gets reviewed exactly once.

**Practice:** per-commit review has a blind spot. Do one whole-state pass
before tagging, and stop a review loop when its scope stops containing product.
