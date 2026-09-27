# ShopBuddy — learning AWS Strands by building one agent, one concept at a time

This repo is a **learning project**, not a product. I am building **ShopBuddy**, a customer-support
agent for a fictional electronics store ("PixelMart"), by adding **exactly one Strands concept per
lesson** to the *same* agent.

The constraint is the point. Every lesson file is a complete, runnable agent, and the only thing that
changes between them is the single new idea. Nothing gets refactored, abstracted, or "cleaned up"
along the way, so the growth from lesson to lesson stays visible and diffable.

I came in knowing Strands *theory* — up to plugins, skills, and steering — and roughly nothing about
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

`requirements.txt` pins `pywin32==312`, so **this file is Windows-only** — that is intentional, not a
mistake to fix.

### Environment variables

`Models/llmModels.py` calls `load_dotenv()` at import time, so `.env` must exist in the repo root
before anything runs.

```powershell
# create .env with your key (key name only below, never the value)
OPENAI_API_KEY=sk-...
```

`.env` is gitignored. Only the key *name* is ever referenced in this repo.

### Running a lesson

```powershell
cd C:\Users\aryan\Desktop\ShopBuddy
.\.venv\Scripts\Activate.ps1
python lesson_01_bare_agent.py
```

No `PYTHONPATH` needed — just run from the repo root so `Models` is importable as a package:

```python
from Models.llmModels import model
```

### The model

This repo runs on **OpenAI `gpt-4o-mini`**, not Bedrock:

```python
model = OpenAIModel(model_id="gpt-4o-mini", client_args={"api_key": os.getenv("OPENAI_API_KEY")})
```

`gpt-4o-mini` keeps the iteration loop fast and the API bill small, which matters for a repo built
around running the same script fifty times. Migrating to Bedrock is a deliberate, explicit step in
the deployment lesson — not a default.

---

## Layout

```
Models/__init__.py          # makes Models a real package - required for the import above
Models/llmModels.py         # the single shared `model` object (module-level, loads .env)
lesson_01_bare_agent.py     # Agent(model=, system_prompt=)
lesson_02_tools.py          # @tool decorator + tools=[...]
```

`Models/` is first-party local code, not a dependency — it has no entry in `requirements.txt`.

The **canonical PixelMart product catalog** lives in the lesson files. There is exactly one source
of truth; a second copy in a scratch file would be a bug, not a convenience.

---

## The lessons

### Lesson 1 — the bare agent ✅
`lesson_01_bare_agent.py` · `Agent(model=, system_prompt=)`

A working agent with zero tools. It can quote prices from the frozen catalog, and it will happily
tell you so. The lesson walks four questions, and the last one is the point:

- A follow-up question is answered without resending the first one — the agent keeps the
  conversation in `agent.messages`.
- "Is the Samsung SSD **in stock**?" — the product *is* in the prompt, so the model *wants* to
  answer, but stock was never given to it. It should refuse.

That refusal is not a bug. That refusal is the wall for Lesson 2.

### Lesson 2 — tools ✅
`lesson_02_tools.py` · `@tool`, `tools=[...]`

The catalog stops being text in a prompt and becomes live code. The agent now closes the gap it hit
in 1.5.

The mental model, in the file's own words: **a tool is an ordinary Python function that also gets
described to the model.** Strands reads the name, type hints, and docstring, and builds a JSON menu
entry. The model has never seen your code — it picks a tool and invents arguments using *only* that
description. Then it emits a *request*; Strands runs the real function and loops the model again.

So: **your docstring is not documentation, it is the model's instruction manual.** The lesson proves
this empirically by registering the same working lookup twice — once with a good docstring, once
with `"""does stuff"""` — and watching the vague one fumble. Same code, same answer, worse
description, worse agent.

Microtasks walk from a plain undecorated function, to one `@tool`, to a deliberately bad one, to two
tools (the model routes between them with **no dispatch code anywhere**), to a hand-written
`calculate` with an AST allowlist, to a prebuilt tool from `strands_tools`.

