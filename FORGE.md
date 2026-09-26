# FORGE — AI Coding Agent Hackathon 2026
## Complete Implementation Blueprint

> **Working concept:** Fork a mature open-source coding agent and transform it into a **self-verifying software-engineering agent** that plans, explores, edits, tests, diagnoses failures, challenges its own solution, and only declares completion when evidence supports the result.

---

# 0. Executive Decision

## Primary choice: `Cline` / `mini-SWE-agent`
FORGE integrates the modular design of `mini-SWE-agent` (lightweight, Python-based, hackable, designed around GitHub issue solving) with the Plan/Act, checkpointing, and tool execution architecture of `Cline`.

---

# 1. The Product: FORGE
**Feedback-Oriented Recursive Generation & Evaluation**

> **FORGE is a self-verifying AI software engineer that does not stop when code compiles; it continuously gathers evidence that the requested behavior is actually correct.**

---

# 2. Hackathon Constraints Satisfied
- [x] Root `Makefile` with `make setup`, `make run`, `make test`, `make clean`
- [x] Reads `AI_API_KEY` at runtime
- [x] Zero committed credentials
- [x] Reproducible setup
- [x] Autonomous evaluation mode

---

# 3. Target Architecture
```text
Task -> Understand -> Map Repo -> Plan -> Baseline Checkpoint -> Builder -> Test Selection -> Diagnoser -> Critic -> Evidence-Backed Done
```

---

# 4. Core Modules
- `forge/state/`: Persistent state machine & JSONL telemetry
- `forge/intelligence/`: AST symbol extraction, dependency graph, requirement mapper, context engine
- `forge/planner/`: Structured step generator and risk engine
- `forge/builder/`: Code editor, syntax validator, tool harness
- `forge/recovery/`: Checkpoints, atomic rollback, strategy shifter
- `forge/verification/`: Impact test selector, test runner, failure clustering, diagnoser, verifier, critic
- `forge/memory/`: Repository memory & failure lessons
- `forge/ui/`: Rich TUI dashboard & replay engine
- `forge/orchestrator/`: Deterministic state machine controller
- `forge/benchmark/`: Comparative benchmark and ablation studies
