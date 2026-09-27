"""Lesson 2 - Tools.

Concept: @tool decorator + tools=[...]

What actually changed since Lesson 1:
  The catalog was FROZEN inside the system prompt. A tool moves data OUT of the
  prompt and INTO live code, so the agent stops guessing and starts looking things up.

Mental model:
  A tool is an ordinary Python function that ALSO gets described to the model.
  Strands inspects the function and builds a "tool spec" - a JSON menu entry the
  model reads. The model has never seen your code; it chooses a tool and builds
  arguments using ONLY the function name, the type hints, and the docstring.

  The model CANNOT run your function. It emits a *request*:
      {"name": "check_stock", "arguments": {"sku": "SKU-EXT-SSD-1TB"}}
  Strands intercepts that, runs the real function, appends the returned string to
  the conversation as a tool result, and loops the model again.

  => YOUR DOCSTRING IS NOT DOCUMENTATION. It is the model's instruction manual.
     A vague docstring yields wrong tool calls even when the code is perfect.

If you know LangChain: this is the same idea as @tool, but there is no Tool class,
no name/description/args attributes, and no AgentExecutor. The Agent *is* the
executor, and the loop is implicit.
"""

import ast
import json

from strands import Agent, tool

from strands_tools import current_time  # a MODULE, not a function - see 2.5

from Models.llmModels import model

# Canonical PixelMart catalog. Prices in INR. This is the single source of truth.
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

SYSTEM_PROMPT = f"""You are a support assistant for PixelMart, an online electronics retailer.

Products and prices (all prices in INR):
{CATALOG}

Stock levels, order status, delivery dates, and refunds live in other systems.
Use the available tools to look them up - never guess or invent an answer.

If no tool can answer a question, say so plainly. Answer in 1-3 friendly sentences."""


# ---------------------------------------------------------------------------
# Shared implementation, so 2.1 and 2.2 can never drift apart.
# ---------------------------------------------------------------------------
def _stock_lookup(sku: str) -> str:
    """The actual business logic. Just a dict lookup."""
    inventory = {
        "SKU-EXT-SSD-1TB": "23 in stock, restock expected next week",
        "SKU-MON-27-DEL": "8 in stock",
        "SKU-MSE-LOG-01": "142 in stock",
    }
    return inventory.get(sku, f"No product found with SKU '{sku}'.")


# ---------------------------------------------------------------------------
# Microtask 2.1 - a tool is just a function
# ---------------------------------------------------------------------------
# No decorator, no AI, no agent. This is the baseline: a plain Python function
# that looks up a dict. Everything Strands adds sits ON TOP of this and changes
# nothing about how the function itself behaves.
def check_stock(sku: str) -> str:
    """Plain function, no decorator. Returns stock text for a PixelMart SKU."""
    return _stock_lookup(sku)


# ---------------------------------------------------------------------------
# Microtask 2.2 - the same logic, now described to the model
# ---------------------------------------------------------------------------
# The only differences from 2.1 are the @tool decorator and a richer docstring.
# @tool requires: a type hint on every parameter, a return type, and a docstring.
# The docstring's "Args:" section becomes the per-parameter description the model
# sees - that is how it learns to pass a SKU rather than a product name.
@tool
def check_stock_tool(sku: str) -> str:
    """Check current stock for a PixelMart product.

    Args:
        sku: The product SKU code, for example SKU-EXT-SSD-1TB
    """
    return _stock_lookup(sku)


# ---------------------------------------------------------------------------
# Microtask 2.3 - the same logic, a DELIBERATELY BAD docstring
# ---------------------------------------------------------------------------
# Nothing about the behaviour changed - same lookup, same answer. Only the
# description got worse. Run the agent with this and it will fumble, because the
# model now has no idea what 'x' means or what 'stuff' covers.
@tool
def check_stock_vague(x: str) -> str:
    """does stuff"""
    return _stock_lookup(x)


# ---------------------------------------------------------------------------
# Microtask 2.4 - a second tool, so the model has to CHOOSE
# ---------------------------------------------------------------------------
# There is no routing code anywhere. The model reads the tool menu, matches the
# customer's intent to one entry, and calls that. Adding tools does not require
# you to write any dispatch logic.
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


