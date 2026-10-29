"""Lesson 5 - Hooks: your code inside the agent's loop.

Concept: hooks=[<HookProvider>]  (strands.hooks.HookProvider, HookRegistry)

THE WALL: Lesson 4 rewired *output* - you watched events stream out. But the
agent's decisions are still a black box: which tool call was attempted, how
long it took, how many tokens the whole loop spent, whether the model
re-called itself. Printing from inside a tool tells you about the tool, not
about the agent's *loop*. And worse: you cannot accumulate anything across
turns without smuggling globals around.

THE IDEA: the agent emits a small set of fixed lifecycle events: an invocation
starts, the model is called, a tool is called, the model answers, call ends.
Hooks are just callbacks that register FOR one lifecycle event. A *HookProvider*
is a normal object with `register_hooks(registry)` - the agent calls it once at
construction; you add your callbacks to the registry. Manual path without a
provider: `agent.add_hook(callback, BeforeModelCallEvent)`.

The event vocabulary mirrors reality (verified against 1.57.0):
  BeforeInvocationEvent  - agent() entered. Has .agent, .invocation_state.
  BeforeModelCallEvent   - about to call the model. Also .projected_input_tokens.
  AfterModelCallEvent    - model returned: .stop_response (may be None), .exception.
  BeforeToolCallEvent    - model picked a tool: .tool_use, .selected_tool.
  AfterToolCallEvent     - tool ran: .tool_use, .result (ToolResult dict),
                           .duration (seconds), .exception.

WHAT'S GENUINELY NEW: this is not a print feature. A hook is a place where
YOUR code runs inside the loop with a back-pointer to the agent and the real
event data - it is the seed of instrumentation (Lesson 11's OpenTelemetry),
of guardrails (Lesson 7's interventions wrap the same events), and of
cross-cutting behavior that tools cannot express.

MICROTASKS:
  5.1 Run block 5.1: a minimal hook function via agent.add_hook that prints
      one line per model call. One new concept, no class.
  5.2 Read AuditTrail below: THE pattern - a class holding state, registered
      via hooks=[AuditTrail()]. Why a class? The Counter lives between events.
  5.3 Run block 5.3: one question that needs a tool + one that does not.
      Watch the audit log order - there is exactly one correct order, and you
      will recognize the loop you saw streaming in Lesson 4.
  5.4 Run block 5.4: the same agent WITHOUT hooks, and diff what you lost:
      no durations, no usage, no failures - just the final text.

LIBRARIES: strands-agents==1.57.0 (no new package).
"""

import time
from collections import Counter

from strands import Agent
from strands.hooks import AfterModelCallEvent, AfterToolCallEvent, BeforeInvocationEvent
from strands.hooks import BeforeModelCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from strands_tools import current_time  # old friend from Lesson 2

from Models.llmModels import model

CATALOG = """
- Wireless Mouse, Logitech - 799            (SKU-MSE-LOG-01)
- USB-C Cable (1m), Anker - 349            (SKU-CBL-ANK-01)
- Bluetooth Earbuds, boAt - 1499           (SKU-EAR-BOA-01)
- 27-inch Monitor, Dell - 15999            (SKU-MON-27-DEL)
- Mechanical Keyboard, Redragon - 2499     (SKU-KEY-RED-01)
- Power Bank 20000mAh, Mi - 1799           (SKU-PWR-20K-MI)
- External SSD 1TB, Samsung - 6499         (SKU-EXT-SSD-1TB)
- Smartwatch, Noise - 2999                 (SKU-SWT-NOI-01)
- Laptop Stand, AmazonBasics - 899         (SKU-STD-AMZ-01)
- Webcam 1080p, Logitech - 3499            (SKU-CAM-LOG-01)
"""


# ---------------------------------------------------------------------------
# 5.1 - a hook function, no class. Registered per-event with agent.add_hook.
# ---------------------------------------------------------------------------
def log_model_call(event: BeforeModelCallEvent) -> None:
    print(f"  [hook] model about to answer ({event.projected_input_tokens} input tokens projected)")


