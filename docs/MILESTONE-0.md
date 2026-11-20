# Milestone 0 — Architecture and Environment

**Status:** IN PROGRESS  
**Branch:** `architect/milestone-0`  
**Acceptance owner:** Project Owner  
**Technical owner:** Agent 0 — Project Architect

## Scope
Establish approved architecture, shared contracts, source layout, dependency strategy, risk register, test strategy and a reproducible Windows 11 development environment before feature implementation.

## Work items and evidence

| ID | Work item | Evidence required | Status |
|---|---|---|---|
| M0-01 | Confirm approved stack and modular-monolith boundaries | ARCHITECTURE.md reviewed | Draft |
| M0-02 | Define shared event/data contracts | DATA_CONTRACTS.md + Pydantic/JSON Schema + tests | Draft |
| M0-03 | Define source tree and module ownership | ARCHITECTURE.md | Draft |
| M0-04 | Validate Windows/Python compatibility | exact versions + successful imports | Blocked: target machine required |
| M0-05 | Validate DXGI capture | real frame capture smoke test on target Windows | Blocked |
| M0-06 | Validate PP-OCRv6 Small CPU | model load + sample inference + latency | Blocked |
| M0-07 | Validate local NLLB runtime | model load + EN→VI smoke test + memory/latency | Blocked |
| M0-08 | Select OpenAI model configuration | current API docs + benchmark + owner approval | Pending |
| M0-09 | Define dependency lock | Windows lockfile + clean install test | Blocked |
| M0-10 | Define testing and performance gates | TESTING.md + CI plan | Draft |
| M0-11 | Create GitHub issue backlog | scoped issues linked to milestone | Pending |
| M0-12 | Independent architecture/contract review | reviewer findings resolved | Pending |

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

## Current repository inspection
At inspection time, the private repository contained only a 2-line README, one initial commit, the `main` branch, and no open issues. This milestone work is isolated on `architect/milestone-0`; `main` is left unchanged.
