"""Lesson 10 - Evaluating: no official eval package - so build the grader.

Concept: evaluation as code, graded on (1) task success, (2) tool-choice
correctness, (3) latency/cost.

THE WALL: Everything so far was graded by please-look-yourself: "should
refuse", "vague docstring fumbles" - all just console prints EYEBALLED at the
time. Nothing stops tomorrow's docstring "fix" from quietly breaking Lesson
2.4's tool routing, and nobody will notice until a customer does.

THE IDEA (from scratch): an agent is a program with nondeterminism, so grade
it the way you grade code - with assertions:
  1. TASK SUCCESS - did the customer get a correct final answer?
     (here: a cheap string-contains grader; a stronger one delegates to the
     model itself, at the price of running the model twice)
  2. TOOL CHOICE  - did the model pick the RIGHT tool with SANE arguments?
     The data is already in agent.messages (verified shape in this repo: the
     model's call is a {"toolUse": {"name", "input"}} block; the reply is a
     {"toolResult": {...}} block) - read and assert on it.
  3. LATENCY/COST - seconds per case; token totals from agent.metrics.
     A grader that never looks at the bill will not warn before it doubles.
There is no official Strands eval package on PyPI (a `strands-agents-eval`
does not exist; `strands-evals` 0.0.1 is a stub). The harness below is
therefore ~60 lines of plain code: cases + graders + a run loop. That IS an
eval framework, covers off.

WHAT'S GENUINELY NEW: the agent is not extended - it is finally a subject.
Nothing in the loop changed; what changed is the RELATIONSHIP: the grader
replays the agent against frozen expectations so regressions become visible.

MICROTASKS:
 10.1 Run block 10.1: one case, one string-contains grader. Feel how low the
      bar is for a GOOD first grader, and why cost/latency need a number.
 10.2 Run block 10.2: the SAME question graded by looking at the TRACE
      instead of the answer. This is the tool-choice check.
 10.3 Run block 10.3: the suite. All five cases, same agent config as Lesson
      2.4 - each case maps to a microtask you have already run by hand.
 10.4 Read test suite variant: evals/test_agent_evals.py wraps the same
      grader functions in pytest so the suite can run in CI: `pytest evals/`.
LIBRARIES: strands-agents==1.57.0; optional: pytest (added in Lesson 10) for
the test-file variant.
"""

import time
from dataclasses import dataclass, field

from strands import Agent, tool

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


@tool
def check_stock_tool(sku: str) -> str:
    """Check current stock for a PixelMart product.

    Args:
        sku: The product SKU code, for example SKU-EXT-SSD-1TB
    """
    inventory = {
        "SKU-EXT-SSD-1TB": "23 in stock, restock expected next week",
        "SKU-MON-27-DEL": "8 in stock",
        "SKU-MSE-LOG-01": "142 in stock",
    }
    return inventory.get(sku, f"No product found with SKU '{sku}'.")


@tool
def check_order_status(order_id: str) -> str:
    """Look up the status of a customer order.

    Args:
        order_id: The order number, for example 8823
    """
    orders = {
        "8823": "Order 8823 shipped on 2026-09-24, arriving 2026-09-28",
        "8810": "Order 8810 is out for delivery today",
    }
    return orders.get(order_id, f"No order found with number '{order_id}'.")


def build_eval_agent() -> Agent:
    """The agent under test - the Lesson 2.4 two-tool configuration."""
    return Agent(
        model=model,
        system_prompt=f"""You are a support assistant for PixelMart.

Products and prices (INR):
{CATALOG}

Stock levels and order status live in the tools; weather, refunds and
non-PixelMart topics are out of scope. Never guess.
If no tool can answer a question, say so plainly in one sentence.""",
        tools=[check_stock_tool, check_order_status],
        callback_handler=None,
    )


# ---------------------------------------------------------------------------
# The harness, covers off. A Case = question + grader. A Record = one turn.
# ---------------------------------------------------------------------------
@dataclass
class Record:
    """Everything a grader needs from ONE question -> answer turn."""

    answer: str
    tool_calls: list[dict] = field(default_factory=list)  # {"name", "input"} per call
    seconds: float = 0.0


