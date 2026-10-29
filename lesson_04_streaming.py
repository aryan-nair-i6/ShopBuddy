"""Lesson 4 - Streaming / callbacks: watching the reply while it is still written.

Concept: callback_handler=<function>  +  agent.stream_async(...)

THE WALL: Lessons 1-3 used `agent(question)` and printed a finished string.
`result` only exists when the whole turn is done: model wrote everything, tool
calls finished, final text assembled. For support chat that is a bad user
experience - the customer stares at a blank bubble for seconds. It is also a
blind spot for YOU: you never saw HOW a turn unfolds, or that a tool call
produces its own visible pause inside one reply.

THE IDEA: tokens arrive from the API one small piece at a time; the library
had been collecting them for you. A *callback handler* is a function called
once per event, in order, as the turn runs. There are two consuming styles:
  (a) pass a function as callback_handler= (sync, registered by construction);
  (b) `async for event in agent.stream_async(...)` - the same turn as an
      explicit async loop you own, which is what a web app would wire.
Lesson 1 quietly passed callback_handler=None to turn off the DEFAULT printer;
this lesson turns the same switch ON, aimed at your own function.

VERIFIED SHAPES (1.57.0, from source): the vocabulary lives in
`strands.types.streaming` (MessageStartEvent, ContentBlockDeltaEvent,
ContentBlockStopEvent, MessageStopEvent, MetadataEvent, ...) BUT the two
consumption paths differ in payload type - async callback handlers may see
typed events while `stream_async` yields plain dicts (legacy keys: "data" for
text, "current_tool_use" for tool activity). Printing `.delta.text` on a
dict prints NOTHING, silently - the shape-agnostic helper below armor-plates
against exactly that bug class by handling both shapes.

MICROTASKS:
  4.1 Run block 4.1: count one turn's events by type name. The event list IS
      what "streaming" concretely is - this census makes it visible.
  4.2 Run block 4.2: print deltas as they arrive (end="", flush). Run it
      directly after Lesson 2's silent agent() calls - feel the difference.
  4.3 Run block 4.3: stream_async - the same turn through a loop YOU own.
      Note the dict-vs-typed difference proven by the helper.
  4.4 Run block 4.4: latency. Time-to-first-delta vs time-to-end: the gap is
      what a chat UI buys the user, the reason streaming exists at all.

LIBRARIES: strands-agents==1.57.0 (no new package).
"""

import asyncio
import time
from collections import Counter

from strands import Agent

from strands_tools import current_time  # module of @tool functions - old friend from 2.5

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
# The one helper every consumer here uses: text out of EITHER payload shape.
# Typed event (1.57 callbacks):   ContentBlockDeltaEvent -> .delta.text
# Legacy dict (stream_async):     {"delta": {"text": ...}} or {"data": "..."}
# ---------------------------------------------------------------------------
def event_text(event) -> str | None:
    if isinstance(event, dict):
        data = event.get("data")
        if isinstance(data, str) and data:
            return data
        delta = event.get("delta")
        if isinstance(delta, dict):
            return delta.get("text")
        return None
    delta = getattr(event, "delta", None)
    text = getattr(delta, "text", None)
    if text:
        return text
    data = getattr(event, "data", None)
    return data if isinstance(data, str) and data else None


def ask(agent, label, question):
    print(f"\n--- {label} ---")
    print(f"you: {question}")
    result = agent(question)
    print(f"shopbuddy: {result}")


def on_event(event):
    """(a) the callback handler - called per event, in order, during the turn."""
    text = event_text(event)
    if text:
        print(f"[delta] {text!r}")


def count_handler_factory(counter: Counter):
    """A handler that counts by event type name - the 4.1 census."""

    def receive(event) -> None:
        counter[type(event).__name__] += 1

    return receive


def main() -> None:
    SYSTEM = f"""You are a support assistant for PixelMart.

Products and prices (INR):
{CATALOG}

Use the tool for today's date when a delivery question needs it. If you cannot
answer something, say so plainly. Answer in 1-3 friendly sentences."""

    agent = Agent(
        model=model,
        system_prompt=SYSTEM,
        tools=[current_time],
        callback_handler=on_event,  # (a) - explicitly NOT None this time
    )

    # 4.1 - the event census: one turn, counted by class name.
    print("--- 4.1  every event type, one turn, counted ---")
    census: Counter = Counter()
    agent.callback_handler = count_handler_factory(census)
    result = agent("Is the Samsung SSD in stock?")
    print(result)  # the census printed above DURING the turn
    print("\nevent counts:")
    for name, count in census.most_common():
        print(f"  {name}: {count}")

    # 4.2 - the reply as the user sees it: deltas printed as they arrive.
    print("\n--- 4.2  live deltas (exactly what a chat UI renders) ---")
    agent.callback_handler = on_event
    print("you: What is today's date?")
    result = agent("What is today's date?")
    print("")
    print(f"final text assembled anyway: {str(result)[:80]!r}")

    # 4.3 - (b) stream_async: the same events, through a loop you own.
    agent.callback_handler = None  # only the explicit loop may print now

    async def stream_and_print(question: str) -> str:
        chunks: list[str] = []
        stream_dict_events = 0
        async for event in agent.stream_async(question):
            if isinstance(event, dict):
                stream_dict_events += 1
            text = event_text(event)
            if text:
                chunks.append(text)
                print(text, end="", flush=True)
        return "".join(chunks), stream_dict_events

    print("\n--- 4.3  stream_async (explicit async loop, dict events) ---")
    print("you: Is the webcam in stock and how many days for delivery?")
    whole, dict_events = asyncio.run(stream_and_print("Is the webcam - SKU-CAM-LOG-01 - in stock?"))
    print("")
    print(f"assembled {len(whole)} chars from the loop; dict-shaped events seen: {dict_events}")
    print("(that counter is the proof callback_handler and stream_async differ in payload)")

    # 4.4 - latency: time-to-first-delta vs time-to-end.
    print("\n--- 4.4  time to first delta ---")

    async def latency(question: str) -> None:
        first_delta_time = None
        start = time.perf_counter()
        async for event in agent.stream_async(question):
            text = event_text(event)
            if text and first_delta_time is None:
                first_delta_time = time.perf_counter()
                print(f"first text after {first_delta_time - start:.2f}s; ", end="")
        print(f"total {time.perf_counter() - start:.2f}s")

    asyncio.run(latency("In one sentence: why is express shipping paid?"))
    print("\nthe gap between first-delta and total is exactly what streaming buys the user.")


if __name__ == "__main__":
    main()
