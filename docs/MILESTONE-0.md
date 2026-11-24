# Milestone 0 — Architecture and Environment

**Status:** IN PROGRESS  
**Branch:** `feature/m0-data-contracts` (M0-02 work; `architect/milestone-0` was merged to `main` in PR #7)  
**Acceptance owner:** Project Owner  
**Technical owner:** Agent 0 — Project Architect

## Scope
Establish approved architecture, shared contracts, source layout, dependency strategy, risk register, test strategy and a reproducible Windows 11 development environment before feature implementation.

## Work items and evidence

| ID | Work item | Evidence required | Status |
|---|---|---|---|
| M0-01 | Confirm approved stack and modular-monolith boundaries | ARCHITECTURE.md reviewed | Draft; scope documents (PRODUCT_SCOPE, ROADMAP, DECISIONS, FLOWS, OVERLAY_AND_ROI) written 2026-11-22, **awaiting owner review** |
| M0-02 | Define shared event/data contracts | DATA_CONTRACTS.md + Pydantic/JSON Schema + tests | Implemented as **v0.2** (C1–C6) and tested on Linux only; **Windows re-run, independent review and owner acceptance pending** (see below) |
| M0-03 | Define source tree and module ownership | ARCHITECTURE.md | Draft |
| M0-04 | Validate Windows/Python compatibility | exact versions + successful imports | **Partially validated**: owner reported Python 3.11.9, `uv sync` and the scaffold tests on Windows (ENVIRONMENT-REPORT.md). Full stack not validated. Scripts W0/W1 written, **not run on Windows** |
| M0-05 | Validate DXGI capture | real frame capture smoke test on target Windows | Blocked: script W2 written, **not run on Windows** |
| M0-06 | Validate PP-OCRv6 Small CPU | model load + sample inference + latency | Blocked: script W3 written, **not run on Windows**; exact small model names unconfirmed |
| M0-07 | Validate local NLLB runtime | model load + EN→VI smoke test + memory/latency | Blocked: script W4 written, **not run on Windows** |
| M0-08 | Select OpenAI model configuration | current API docs + benchmark + owner approval | Pending: script W5 written; needs the owner's key and a model choice; **not run** |
| M0-09 | Define dependency lock | Windows lockfile + clean install test | Partial: `uv.lock` now includes `jsonschema` and passes `uv lock --check` on Linux; it covers only the current lightweight scaffold. The full runtime stack is **not locked** and nothing was clean-installed on Windows |
| M0-10 | Define testing and performance gates | TESTING.md + CI plan | TESTING.md updated; owner decided no mandatory CI now (D-20); W0–W8 scripts written. Performance gates not defined (no budgets approved) |
| M0-11 | Create GitHub issue backlog | scoped issues linked to milestone | Pending |
| M0-12 | Independent architecture/contract review | reviewer findings resolved | Pending |

### Windows validation scripts (scripts/windows_tests/)

| ID | Script | Linux dry run | Windows run |
|---|---|---|---|
| W0 | W0_env_snapshot.py | ran: `DRY_RUN_FAIL` (Linux; target-machine checks fail by design) | **Not run** |
| W1 | W1_dependency_imports.py | ran: `DRY_RUN_FAIL` (packages not installed on Linux, as expected) | **Not run** |
| W2 | W2_dxgi_capture.py | `SKIP` off-Windows | **Not run** |
| W3 | W3_ocr_ppocr.py | `DRY_RUN_FAIL`: stopped at missing packages, as expected; small model names exist in the official HF collection but loading is unverified | **Not run** |
| W4 | W4_nllb.py | `DRY_RUN_FAIL`: stopped at missing `torch`, as expected | **Not run** |
| W5 | W5_openai.py | `SKIP` without a key | **Not run** |
| W6 | W6_overlay_hotkeys.py | `SKIP` off-Windows; syntax and lint only | **Not run** |
| W7 | W7_queue_timeout.py | ran: `DRY_RUN_PARTIAL` (simulation; helper-only checks are N/A, no real pipeline exists) | **Not run** |
| W8 | W8_game_impact.py | `run` is `SKIP` off-Windows; `analyze` ran on synthetic data | **Not run** |

A Linux dry run is not evidence for the target machine. See `scripts/windows_tests/README.md`.

## Exit criteria
- [ ] Project Owner approves architecture and technology decisions.
- [ ] All module contracts are versioned and validated with tests.
- [ ] Clean Windows 11 environment installs from a committed lockfile.
- [ ] DXGI smoke test passes on target hardware.
- [ ] PP-OCRv6 Small CPU smoke test passes and latency is recorded.
- [ ] NLLB-200 600M smoke test passes and resource use is recorded.
- [ ] OpenAI integration model is selected from current official API documentation and measured.
- [ ] GitHub backlog exists with acceptance criteria and ownership.
- [ ] Independent QA review has no unresolved blocker-level findings.

## Explicit non-goals
- No full screen-to-overlay feature implementation in Milestone 0.
- No training of OCR or translation models from scratch.
- No unapproved replacement of technologies in the Master Prompt.
- No claiming environment or hardware tests passed without logs.

## M0-02 status (data contracts)
- Implemented: all ten Master Prompt contracts (`CapturedFrame`, `TextRegion`, `OCRResult`≡`OCRObservation`, `TrackedText`, `DialogueEvent`≡`LifecycleEvent`, `TranslationRequest`, `TranslationResult`, `OverlayMessage`≡`OverlayUpdate`, `GameProfile`, `PerformanceMetric`) plus `SubtitleContext`/`ErrorInfo`; 13 generated JSON Schemas in `schemas/`.
- v0.2 (owner-approved 2026-11-22): `Trigger` and `batch_id` on `TranslationRequest` (C1); `display_mode` removed and `batch_id` added on `OverlayUpdate` (C2); `OverlayStyle` per game replaces `overlay_display_mode`, `OverlayDisplayMode` deleted (C3); no ROI change (C4); no `LifecycleReason` change (C5); `schema_version` `0.1` → `0.2` (C6).
- Verified by running on Linux (CPython 3.11.18): `pytest` 429 passed (415 contract/doc/schema tests plus 14 tests of the Windows-script helpers), `ruff check`, `ruff format --check`, `scripts/export_schemas.py --check`, `uv lock --check`. **Not run on Windows or CPython 3.11 on the owner's machine.**
- Not done / open: reviewer sign-off, owner acceptance, unresolved design decisions in `DATA_CONTRACTS.md` §17 and `DECISIONS.md` §3. Contracts are not yet exercised by any real pipeline module.
- M0-02 completion does **not** complete Milestone 0; all exit criteria remain unchecked. Milestone 1 has not been started.

## Current repository inspection
Historical note: at the original inspection the repository contained only a 2-line README and one commit. The scaffold was later merged to `main` (PR #7). M0-02 work is isolated on `feature/m0-data-contracts`; `main` is left unchanged.