# ---------------------------------------------------------------------------
# Microtask 2.5 (a) - a tool you wrote yourself
# ---------------------------------------------------------------------------
# Look at the docstring again: `expression` and `mode` are described, and the
# examples matter. The model has to guess any parameter you fail to describe.
#
# This is also the first tool with real logic, so note the AST allowlist. Calling
# eval() on model-supplied text is how agents get exploited; walking the parsed
# tree and rejecting anything that is not a number or an arithmetic operator is
# what makes this safe. `import os` is already refused as an unallowed node.
@tool
def calculate(expression: str, mode: str = "evaluate") -> str:
    """Evaluate a simple arithmetic expression.

    Args:
        expression: The arithmetic to evaluate, for example 2400 * 0.15
        mode: Either "evaluate" to compute the result, or "simplify" to reduce a fraction
    """
    allowed = (
        ast.Expression, ast.Constant, ast.BinOp, ast.UnaryOp,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd, ast.Load,
    )
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return f"Could not parse expression: {expression!r}"
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            return "Only numbers and the + - * / operators are allowed."
    try:
        value = eval(compile(tree, "<tool>", "eval"), {"__builtins__": {}}, {})
    except ZeroDivisionError:
        return "Cannot divide by zero."
    return str(value)


def ask(agent: Agent, label: str, question: str) -> None:
    """Send one question, print the reply, and show which tools were used.

    The tool trace is the important part. It is how you see WHICH tool the model
    picked and WHAT arguments it invented. Invented arguments are the most common
    tool bug, and they are invisible unless you print this.

    The trace comes from agent.messages, which the agent appends to on every turn.
    It is a list of {"role": ..., "content": [blocks]}; a model block that called a
    tool is a toolUse block, and the tool's reply is a toolResult block.
    """
    before = len(agent.messages)
    print(f"\n--- {label} ---")
    print(f"you: {question}")
    result = agent(question)
    print(f"shopbuddy: {result}")

    for message in agent.messages[before:]:
        for block in message.get("content", []):
            if "toolUse" in block:
                call = block["toolUse"]
                print(f"  -> {call['name']}({call['input']})")
            elif "toolResult" in block:
                result_block = block["toolResult"]
                status = result_block.get("status")
                text = " ".join(
                    part.get("text", "") for part in result_block.get("content", [])
                )
                print(f"  <- [{status}] {text[:70]}")


def main() -> None:
    # -----------------------------------------------------------------------
    # 2.1 - call the plain function directly. No model involved.
    # -----------------------------------------------------------------------
    print("--- 2.1  plain function, no AI ---")
    print(f"check_stock('SKU-EXT-SSD-1TB') -> {check_stock('SKU-EXT-SSD-1TB')}")
    print(f"check_stock('nonsense')       -> {check_stock('nonsense')}")

    # -----------------------------------------------------------------------
    # 2.2 - what the model is actually shown. This JSON *is* the interface.
    # -----------------------------------------------------------------------
    print("\n--- 2.2  the tool spec the model reads ---")
    print(json.dumps(check_stock_tool.tool_spec, indent=2, default=str))
    print("\n--- 2.2  agent with one tool ---")
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[check_stock_tool],
        callback_handler=None,  # silence Strands' default printer
    )
    # The gap from Lesson 1.5 ("I'm sorry, I don't have access to stock levels")
    # is now closed - the answer is looked up, not refused.
    ask(agent, "2.2  stock lookup", "Is the Samsung SSD in stock?")
    ask(agent, "2.2  a bad SKU", "Is SKU-FAKE-999 in stock?")

    # -----------------------------------------------------------------------
    # 2.3 - degrade the docstring on purpose, watch the model struggle.
    # -----------------------------------------------------------------------
    print("\n--- 2.3  same logic, useless docstring ---")
    vague = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[check_stock_vague],
        callback_handler=None,
    )
    ask(vague, "2.3  vague docstring", "Is the Samsung SSD in stock?")

    # -----------------------------------------------------------------------
    # 2.4 - two tools, and the model routes by itself.
    # -----------------------------------------------------------------------
    print("\n--- 2.4  two tools, model picks the right one ---")
    multi = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[check_stock_tool, check_order_status],
        callback_handler=None,
    )
    ask(multi, "2.4  routes to orders", "Where is my order 8823?")
    ask(multi, "2.4  routes to stock", "Is the Dell monitor in stock?")

    # -----------------------------------------------------------------------
    # 2.5 - a tool you did not write.
    #     (a) our own `calculate`, and (b) a prebuilt MODULE, current_time.
    #     A module is not a function: Strands scans it and registers every
    #     @tool it finds inside. Same list, different kind of entry.
    # -----------------------------------------------------------------------
    print("\n--- 2.5  own tool + prebuilt module ---")
    kitchen_sink = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT
        + "\nUse the calculator for arithmetic, and current_time to tell the "
          "customer what today's date is when a delivery estimate is vague.",
        tools=[check_stock_tool, check_order_status, calculate, current_time],
        callback_handler=None,
    )
    ask(kitchen_sink, "2.5  own calculator", "What is 15% of 2400?")
    ask(kitchen_sink, "2.5  module tool", "What is today's date?")


if __name__ == "__main__":
    main()
