# ShopBuddy — learning AWS Strands by building one agent, one concept at a time

This repo is a **learning project**, not a product. I built **ShopBuddy**, a customer-support
agent for a fictional electronics store ("PixelMart"), by adding **exactly one Strands concept per
lesson** to the *same* agent. Eleven lessons, eleven files, one growing agent.

The constraint is the point. Every lesson file is a complete, runnable agent, and the only thing
that changes between them is the single new idea. Nothing gets refactored, abstracted, or "cleaned
up" along the way, so the growth from lesson to lesson stays visible and diffable.

I came in knowing Strands *theory* — up to plugins, skills and steering — and roughly nothing about
running one. So the lessons are written from the ground up: plain language, no assumed jargon, and
an explicit statement of what is *actually* new rather than just "more code".

---

## What makes this different from a tutorial

Most agent tutorials hand you a finished app and walk backwards. This goes the other way: start
with an agent that genuinely cannot do its job, feel the wall, then add the one thing that breaks
through it. Every lesson answers four questions:

1. **The wall** — the concrete ShopBuddy problem at this stage, *without* the new concept.
2. **The idea** — explained from zero, with an analogy where it helps.
3. **What's genuinely new** — why this is not just more code.
4. **Microtasks** — tiny, individually checkable steps.

---

## Setup