def play_and_record(agent: Agent, question: str) -> Record:
    """Run one turn and collect the trace - the Lesson 2.5 ask() pattern."""
    before = len(agent.messages)
    t0 = time.perf_counter()
    result = agent(question)
    seconds = time.perf_counter() - t0
    calls = []
    for message in agent.messages[before:]:
        for block in message.get("content", []):
            if "toolUse" in block:
                calls.append(
                    {"name": block["toolUse"].get("name"), "input": block["toolUse"].get("input")}
                )
    return Record(answer=str(result), tool_calls=calls, seconds=seconds)


def grade_contains(fragment: str):
    def check(record: Record) -> list[str]:
        if fragment.lower() not in record.answer.lower():
            return [f"answer missing {fragment!r}: got {record.answer[:120]!r}"]
        return []

    return check


def grade_tool_choice(tool_name: str, expect_input: dict | None = None):
    """Grade the tool call at the HEAD of the trace: name, then arguments."""

    def check(record: Record) -> list[str]:
        if not record.tool_calls:
            return ["expected a tool call, none happened"]
        first = record.tool_calls[0]
        if first["name"] != tool_name:
            return [f"first call should be {tool_name!r}, was {first['name']!r}"]
        for key, fragment in (expect_input or {}).items():
            got = str(first["input"].get(key, ""))
            if fragment.lower() not in got.lower():
                return [f"{tool_name}({key}=...) missing {fragment!r}: got {got!r}"]
        return []

    return check


@dataclass
class Case:
    name: str
    question: str
    grade: object  # callable(Record) -> list[str]; empty list == pass


CASES = [
    Case("quote monitor price", "How much is the 27-inch Dell monitor?", grade_contains("15999")),
    Case("stock question routes to stock tool", "Is the Samsung SSD in stock?",
         grade_tool_choice("check_stock_tool")),
    Case("order question routes to orders tool", "Where is my order 8823?",
         grade_tool_choice("check_order_status", {"order_id": "8823"})),
    Case("wrong-SKU refusal", "Is SKU-FAKE-999 in stock?", grade_contains("no product found")),
    Case("weather stays refused", "What is the weather today?", grade_contains("cannot")),
]

BUDGET_SECONDS = 120.0


def run_suite(agent: Agent) -> tuple[list[str], float]:
    """Run every case once; return (failed case names, total seconds)."""
    failures: list[str] = []
    total_seconds = 0.0
    for case in CASES:
        record = play_and_record(agent, case.question)
        total_seconds += record.seconds
        problems = case.grade(record)
        mark = "PASS" if not problems else "FAIL"
        print(f"  [{mark}] {case.name}  ({record.seconds:.1f}s)")
        for p in problems:
            print(f"         -> {p}")
        if problems:
            failures.append(case.name)
    return failures, total_seconds


def main() -> None:
    agent = build_eval_agent()

    # 10.1 - one case, crude grader: task success, the floor.
    print("--- 10.1  one case, one string-contains grader ---")
    record = play_and_record(agent, "How much is the 27-inch Dell monitor?")
    problems = grade_contains("15999")(record)
    print(f"PASS: {not problems}{'' if not problems else ' -> ' + problems[0]}")
    print(f"(latency for that turn: {record.seconds:.1f}s - already a metric, no extra code)")

    # 10.2 - the SAME question shape, graded on the trace instead.
    print("\n--- 10.2  tool-choice grading reads the trace ---")
    record = play_and_record(agent, "Where is my order 8823?")
    print(f"  trace: {record.tool_calls}")
    print(f"  grade: {grade_tool_choice('check_order_status', {'order_id': '8823'})(record) or 'PASS'}")

    # 10.3 - the suite, with a budget gate at the end.
    print("\n--- 10.3  the suite ---")
    failures, total = run_suite(agent)
    ok_budget = total < BUDGET_SECONDS
    print(f"\n  correctness: {'ALL PASS' if not failures else 'FAILURES: ' + ', '.join(failures)}")
    print(f"  budget gate: {total:.1f}s < {BUDGET_SECONDS}s {'=> PASS' if ok_budget else '=> FAIL'}")
    print("\ntoken cost would grade identically - a threshold on the usage")
    print("(agent.metrics on the returned result) instead of the wall clock.")

    print("\n--- 10.4  pytest variant ---")
    print("evals/test_agent_evals.py reuses these grader functions under")
    print("pytest so the suite runs in CI:  pytest evals/")


if __name__ == "__main__":
    main()