# ---------------------------------------------------------------------------
# 5.2 - the AuditTrail provider: one object, five events, shared state.
# ---------------------------------------------------------------------------
class AuditTrail(HookProvider):
    """Print every lifecycle event of one invocation, in real order boringly."""

    def __init__(self) -> None:
        self.tool_calls: Counter[str] = Counter()
        self.failures: int = 0

    def register_hooks(self, registry: HookRegistry) -> None:
        # each callback handles ONE event kind; type hints decide inference
        registry.add_callback(BeforeInvocationEvent, self._on_invocation_start)
        registry.add_callback(BeforeModelCallEvent, self._on_model_call)
        registry.add_callback(AfterModelCallEvent, self._on_model_done)
        registry.add_callback(BeforeToolCallEvent, self._on_tool_call)
        registry.add_callback(AfterToolCallEvent, self._on_tool_done)

    # -- callbacks ---------------------------------------------------------
    def _on_invocation_start(self, event: BeforeInvocationEvent) -> None:
        print(f"  [audit] invocation begins at {time.strftime('%H:%M:%S')}")

    def _on_model_call(self, event: BeforeModelCallEvent) -> None:
        print("  [audit] -> model called")

    def _on_model_done(self, event: AfterModelCallEvent) -> None:
        if event.exception:
            self.failures += 1
            print(f"  [audit] <- model ERROR: {event.exception!r}")
        else:
            print("  [audit] <- model answered")

    def _on_tool_call(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use.get("name", "?")
        self.tool_calls[name] += 1
        print(f"  [audit] -> tool {name}({event.tool_use.get('input')})")

    def _on_tool_done(self, event: AfterToolCallEvent) -> None:
        status = event.result.get("status") if isinstance(event.result, dict) else "?"
        secs = f"{event.duration:.2f}s" if event.duration else "?"
        print(f"  [audit] <- tool {event.tool_use.get('name')} [{status}] in {secs}")


def ask(agent: Agent, question: str) -> None:
    print(f"you: {question}")
    result = agent(question)
    print(f"shopbuddy: {result}")  # the final text; the audit lines went above


def main() -> None:
    SYSTEM = f"""You are a support assistant for PixelMart.

Products and prices (INR):
{CATALOG}

Stock, orders live in tools; the current date comes from a tool as well.
Never guess. If no tool can answer, say so plainly.
Answer in 1-3 friendly sentences."""

    # 5.1 - the one-liner hook, registered manually on the live agent.
    print("--- 5.1  add_hook: bare function, single event kind ---")
    simple = Agent(
        model=model, system_prompt=SYSTEM, tools=[current_time], callback_handler=None
    )
    simple.add_hook(log_model_call, BeforeModelCallEvent)
    ask(simple, "What is today's date?")

    # 5.2 + 5.3 - the provider, with shared state and a real tool call.
    audit = AuditTrail()
    audited = Agent(
        model=model, system_prompt=SYSTEM, tools=[current_time], callback_handler=None, hooks=[audit]
    )
    print("\n--- 5.3  AuditTrail over a no-tool question ---")
    ask(audited, "How much is the smartwatch?")
    print("\n--- 5.3  AuditTrail over a tool question ---")
    ask(audited, "Is today a working day for delivery estimates?")

    # the state a provider keeps is the whole point: aggregate after runs
    print("\n--- 5.3  state that survived between the invocations ---")
    print(f"tool usage across both questions: {dict(audit.tool_calls)}")
    print(f"model failures so far: {audit.failures}")

    # 5.4 - the without-hooks version: the differences are all negative.
    plain = Agent(
        model=model, system_prompt=SYSTEM, tools=[current_time], callback_handler=None
    )
    print("\n--- 5.4  same two questions, no hooks ---")
    ask(plain, "How much is the smartwatch?")
    ask(plain, "Is today a working day for delivery estimates?")
    print("(no durations, no usage, no start marker - invisible unless asked)")


if __name__ == "__main__":
    main()