Windows / PowerShell. Python **3.13.4**. Virtualenv lives at the repo root as `.venv\`.

```powershell
cd C:\Users\aryan\Desktop\ShopBuddy
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt` pins `pywin32==312`, so **that file is Windows-only** — intentional, not a
mistake to fix (the Dockerfile in Lesson 11 installs the Linux-safe subset instead). Editing it
does not help: it is UTF-16 LE with a BOM; `pip install -r` handles that, text editors might not.

### Environment variables

`Models/llmModels.py` calls `load_dotenv()` at import time, so `.env` must exist in the repo root:

```powershell
Copy-Item .env.example .env   # then fill in your key
# OPENAI_API_KEY=sk-...  (only the key NAME is ever referenced in this repo)
```

### Running a lesson

```powershell
cd C:\Users\aryan\Desktop\ShopBuddy
.\.venv\Scripts\Activate.ps1
python lesson_01_bare_agent.py
```

No `PYTHONPATH` needed — just run from the repo root so `Models` imports as a package:

```python
from Models.llmModels import model
```

### The model

Runs on **OpenAI `gpt-4o-mini`**, not Bedrock:

```python
model = OpenAIModel(model_id="gpt-4o-mini", client_args={"api_key": os.getenv("OPENAI_API_KEY")})
```

`gpt-4o-mini` keeps the iteration loop fast and the API bill small, which matters for a repo built
around running the same script fifty times. Migrating to Bedrock is a deliberate, explicit step in
Lesson 11 — not a default.

---

## Layout

```
Models/__init__.py             # makes Models a real package - required for the import above
Models/llmModels.py            # the single shared `model` object (module-level, loads .env)
lesson_01_bare_agent.py        # Agent(model=, system_prompt=)
lesson_02_tools.py             # @tool + tools=[...]
lesson_03_mcp_server.py        # the PixelMart POLICY server (MCPServer)
lesson_03_mcp_tools.py         # MCPClient - tools from another process
lesson_04_streaming.py         # callback_handler= + agent.stream_async()
lesson_05_hooks.py             # hooks=[<HookProvider>]
lesson_06_plugins_skills.py    # plugins=[<Plugin>] + Skill/AgentSkills
lesson_07_steering.py          # interventions=[<InterventionHandler>] + interrupts
lesson_08_memory.py            # session_manager= (transcripts) memory_manager= (facts)
lesson_09_multiagent.py        # as_tool() / GraphBuilder / Swarm
lesson_10_bare_evals.py        # the grader harness, covers off
evals/test_agent_evals.py      # the same cases under pytest (pytest evals/)
lesson_11_deploy.py            # OTel telemetry + the S3/Bedrock/container checklist
Dockerfile                     # Linux-safe containerization
```

The **canonical PixelMart catalog** lives in the lesson files. There is exactly one source of
truth, copied forward per lesson (lessons never import from each other — built to be diffable).

---

## The lessons

### Lesson 1 — the bare agent ✅
`Agent(model=, system_prompt=)`. Quotes perfect prices, refuses a stock question with perfect
manners — the refusal IS the wall for Lesson 2.

### Lesson 2 — tools ✅
`@tool`, `tools=[...]`. The catalog stops being prompt text and becomes live code. The central
insight, provable in one run: **your docstring is not documentation — it is the model's
instruction manual.** The lesson registers the same lookup twice (good docstring vs
`"""does stuff"""`) and watches the vague one fumble. Invented tool arguments — the most common
tool bug — are printed via the `agent.messages` trace, because they are invisible otherwise.

### Lesson 3 — tools from another process (MCP) ✅
`MCPClient` + a real local server (`lesson_03_mcp_server.py`, written with mcp 2.1.1's
`MCPServer` — **v2 renamed FastMCP → MCPServer**). Same loop, same menu interface; only the
source of the tool list changed. Local tools and MCP tools mix in one agent with zero
dispatch code.

### Lesson 4 — streaming ✅
`callback_handler=` and `agent.stream_async(...)`. The event census block makes "streaming"
concrete: it is a list of typed events in order. Verified trap: the two consumption paths deliver
different payload shapes (typed events vs. legacy dicts), so the lesson ships one shape-agnostic
helper — printing `.delta.text` on a dict otherwise prints nothing, silently.

### Lesson 5 — hooks ✅
`hooks=[<HookProvider>]`. The AuditTrail prints the whole lifecycle in order — invocation →
model → tool → model — and the provider object is where aggregate state lives (tool counters,
failures). This is the seed of Lesson 11's telemetry.

### Lesson 6 — plugins & skills ✅
`plugins=[<Plugin>]` + `Skill`/`AgentSkills`. The plugin bundles tools + hooks under one auto-
discovered name; the skill is *know-how*, not code (name + description + instructions). The
lesson demonstrates the split empirically: same agent, angry customer turn, skill instructions
shape the reply only when the description matches the task.

### Lesson 7 — steering ✅
`interventions=[<InterventionHandler>]`. Same lifecycle events as hooks, but every method returns
a verdict: `Proceed` / `Guide` / `Deny` / `Confirm`. `Confirm` raises a real human-in-the-loop
**interrupt** — the agent call returns early with pending interrupts, the human answers, and
resuming replays the parked tool *without calling the model again*. Verified: `InterventionHandler`
is an ABC and subclasses MUST provide a `name`.

### Lesson 8 — persistent memory ✅
`session_manager=` and `memory_manager=` — the split beginners always conflate. A **session** is
a replayable transcript (`FileSessionManager`); a new agent with the same id continues the chat
word-for-word. **Memory** is extracted facts (`MemoryManager` + `FileMemoryStore`); a brand-new
session still answers "what do you know about me" from injected facts. 8.2 replays words; 8.5
reuses a fact.

### Lesson 9 — multiagent ✅
Three patterns, three different problems, deliberately not presented as interchangeable:
**agent-as-tool** (`specialist.as_tool()`) hides a specialist behind one menu entry;
**GraphBuilder** fixes control flow in authored edges with Python edge conditions over
`GraphState`; **Swarm** gives agents dynamic handoff with no fixed order. The lesson runs the same
questions through graph AND swarm so you can diff fixed vs. emergent routing.

### Lesson 10 — evaluating ✅
No official Strands eval package exists on PyPI, so the grader is ~60 lines here with the covers
off: cases + graders + a run loop, judging **task success** (string-contains), **tool choice**
(first `toolUse` block in `agent.messages` + argument sanity) and **latency** (a budget gate).
`evals/test_agent_evals.py` wraps the same graders as pytest for CI (`pytest evals/`; needs key
and makes live calls).

### Lesson 11 — deploy ✅
`strands.telemetry` + OTel: register providers *before* Agents exist, then a traced turn emits to
the `ConsoleSpanExporter` — the same payload an OTLP backend receives. The migration checklist is
in the lesson itself: sessions to `S3SessionManager`, model to `BedrockModel`, containerize with
the Linux-safe `Dockerfile`.

---

## Notes learned the hard way (all verified against 1.57.0)

- **`strands-agents-cli` does not exist on PyPI.** There is no `strands` CLI here; any tutorial
  step that runs `strands run/evals/tools` is wrong.
- **`strands_tools` is a module-per-tool package.** `from strands_tools import calculator` binds a
  *module*; passing a module in `tools=[...]` is fine (the registry scans it), calling it is not.
  `file_editor` / `web_fetch` live in `strands.vended_tools`, and `strands_tools.calculator` is
  deprecated (hard error in 0.9.0) — hence the hand-written `calculate` in Lesson 2.
- **mcp 2.x renamed `FastMCP` → `MCPServer`** (`mcp.server.mcpserver`). `mcp.server.fastmcp`
  raises `ModuleNotFoundError` on `mcp==2.1.1`.
- **A running `MCPClient` cannot be passed as `tools=[mcp_client]` itself** (the registry would
  re-`start()` it). Inside the `with` block, pass the listed tools:
  `tools=[*mcp_client.list_tools_sync()]`. Listed tools are `MCPAgentTool`s — their name lives on
  `.tool_name`, not `.name`.
- **`stream_async` yields dicts; callback handlers get typed events** (both verified from source).
  One helper handles both shapes.
- **`InterventionHandler` is an ABC** — a concrete gate must define `name`. `Confirm` returns a
  pending interrupt; resume by setting `interrupt.response` and invoking the agent again.
- **`Agent(...)` params verified in 1.57.0** (the roadmap's anchor): `callback_handler`,
  `hooks`, `plugins`, `interventions`, `session_manager`, `memory_manager`,
  `trace_attributes`, `structured_output_model` — all real, all exercised across the lessons.
- **AgentResult exposes `.messages`-side data differently depending on the surface**: the tool
  trace comes from `agent.messages` (a `toolUse` block is a single dict, not a list; the reply is
  a `toolResult` block), while `AgentResult` itself carries `stop_reason`, `message`, `metrics`,
  `structured_output`, `interrupts`.
- **OpenTelemetry providers must be registered before Agents emit** and `TracerProvider` takes
  processors via `add_span_processor(...)`, not an init kwarg.

---

## Conventions this repo follows

- One new Strands concept per lesson, even when it looks like duplication.
- Lesson files are standalone and never import from each other — code is copied forward, not
  shared, so each file can be read and diffed in isolation.
- No linters, formatters, or CI config until the lesson that motivates them.
- No new dependency without a stated version and a reason. (`pytest==9.2.0` was added with Lesson
  10 — the only added dependency in this push.)
- Never print or echo secret values — reference key *names* only.
- `.env.example` exists with placeholder names only; `.env` is gitignored.

---

## Why an agent at all

The point of this repo is not ShopBuddy. It is that **the behaviour of an AI agent is decided
almost entirely by what you give it access to, not by how clever the prompt is.**

Lesson 1 can quote a price from memory and refuses a stock question with perfect manners.
Lesson 2 answers the same question correctly — not because it got smarter, but because it was
given lookup access. Every later lesson adds one more such affordance: other systems (MCP),
visible events (streaming), instrumentation (hooks), reusable bundles (plugins), judgment gates
(steering), durable understanding (memory), teammates (multiagent), a mirror (evals), a shipping
path (deploy).

If a lesson's output ever surprises you, the tool trace is printed right there in Lesson 2's
`ask()`, and Lesson 10's graders make the same trace assertable. That habit — instrument, then
assert — is the actual takeaway of the repo, not the catalog.
