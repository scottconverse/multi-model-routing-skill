# Prover — Spec and Implementation Plan (Layer 1 completion)

**Status:** Revision 3 — **approved by Scott 2026-08-11. Implementation authorized; codex begins at S0.**
**Decisions (Scott, 2026-08-11):** Sequencing = prover first, Milestone 2 design starts when F-8 passes (D-A). Repo = new standalone `prover` repo (Q-1). Manifest #2 = DevHarmonics npm package (Q-6).
**Supersedes direction (not content) of:** `SYSTEM_SPEC.md` / `IMPLEMENTATION_PLAN.md` in this directory. Those documents remain the design record; their §3 failure table, §5 authority map, §15 invariants, and the authority-rooted-completeness invariant from the review thread carry forward verbatim. Their 13-phase program does not.
**Authorization:** Design + one diff review. Implementation begins after Scott approves the revision.
**Working name:** `prover` — naming is Scott's call, nothing below depends on it.

---

## 1. What this is and why the plan changed

The 13-phase DevHarmonics Next program answered "how do we make giant unattended agent batches trustworthy." This plan splits that into:

- **Milestone 1 — the prover toolchain (this document):** lock, build-from-lock, finalize, attest, verify, journey, packet. Deterministic, CLI-shaped, manifest-driven, useful on *any* project on this machine.
- **Milestone 2 — the swarm execution layer:** scheduler, work packages, producer orchestration, large local-model swarms on the 128 GB AMD Halo machine, and the evaluation loop. **Sequenced after Milestone 1, not cancelled.** The prover is what makes swarm output *acceptable*: a swarm without an artifact-proof floor reproduces the CivicCast failure at higher speed. Ruflo, Switchyard, and learning/promotion are Milestone 2+ candidates, and each must beat the measured Milestone 1 + single-agent baseline (which includes v1's existing routing/ollama modules) to be admitted.

**This sequencing was approved by Scott on 2026-08-11 (D-A, §10): prover first.** The architecture supports building Milestone 2 immediately after (or alongside) Milestone 1; the recommendation is strictly ordered because every Milestone 2 result is untrustworthy until the prover exists to gate it.

Milestone 1 is general from day one: the tool reads a **project manifest**; it never contains the name of any project. CivicCast is manifest #1 and supplies the falsification fixture (the preserved stale-payload failure). A second manifest for a different artifact type follows within weeks (§9, "rule of two manifests").

## 2. What exists, what doesn't (corrected)

A code-level inventory (2026-08-11) of the repos found reusable **patterns and modules at both ends** of the pipeline — but the six modules in §6 are the product's core, and they exist nowhere. "Most of Layer 1 exists" overstates it; the honest statement is: *the receipt, budget, integration, identity, assurance, and reconciliation patterns exist and are battle-tested; the product-bytes middle is unbuilt.*

The design documents missed this because "artifact" means three different things across the corpus:

| Corpus | "artifact" means |
|---|---|
| Current DevHarmonics (`C:\Users\scott\Desktop\Code\DevHarmonics`) | a **tool binary** (tampercheck/validator executable identity) |
| devharmonics-v1 (GitHub: `scottconverse/devharmonics-v1`, not currently cloned locally) | a **delivery object** (branch, PR, checks, tag) |
| The Next-plan documents | **product bytes** (installer, packs, packages, images) |

```
current DevHarmonics          [ THE GAP ]              devharmonics-v1
─────────────────────         ───────────              ─────────────────────
worker receipts               build from lock          typed delivery actions
admission/budgets             embed/verify bindings    tag-truth gate
integration sets (2-phase)    SET-level consistency    remote reconciliation
tampercheck identity          clean-profile attest     release-unit authority
assurance grading             journey runner           verification-integrity
                              packet compiler          ledger + redaction
   pre-merge truth          product-bytes truth          post-merge truth
```

### 2.1 The sharpened gap: sets, not files

Verified against `C:\Users\scott\Desktop\Code\civiccast-b3-audit` (2026-08-11): the native-beta candidate is **not one installer**. It is a release set —

- signed installer EXE (Azure Artifact Signing; cert key in Azure's HSM, never on any local machine or runner);
- `native-app-payload.ccpack`;
- `native-server-binaries.ccpack`;
- `native-ffmpeg-runtime.ccpack`;

uploaded as four separate candidate artifacts (`.github/workflows/native-beta-candidate-artifacts.yml`). Furthermore, per-artifact defenses **already exist**: the pack builder refuses to pack a tree whose embedded `source_sha` mismatches (`scripts/build_native_app_payload_pack.py`), and the installer bootstrap verifies each pack tree at install time (`--civiccast-verify-pack-tree`).

**The historical failure was set-level:** an EXE from commit A paired with a self-consistent, individually-valid pack from commit B (`NATIVE-BETA-HANDOFF-2026-08-02-OVERNIGHT.md`). Every artifact defended itself; nothing defended the set. The prover's central new capability is therefore **cross-artifact set verification against an authority root**, not per-file probe stamping — where bindings already exist (ccpack metadata), the prover *verifies* them; it adds probes only where an artifact type carries no binding.

## 3. Verified inventory (file-level, checked 2026-08-11)

### 3.1 Current DevHarmonics — reuse in A0

| Module | Role in prover |
|---|---|
| `scripts/receipts.mjs` | Attempt envelope. One schema across lanes; absence-as-null-never-zero; `resolutionVerified`. Becomes `attempt-result.json`. |
| `scripts/admission.mjs` | Budget ledger: append-only, file locks, full replay, highest-terminal-wins (MONEY-001). |
| `scripts/integrate.mjs` + `scripts/integration-set.mjs` | Two-phase multi-repo integration; per-repo `baseCommit` pinned at plan time, all-or-nothing readiness. Source half of the candidate lock. |
| `scripts/integrate.mjs` tampercheck | Executable identity: `expectedTampercheckSha256`; "version SHAPE only" distinction. |
| `scripts/assurance.mjs` | Claim-vs-evidence grading derived only from evidence that ran. Ancestor of the packet compiler. |
| `scripts/probes.mjs` | The house rule the prover inherits: *"a probe that could not run its check reports FAIL with the reason, never PASS by absence of error."* |
| `scripts/run-worker.mjs`, `messages-client.mjs`, `qualify.mjs` | Executor-lane patterns for the seat contract (§7). |
| `test/` (31 files) | Falsification-suite pattern; migration criterion: original test fails against a vulnerable fixture, passes against the prover. |

### 3.2 devharmonics-v1 — **patterns only in A0; no ports**

Publication is out of A0 scope, so `delivery.ts` and `reconciliation.ts` are **not ported now**. They are recorded as the designated A1 basis (typed delivery actions, tag-truth gate, `matches / diverged / unobservable` reconciliation) and as the source of invariant I-6. Two v1 items do enter A0 as *patterns*:

| Module | A0 use |
|---|---|
| `src/verification-integrity.ts` | Anti-gaming taxonomy (`test-deleted / test-skipped / test-focused / assertion-weakened / unconditional-success / placeholder / swallowed-error`) → invariant I-8; reimplemented over producer diffs in the packet compiler's integrity pass. |
| `src/release-units.ts` | Manifest-inventory-at-exact-OID pattern → the lock's authority-rooting discipline. |

v1's `model-intelligence` / `ollama` / `routing` modules are noted as the existing baseline Track B must beat. v1's SQLite `ledger.ts` record shapes inform the packet schema so a future Milestone 2 ledger ingests prover runs without rework.

### 3.3 MMR skill (`C:\Users\scott\Desktop\Code\multi-model-routing-skill`)

Routing *knowledge and scripts* — *not* a stable invocation runtime. **The prover owns the executor command contract** (§7); MMR may inform which command the manifest configures, nothing more.

### 3.4 CivicCast assets (manifest #1 content)

Build commands, walkthrough journeys, clean-Windows proof procedure: `C:\Users\scott\Desktop\Code\civiccast\docs\audits\` audit-lite kits and the native-beta handoffs. The candidate workflow, pack builder, and bootstrap verifier in `civiccast-b3-audit` define the artifact topology and existing bindings. Manifest #1 is transcription plus the topology declaration.

### 3.5 The six new modules (the product's core — exists nowhere)

1. Build-from-lock for the product artifact set.
2. Binding embed/verify per artifact type (verify existing bindings first; add probes only where none exist).
3. **Set-level verification**: complete expected set + cross-artifact consistency against the authority root.
4. Clean-profile attestation.
5. Journey runner (zero "journey" hits in any repo — verified).
6. Contract-rooted packet compiler.

## 4. Product definition

A standalone CLI. No daemon, no database. Files in, files out, one run directory per invocation. Native Windows first (the artifacts being proven are Windows binaries; the proof runs on the product's side of the boundary).

```
prover run      --manifest <path> --profile <name> --run <dir>   # execute/resume the whole graph
prover lock     --manifest <path> --run <dir>     → candidate-lock.json
prover build    --run <dir>                       → artifact set + observed-contents report
prover finalize --run <dir>                       → final bytes per transform adapter + digest chain
prover ingest   --run <dir>                       → final bytes into objects/ (immutable, hash-addressed)
prover verify   --run <dir> [--static]            → set-verification.json
prover attest   --profile <name> --run <dir>      → profile-attestation.json
prover journey  --run <dir>                       → journey/<n>/ evidence
prover packet   --run <dir>                       → acceptance-packet.json
prover replay   --fixture <path> --run <dir>      → runs the falsification matrix (§9)
```

`prover run` executes the dependency graph (`lock → build → finalize → ingest → attest → verify → journey → packet`). The individual commands remain for debugging and single-node reruns. `verify --static` inspects final bytes without a profile (set completeness, bindings, digests); full `verify` additionally installs in the attested profile.

Failure and resume semantics:

| Condition | Behavior |
|---|---|
| Deterministic stage failure | Stop; preserve the attempt receipt; **no automatic retry** (I-7 — retry eligibility is policy, and unchanged input reproduces the failure). |
| Ambiguous CI-finalize result | Reconcile the recorded CI run (workflow run ID + receipts) before any retry; never re-trigger blind. |
| Journey failure | Bounded attempts declared in the manifest (default 2), then stop with evidence preserved. |
| Resume skip | Requires a terminal PASS receipt **plus** input/output digests fresh against the authority root — never the mere existence of output files. |

**After `ingest`, every later stage consumes a digest resolved through `objects/` — never a mutable filesystem path.**

**The manifest** (`prover-manifest.yaml`, one per project) declares: repositories + roles + authoritative branches; build command(s); **artifact topology** — the complete expected artifact set, each artifact's kind, its binding mechanism (existing metadata vs. injected probe), and the cross-artifact consistency rules; finalization transforms per artifact (§6.3); clean-profile definition (image/snapshot identity + forbidden-residue list); journeys; acceptance criteria; owner-only actions.

## 5. Invariants

- **I-1 Authority-rooted completeness.** Every admission/verification/acceptance decision derives its required set from the **authority root: the validated manifest digest + the resolved candidate lock digest, bound as a pair** — never from the subject being evaluated. Missing, stale, circular, or unbound items fail closed. Root changes invalidate dependent evidence (validity computed at read time by digest comparison — a join, not a notification).
- **I-2 Absence fails like mismatch.** A missing artifact, binding, receipt, or attestation is a hard failure of equal severity to a wrong one.
- **I-3 Exact binding, set-complete.** Source claims bind to SHAs; product claims bind to the digests of the **complete artifact set** + environment identity. N−1 valid artifacts = failed set. Evidence does not transfer across a changed digest.
- **I-4 Coordination is not execution.** Only a normalized non-empty receipt plus an independent check completes anything.
- **I-5 Byte-mutating transforms create new identity.** Signing, bundling, timestamping, compression → new digest, recorded transform receipt, predecessor's artifact-level evidence invalidated. Verification counts only on final publishable bytes.
- **I-6 Irreversible actions are observed, not re-run.** Post-action reconciliation against the root (v1 `reconciliation.ts` pattern: `matches / diverged / unobservable`), never retried automatically unless proven idempotent. (A1 concern; recorded now so A0 schemas leave room.)
- **I-7 Classification by authority.** Runtime owns observable outcomes; independent checkers own semantic verdicts; policy owns retry eligibility; the producer owns none of these.
- **I-8 Check integrity is itself checked.** A passing check whose integrity wasn't verified is not evidence (verification-integrity taxonomy over producer diffs).
- **I-9 Advisory context never becomes evidence.**
- **I-10 Independence is recorded, not assumed.** Every evidence file records its producer (executor, model with `resolutionVerified`, session, environment); the packet reports the independence vector actually achieved per criterion.
- **I-11 Proof boundaries are honest about agents.** The prover proves *which request it issued* (compiled, hashed) and *what observations came back*. It cannot prove an agent executed a journey "byte-identically"; agent fidelity is a recorded proof boundary, not a claim.

## 6. New modules — build specs

House style: Node ESM `.mjs`, matching the current kernel. Failure semantics follow I-2 throughout.

### 6.1 `manifest` + `lock`
Manifest schema/validation is a compile step: required fields, artifact topology well-formedness, path-sensitive input rules, ≥1 acceptance criterion, ≥1 journey. `lock` extends `integration-set.mjs` pinning into `candidate-lock.json`: per-repo exact SHA **and review-base SHA** (so I-8's producer-diff range is deterministic; `integration-set.mjs` already tracks `baseCommit`) + dirty state, submodules/packages, runtime versions, tool identities, environment fingerprint. The validated-manifest digest + lock digest pair is the run's authority root (I-1). Refuses dirty repos unless the manifest names an exception.

### 6.2 `build`
Materializes a workspace *only* from the lock (fresh checkout of exact SHAs — never the developer tree) and runs the manifest's build commands to produce the **artifact set**. Emits two separate records, never merged: `expected-set.json` — compiled independently from **manifest topology + lock** — and `observed-contents.json` — what the build actually produced. Where the artifact type declares an existing binding mechanism (e.g. ccpack embedded `source_sha`), `build` confirms it was populated from this lock; where none exists, injects a probe carrying `{repo, sha, root-digest, run-id}`.

### 6.3 `finalize`
One adapter per declared transform; **signing is two different systems and gets two adapters**:

- **`azure-artifact-signing`** — installer EXE; the key lives in Azure's HSM and never touches any machine here. **Resolved (Q-2): CI executes finalize; the prover ingests signed bytes + receipts and re-verifies digests.** CivicCast's release workflow already signs *after build, before hashing* and regenerates hashes post-signing (`release-artifacts.yml`) — reuse it, with one addition: the current `candidate-receipt.json` is unsigned, so finalize also emits a **set manifest (every final artifact digest + the authority root) attested with CivicCast's existing Cosign pattern**. That signed set attestation is simultaneously the EXE's set-level binding (Q-4) — it directly encodes "these exact artifacts belong together under this root," which is the property whose absence caused the historical failure.
- **`ed25519-pack-signing`** — `.ccpack` components; local key per the pack builder's existing contract.

Every transform: consumes an immutable input digest, produces a new output digest, records `{transform, tool identity, policy, receipt}`, invalidates predecessor artifact-level evidence (I-5). Reproducible unsigned payload and traceable signed envelope both keep recorded digests.

### 6.4 `verify`
Static pass (`--static`, no profile): against `expected-set.json` (authority-root-derived, never the artifacts' own manifests):
1. **Set completeness** — every expected artifact present; absence = failure (I-2);
2. **Set consistency** — every artifact's binding resolves to the *same* lock; any pairwise mismatch (EXE from commit A + pack from commit B — the historical failure) = failed set;
3. per-artifact bindings valid (existing metadata verified, injected probes matched) and the Cosign set attestation verifies against the authority root;
4. no artifact matching a *different* lock (stale detection, names the stale SHA);
5. N−1 valid + 1 invalid = failed set, no partial credit (I-3);
6. **expectations** never derive from the artifact; **observed bindings** may derive from authenticated metadata or injected probes, and are checked against the authority root.

Installed pass (requires `attest`): install/extract exact final bytes in the attested profile; re-verify bindings from installed/loaded state; reuse the existing bootstrap `--civiccast-verify-pack-tree` behavior as a sub-check rather than reimplementing it. Emits `set-verification.json`, one row per expected artifact per check.

### 6.5 `attest`
Proves the profile is clean before installed-verify/journey: snapshot/image identity, reset receipt, forbidden-residue probes (files, services, registry keys, processes, ports, caches, PATH) per the manifest's residue list. Dirty profile refuses the run. Identity + reset + residue checks — not a full-profile hash.

### 6.6 `journey`
Executes the manifest's pre-approved journeys against verified final bytes in the attested profile through an executor seat (§7). The prover compiles the journey into a **hashed request** (steps, expected observations, environment) proven identical to the manifest's approved journey; captures screenshots/logs/state per step; records automation limits and physical-observation boundaries. Per I-11, fidelity of the agent's execution is a recorded proof boundary.

### 6.7 `packet`
Deterministic compiler. Roots in the authority pair's acceptance criteria + journeys (I-1); joins every criterion to evidence rows (digest, freshness vs. root, proof boundary, independence vector, assurance grade); runs the I-8 integrity pass; marks unmatched criteria `UNPROVEN` — visible, never absent. The audit seat *annotates and challenges*; it never authors or filters. Schema shaped for future Milestone 2 ledger ingestion.

## 7. Executor seats

The prover's only agent interface. A seat invocation is: a **compiled, hashed request** + explicit named inputs + a designated output location — **never mutable ownership of the run directory**. The prover wraps every invocation in a receipt (`receipts.mjs`): executor identity, model (`resolutionVerified` semantics), session, wall time, request hash.

Seats in v0: `journey` (required), `audit` (optional annotator). Scout/plan/build/repair seats are Milestone 2. Routing a seat to Claude/Codex/local models is configuration the manifest owns; MMR knowledge may inform the choice. The prover records who showed up (I-10).

**Re-derivation rule:** A0 re-derives **all** acceptance-critical bindings. With four artifacts, sampling buys nothing — and any sampling scheme seeded from producer-influenceable material (run IDs known in advance, evidence-set digests that can be ground by varying timestamps) is gameable. If sampling ever becomes necessary at scale, selection uses independent randomness generated *after* evidence commitment and recorded in a receipt — never a digest a producer can influence. Re-derivation recomputes from raw bytes and compares values, not receipts.

## 8. Out of A0 scope (sequenced, not rejected)

- Milestone 2: scheduler, work packages, producer orchestration, swarms, repair loops and their budget semantics, mission control, event streams, resident ledger service.
- Ruflo, Switchyard, learning/promotion (Track B; must beat the measured baseline, which includes v1's own routing modules).
- Publication adapters — v1 `delivery.ts`/`reconciliation.ts` are the designated A1 basis; **no port during A0**. In v0 Scott publishes via existing v1 actions or by hand, from the packet.
- CAS garbage collection and retention policy (v0: hash-keyed `objects/` directory, manual cleanup).

## 9. A0 acceptance — the falsification matrix

Against manifest #1 (CivicCast) on this machine:

| # | Fixture | Required result |
|---|---|---|
| F-1 | Correct complete artifact set | PASS |
| F-2 | One expected artifact **absent** | FAIL (severity = mismatch) |
| F-3 | One artifact stale (binds to an older lock) | FAIL, names the stale SHA |
| F-4 | N−1 valid + 1 invalid (within-artifact binding broken) | FAIL, no partial credit |
| F-5 | **Set mismatch: every artifact individually valid, two bound to different locks** (the historical failure shape) | FAIL, names both locks |
| F-6 | Artifact altered after verification (digest drift before packet) | FAIL |
| F-7 | Dirty clean-profile (seeded residue) | `attest` refuses the run |
| F-8 | **Preserved CivicCast stale-payload replay** (characterized and preserved in S0) | the historical set fails `verify`; the corrected build passes |
| F-9 | Journey request differing from the manifest's approved journey | `journey` refuses |
| F-10 | Unmatched acceptance criterion | packet shows `UNPROVEN`; run does not report success |
| F-11 | Seeded no-op validator (`node -e "process.exit(0)"`) | integrity pass exposes it; packet does not count it as evidence |

Bidirectional throughout: each detector fails its seeded fixture **and** passes the corrected one.

**Rule of two manifests:** within ~2 weeks of F-1..F-11 passing, manifest #2 for a different artifact type — recommend DevHarmonics itself (npm package: no installer, no Azure signing, single-artifact set) — must run F-1..F-6 + F-10 with no prover code changes beyond per-artifact-type binding adapters.

## 10. Decisions and resolved questions

**Resolved by Scott (2026-08-11):**

- **D-A Sequencing** — prover first; Milestone 2 (swarm layer) design begins when F-8 passes.
- **Q-1 Repo location** — new standalone `prover` repo. This activates Q-3's separate-repo rule: copy only small self-contained functions with provenance; port behavior from coupled modules.
- **Q-6 Manifest #2** — DevHarmonics npm package.

**Resolved earlier:**

- **Q-2 Finalize boundary** — CI-executed finalize with locally ingested, digest-re-verified receipts, plus the Cosign-attested set manifest (§6.3).
- **Q-3 Reuse mechanics** — conditional on Q-1. Inside DevHarmonics: import directly. Separate repo: copy only small self-contained functions with `PROVENANCE.md`; **do not wholesale-copy coupled modules** such as `integration-set.mjs` — port the pinning behavior instead.
- **Q-4 Binding adapters** — `ccpack-metadata` (verify existing embedded `source_sha`); the installer EXE embeds its pack trust root but **not** its source SHA (`build_native_bootstrap.py` records only artifact digest + key ID), so the EXE is bound by build/finalize lineage plus the **signed set attestation** (primary — it addresses the actual set-level failure directly).
- **Q-5 Clean profile** — already decided by an owner-approved CivicCast decision (`spec-native-beta-recovery.md`): **Windows Sandbox primary**; persistent VM only for reboot, pre-login, or multi-session boundaries. Starting implementation: the existing nonce/fresh-directory cleanroom gate (`ws5-packaging-closure/evidence/cleanroom-gate.sh`). **Windows Sandbox is not currently enabled on this machine — S0 enables it** (admin feature enable via the elevated dev helper).

## 11. Build order

Dependency-true: `lock → build → finalize → ingest → attest → verify(installed) → journey → packet`, with static verify available early. **F-8 characterization starts in S0, not at the end** — the fixture that defines the product is preserved before abstractions are built.

1. **S0 — Repo, provenance, and the fixture.** Create repo (Q-1); **commit this plan file so every future revision has a real git diff**; clone v1 locally; bring in reused code per the Q-3 rule (small self-contained functions with `PROVENANCE.md`; port behavior from coupled modules, don't copy them); carried falsification tests pass unchanged. **Locate and preserve the stale-payload evidence** (native-beta handoffs, `civiccast-releases`, `civiccast-b3-audit`): exact artifact files or their digests + the two mismatched locks, stored as the F-8 fixture. **Enable Windows Sandbox** (elevated dev helper). If the historical bytes are unrecoverable, S0 reconstructs an equivalent mismatched set and records that substitution in the fixture's provenance.
2. **S1 — Artifact characterization + `manifest` + `lock`.** Codex inspects the real candidate workflow, pack builder, bootstrap verifier, and installer layout; writes the topology section of manifest #1; resolves Q-4. Then manifest schema/validation and `candidate-lock.json`. Tests: lock refuses dirty repo; root digest stable across re-runs.
3. **S2 — `build` + expected/observed separation.** Expected set compiled from topology + lock; observed contents reported separately; existing ccpack bindings confirmed; probe injection where declared. 
4. **S3 — `finalize` + `ingest`.** Both signing adapters per Q-2 decision; digest chain + transform receipts; immutable `objects/`. 
5. **S4 — `attest`.** Windows Sandbox + the cleanroom-gate pattern per Q-5. Fixture F-7.
6. **S5 — `verify`.** Static pass first (F-1..F-6 runnable now), then installed pass reusing the bootstrap pack-tree check. 
7. **S6 — `journey` + seats.** Compiled hashed requests, receipts, output containment. F-9.
8. **S7 — `packet` + re-derivation + `prover run`.** Integrity pass (F-11), `UNPROVEN` surfacing (F-10), commit-then-select re-derivation; the top-level graph runner with resume.
9. **S8 — F-8 end to end.** The preserved historical set fails; the corrected build passes; both directions recorded.
10. **S9 — Manifest #2** (Q-6); generality subset with no core changes.

Definition of done = §9 in full. Code volume, passing unit tests, or agent activity is not a substitute for any fixture.

---

*Inventory verified 2026-08-11 against `C:\Users\scott\Desktop\Code\DevHarmonics`, `C:\Users\scott\Desktop\Code\civiccast-b3-audit` (candidate workflow, pack builder, release signing workflow, overnight handoff), and a shallow clone of `scottconverse/devharmonics-v1`. Revision 2 incorporated the first coder review: set-level topology, dependency-true build order, dual signing adapters, authority root as manifest+lock pair, seat containment, I-11 honest agent proof boundaries, v1 ports deferred to A1, `prover run` added. Revision 3 incorporates the second coder review: sequencing marked pending Scott's decision, `prover run` failure/resume semantics, re-derive-all replacing the grindable commit-then-select, expectations-vs-observed-bindings wording, review-base SHA in the lock, Q-2/Q-3/Q-4/Q-5 resolved (CI finalize + Cosign set attestation; conditional reuse rule; set attestation as the EXE's set binding; Windows Sandbox + cleanroom gate, with S0 enabling Sandbox).*
