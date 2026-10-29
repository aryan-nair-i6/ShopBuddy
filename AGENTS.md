# ShopBuddy — AGENTS.md

## What this repo is

A **learning project**, not a product. The learner is building **ShopBuddy**, a customer-support
agent for a fictional store ("PixelMart"), by adding **exactly one Strands concept per lesson**
to the *same* agent. Do not restructure, "clean up", or refactor across lessons — each lesson
must build on the previous file.

The learner is **new to AWS Strands** (knows theory up to plugins/skills/steering). Every
explanation must be **from the ground up, plain language, no assumed jargon**.

## Lesson shape (required for every lesson)

Each lesson must contain, in this order:

1. **The wall** — the concrete ShopBuddy problem at this stage *without* the new concept.
2. **The idea** — explained from zero, with an analogy if it helps.
3. **What's genuinely new** — why this is not "more code".
4. **Microtasks** — small, individually checkable steps.
5. **Libraries** — exact package(s) + version, and how to install.

Keep microtasks tiny. The learner runs one at a time and reports back.

## Environment (verified on this machine)

- Windows, PowerShell. Python **3.13.4**. Venv at repo root: `.venv\` (gitignored).
- Activate first: `.venv\Scripts\Activate.ps1`
- `strands-agents==1.57.0`, `strands-agents-tools==0.8.9`, `mcp==2.1.1`, `openai==3.19.2`,
  `boto3==1.43.102`, `python-dotenv==1.2.3`. `pywin32==312` is pinned → this requirements
  file is **Windows-only**; do not "fix" it for Linux.
- Model is **OpenAI `gpt-4o-mini`**, not Bedrock: `Models/llmModels.py` builds
  `OpenAIModel(model_id="gpt-4o-mini")` and calls `load_dotenv()` **at import time**.
  `.env` holds only `OPENAI_API_KEY` and is gitignored.

## How to run things

```powershell
cd C:\Users\aryan\Desktop\ShopBuddy
.\.venv\Scripts\Activate.ps1
python lesson_01_bare_agent.py
```

No `PYTHONPATH` is needed. Run lesson files **from the repo root** so that `Models` is
importable as a package.

There is **no `strands` CLI installed** (`strands-agents-cli` is not a real PyPI package).
So `strands run`, `strands evals`, `strands tools` **do not exist here**. Never tell the
learner to run them.

## Gotchas (all verified — do not "correct" these, they are real)

1. **`Models\` is a package and must be imported as one.** `Models\__init__.py` exists, so the
   correct import from a lesson file at the repo root is:
   ```python
   from Models.llmModels import model
   ```
   Do **not** "fix" this back to `import llmModels` — that form only resolves with
   `$env:PYTHONPATH=Models` exported, and fails outright otherwise. There is no
   `Models` entry in `requirements.txt`; it is a first-party local package.
   A historical top-level `test.py` used the broken `import llmModels` form and has been
   deleted. Do not reintroduce it.
2. **`requirements.txt` is UTF-16 LE with a BOM.** `pip install -r` handles it, but the
   `read`/`edit` tools report it as a **binary file**. Read it with
   `Get-Content requirements.txt -Encoding UTF8`. Do not rewrite it as UTF-8 casually — that
   diffs the whole file.
3. **`strands_tools` 0.8.9 has no `file_editor` and no `web_fetch`.** It is a flat
   *module-per-tool* package. `strands_tools/__init__.py` deliberately exports nothing at
   runtime. Correct patterns:
   - `from strands_tools import calculator` → binds the **module**, not the tool. Passing the
     module in `tools=[...]` is fine (registry scans it), but `calculator(...)` will not call a tool.
   - `file_editor` / `web_fetch` exist **only** via `from strands.vended_tools import file_editor, web_fetch`
     (still working, no deprecation warning in 1.57.0). This is what `test.py` uses.
4. **Two packages both provide a `dotenv` module**: `python-dotenv==1.2.3` (correct) and a stray
   `dotenv==0.9.9`. `Models/llmModels.py` does `from dotenv import load_dotenv`, which currently
   resolves and works — but it is ambiguous. Prefer the `python-dotenv` spelling in new code.
5. **No `.env.example` exists**, even though `.gitignore` un-ignores it. Create it when touching
   env setup.
6. `report.md` is **gitignored as generated agent output** — that is intentional, not an oversight.
7. **`strands_tools.calculator` is deprecated** in `0.8.9` and becomes a hard error in `0.9.0`.
   `lesson_02_tools.py` defines its own `calculate` tool instead. Do not reintroduce `calculator`.
8. **Tool-trace block shapes** (verified by inspecting `agent.messages`): a tool call is
   `{"toolUse": {"toolUseId", "name", "input"}}` — `toolUse` is a **single dict, not a list** —
   and the reply is `{"toolResult": {"toolUseId", "status", "content": [{"text": ...}]}}`.
   `AgentResult` has no `.message` or `.metrics`; read the trace from `agent.messages`.
   `lesson_02_tools.py::ask()` is a working reference implementation.
   *(correction 2026-10-30, re-verified on the installed 1.57.0: `AgentResult` now has
   `dataclass` fields `stop_reason, message, metrics, state, interrupts, structured_output,
   checkpoint` — the trace-from-`agent.messages` advice is still the practical one, but the
   "no .message/.metrics" claim is stale.)*

## Curriculum roadmap

Concepts map onto real `Agent.__init__` parameters (verified for 1.57.0). Use these as the
"what's new" anchor for each lesson.

| # | Lesson | Strands surface | Extra library |
|---|--------|-----------------|---------------|
| 1 | Bare agent | `Agent(model=, system_prompt=)` | `strands-agents` |
| 2 | Tools | `@tool`, `tools=[...]` (registry accepts functions, modules, `AgentTool`, nested iterables) | `strands-agents` |
| 3 | Tools via MCP | `strands_tools.mcp_client`, `MCPClient` | `mcp==2.1.1`; `strands-agents-mcp-server==0.3.0` to test against a real server |
| 4 | Streaming / callbacks | `callback_handler=`, `strands.types.streaming` | `strands-agents` |
| 5 | Hooks | `hooks=`, `strands.hooks` (`HookProvider`, `BeforeModelCallEvent`, `AfterToolCallEvent`, `HookOrder`, …) | `strands-agents` |
| 6 | Plugins & skills | `plugins=`, `load_tools_from_directory=`, `Plugin` (`.tools`, `.hooks`, `.init_agent`), `Skill(name, description, instructions, path, allowed_tools)`, `AgentSkills`, `strands.vended_plugins.skills` | `strands-agents` |
| 7 | Steering | `interrupt`, `InterventionHandler`, `interventions=` | `strands-agents` |
| 8 | Persistent memory | `session_manager=` (`FileSessionManager`, `S3SessionManager`, `SnapshotSessionManager`), `memory_manager=`, `strands.memory` (`MemoryStore`, `MemoryManager`, `Extractor`, `MemoryEntry`) | `strands-agents` (+ `boto3` for S3) |
| 9 | Multiagent | `strands.multiagent` (`GraphBuilder`, `EdgeCondition`, `Swarm`, `MultiAgentBase`, `Status`), `LocalAgent`, `AgentBase`, `MultiAgentPlugin`; helpers `strands_tools.agent_graph`, `strands_tools.swarm`, `strands_tools.use_agent`, `strands_tools.handoff_to_user` | `strands-agents` |
| 10 | Evaluating | **No `strands-agents-eval` on PyPI** (it does not exist) and no CLI. Build evals yourself with `pytest` over recorded/replayed results, or `strands-evals==0.0.1` | `pytest`, `strands-evals` |
| 11 | Deploy to cloud | `strands.telemetry` (OTel), `S3SessionManager`, containerize, Bedrock for AWS-native | `boto3`, `opentelemetry-*` |

### Notes for specific lessons

- **Lesson 3 (MCP)**: explain the client/server split from zero. Use
  `strands-agents-mcp-server` as a *known-good* local server so the learner sees a real
  handshake before touching a remote one.
- **Lesson 8 (memory)**: separate the two ideas clearly — *session* = replayable message
  history; *memory* = extracted, searchable facts. Beginners conflate these constantly.
- **Lesson 9 (multiagent)**: teach the three patterns as distinct answers to distinct problems —
  **agent-as-tool** (a specialist stays hidden, `use_agent`), **graph** (fixed, hand-authored
  control flow, `GraphBuilder`), **swarm** (dynamic handoff, no fixed order, `Swarm`).
  Do not present them as interchangeable.
- **Lesson 10 (eval)**: set expectations that there is **no official Strands eval package**
  here. Judge on task success, tool-choice correctness, and latency/cost.
- **Lesson 11 (deploy)**: note the repo currently runs on **OpenAI**, so the AWS/Bedrock step is
  a deliberate migration, not a default.

## Layout convention

```
Models/__init__.py       # makes Models a real package - required
Models/llmModels.py      # single shared `model` object (module-level, loads .env)
lesson_XX_<slug>.py      # one file per lesson at repo root
```

Import the model as `from Models.llmModels import model`.

**The canonical PixelMart product catalog lives in `lesson_XX_*.py` (currently
`lesson_01_bare_agent.py`).** No other file is authoritative. An older `test.py` carried a
second, conflicting catalog as vended-tool demo data; it has been deleted, so there is exactly
one source of truth. If a new file introduces different products or prices, that is a bug.

Each lesson file is **standalone-runnable** and must not import from other lesson files —
copy forward instead. The learner runs them one at a time and diffs the growth.

## Rules for agents working in this repo

- Do not add dependencies to `requirements.txt` without stating the version and why.
- Do not swap OpenAI for Bedrock unless the lesson is explicitly about deploying to AWS.
- Do not introduce pytest/ruff/mypy/CI config until the matching lesson — the learner asked for
  concepts in a specific order.
- Preserve the "one new concept per lesson" rule even if it looks like duplication.
- If you touch `.env`, never print or echo secret values — reference key names only.
