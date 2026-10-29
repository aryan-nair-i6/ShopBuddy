"""pytest variant of the Lesson 10 evals.

Same cases, same graders - COPIED FORWARD, not imported, because the repo rule
is that lesson files never import from each other and the test suite must run
without touching lesson module state.

Runs against the real OpenAI model, so it needs a live OPENAI_API_KEY in .env:
    .\\.venv\\Scripts\\Activate.ps1
    pytest evals/ -v
"""

import time
from dataclasses import dataclass, field

import pytest

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


@pytest.fixture(scope="module")
def agent():
    """One agent for the whole module - config frozen as in Lesson 2.4."""
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
# Graders (identical logic to lesson_10_bare_evals.py)
# ---------------------------------------------------------------------------
@dataclass
class Record:
    answer: str
    tool_calls: list[dict] = field(default_factory=list)
    seconds: float = 0.0


def play_and_record(agent: Agent, question: str) -> Record:
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


def grade_contains(fragment):
    def check(record: Record):
        assert fragment.lower() in record.answer.lower(), (
            f"answer missing {fragment!r}: got {record.answer[:200]!r}"
        )

    return check


def grade_tool_choice(tool_name, expect_input=None):
    def check(record: Record):
        assert record.tool_calls, "expected a tool call, none happened"
        first = record.tool_calls[0]
        assert first["name"] == tool_name, (
            f"first call should be {tool_name!r}, was {first['name']!r}"
        )
        for key, fragment in (expect_input or {}).items():
            got = str(first["input"].get(key, ""))
            assert fragment.lower() in got.lower(), (
                f"{tool_name}({key}=...) missing {fragment!r}: got {got!r}"
            )

    return check


@pytest.mark.parametrize(
    "question, grade_fn",
    [
        ("How much is the 27-inch Dell monitor?", grade_contains("15999")),
        ("Is the Samsung SSD in stock?", grade_tool_choice("check_stock_tool")),
        ("Where is my order 8823?", grade_tool_choice("check_order_status", {"order_id": "8823"})),
        ("Is SKU-FAKE-999 in stock?", grade_contains("no product found")),
        ("What is the weather today?", grade_contains("cannot")),
    ],
)
def test_agent_turn(agent, question, grade_fn):
    """Graded on task success + tool choice; a turn over 120s fails the budget."""
    record = play_and_record(agent, question)
    grade_fn(record)
    assert record.seconds < 120.0, f"turn over budget: {record.seconds:.1f}s"