It also prints the tool trace after every question, because **invented tool arguments are the most
common tool bug and are completely invisible unless you print them.**

### Lessons 3-11 — the roadmap

| # | Lesson | Strands surface |
|---|--------|-----------------|
| 3 | Tools via MCP | `strands_tools.mcp_client`, `MCPClient` |
| 4 | Streaming / callbacks | `callback_handler=`, `strands.types.streaming` |
| 5 | Hooks | `hooks=`, `strands.hooks` (`HookProvider`, `BeforeModelCallEvent`, …) |
| 6 | Plugins & skills | `plugins=`, `load_tools_from_directory=`, `Plugin`, `Skill`, `AgentSkills` |
| 7 | Steering | `interrupt`, `InterventionHandler`, `interventions=` |
| 8 | Persistent memory | `session_manager=`, `memory_manager=`, `strands.memory` |
| 9 | Multiagent | `GraphBuilder`, `Swarm`, `use_agent`, `handoff_to_user` |
| 10 | Evaluating | build evals with `pytest` (there is no official Strands eval package) |
| 11 | Deploy to cloud | `strands.telemetry` (OTel), `S3SessionManager`, containerize, Bedrock |

The order is not arbitrary. Memory comes after steering because a session you can interrupt is
worth more than one you cannot. Multiagent comes last of the architecture lessons because it is the
most expensive to get wrong.

---

## Notes learned the hard way

Things that cost real time and are easy to trip over again:

- **`strands-agents-cli` does not exist on PyPI.** There is no `strands run`, `strands evals`, or
  `strands tools` command in this environment. Any lesson that tells you to run one is wrong.
- **`strands_tools` is a module-per-tool package.** `from strands_tools import calculator` binds a
  *module*, not a tool. Passing a module inside `tools=[...]` is fine — the registry scans it — but
  `calculator(...)` will not call anything. And `file_editor` / `web_fetch` live in
  `strands.vended_tools`, not `strands_tools`.
- **`strands_tools.calculator` is deprecated** and becomes a hard error in 0.9.0, which is why
  Lesson 2 writes its own `calculate`.
- **Two packages provide a `dotenv` module** (`python-dotenv` and a stray `dotenv==0.9.9`).
  It currently resolves, but the intent is `python-dotenv`.
- **`AgentResult` has no `.message` or `.metrics`.** Read the trace from `agent.messages`: a call is
  `{"toolUse": {"toolUseId", "name", "input"}}` (a single dict, not a list) and the reply is
  `{"toolResult": {"toolUseId", "status", "content": [{"text": ...}]}}`.
- **`Models` must be imported as a package.** `import llmModels` only works if you export
  `PYTHONPATH=Models`, and fails outright otherwise. Don't "fix" it back.

---

## Conventions this repo follows

- One new Strands concept per lesson, even when it looks like duplication.
- Lesson files are standalone and never import from each other — code is copied forward, not shared,
  so each file can be read and diffed in isolation.
- No linters, formatters, or CI config until the lesson that motivates them. Learning the framework
  first is the point; tidying the repo is not.
- No new dependency without a stated version and a reason.
- Never print or echo secret values — reference key *names* only.

---

## Why an agent at all?

The point of this repo is not ShopBuddy. It is that **the behaviour of an AI agent is decided almost
entirely by what you give it access to, not by how clever the prompt is.**

Lesson 1 can quote a price from memory and will refuse a stock question with perfect manners.
Lesson 2 answers the same stock question correctly — not because it got smarter, but because it was
given a way to look the answer up. Every lesson after that adds one more such affordance: tools,
other systems (MCP), observability, guardrails, memory, teammates.

If a lesson's output ever surprises you, the tool trace is printed right there underneath it. That
is the habit worth taking away from this repo — not the catalog.
