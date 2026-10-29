"""Lesson 7 - Steering: your judgment INSIDE the loop, not just a log next to it.

Concept: interventions=[<InterventionHandler>] with Proceed/Guide/Deny/Confirm
and the human-in-the-loop interrupt that Confirm raises.

THE WALL: Lesson 5's AuditTrail could only WATCH. Support reality needs
control: a wrong tool call must not execute; an ambiguous docstring must not
reach the customer; a refund must wait for a human yes/no. A log can note
"the model called process_refund"; it cannot STOP it.

THE IDEA: an InterventionHandler looks like a HookProvider (same events!) but
every method RETURNS A VERDICT instead of nothing:
  Proceed()       - normal path, no comment (the default).
  Guide(feedback) - let it through, but inject feedback the model reads next
                    turn. Nudge, not veto.
  Deny(reason)    - cancel the action; the reason becomes the tool result the
                    model sees, so it can explain and try a different path.
  Confirm(prompt) - STOP. The agent call returns early with
                    `result.interrupts`; the pending action is parked. You
                    fill in `interrupt.response = <human answer>` and re-call
                    the agent() to resume exactly where it stopped.
Verified verdict methods on 1.57.0 InterventionHandler:
  before_invocation / before_model_call / after_model_call /
  before_tool_call / after_tool_call.

WHAT'S GENUINELY NEW: Lesson 5 hooks run next to the loop; interventions are
decision points IN the loop. The Confirm flow is genuinely novel machinery:
the pending tool replays WITHOUT re-calling the model - the model never knows
it was paused.

MICROTASKS:
  7.1 Run block 7.1 - Guide: ask for webcam stock WITHOUT a SKU. The gate
      agrees to let the turn continue but injects feedback; watch the model
      respond to the guidance in the SAME conversation.
  7.2 Run block 7.2 - Deny against the money tool for an order that has not
      even been delivered (8810). The tool never runs; the model *sees the
      reason* and answers humanly instead.
  7.3 Run block 7.3 - Confirm, the human loop: refund attempt -> agent call
      returns with interrupts NOT executed -> simulate the human answering ->
      resume -> tool runs, the customer gets the real answer.
LIBRARIES: strands-agents==1.57.0 (no new package)."""

from strands import Agent, tool
from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed
from strands.hooks import BeforeToolCallEvent

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
        "SKU-CAM-LOG-01": "12 in stock",
        "SKU-EXT-SSD-1TB": "23 in stock, restock expected next week",
        "SKU-MON-27-DEL": "8 in stock",
        "SKU-MSE-LOG-01": "142 in stock",
    }
    return inventory.get(sku, f"No product found with SKU '{sku}'.")


@tool
def process_refund(order_id: str, order_total_inr: str) -> str:
    """Issue a full refund of the order total back to the original payment method.

    Args:
        order_id: The order number, for example 8823
        order_total_inr: The refund amount in INR, for example 15999
    """
    return f"Refund of INR {order_total_inr} issued for order {order_id}."


class SupportGate(InterventionHandler):
    """The support supervisor: nudges sloppy calls, controls money only."""

    # InterventionHandler is an ABC: a stable name is required by the
    # machinery (it appears in interrupt ids and any per-gate bookkeeping).
    name = "support-gate"

    def before_tool_call(self, event: BeforeToolCallEvent):
        name = event.tool_use.get("name")
        args = event.tool_use.get("input") or {}

        if name == "check_stock_tool" and not str(args.get("sku", "")).startswith("SKU-"):
            # 7.1 - nudge the model to look up a real SKU; allow retry next turn
            return Guide(feedback=(
                "Stock lookups need a SKU code from the catalog, not a product "
                "name. Answer from what you have; if a SKU is required, say so."
            ))

        if name == "process_refund":
            if str(args.get("order_id")) == "8810":
                # 7.2 - hard veto: it never runs, the model sees the reason
                return Deny(reason=(
                    "Order 8810 has not been delivered yet - our refund policy "
                    "starts after delivery. Explain this and offer the options."
                ))
            # 7.3 - pausing money always needs a human; the tool is NOT run yet
            return Confirm(
                prompt=(
                    f"Human approval needed: refund INR {args.get('order_total_inr')} "
                    f"for order {args.get('order_id')}? Answer with 'approved' or 'denied'."
                ),
                reason="Refunds are irreversible.",
            )

        return Proceed()


def main() -> None:
    SYSTEM = f"""You are a support assistant for PixelMart.

Products and prices (INR):
{CATALOG}

Refunds are issued only through the refund tool, and only after the customer
has been told the 7-day policy. Answer in 1-3 friendly sentences."""

    gate = SupportGate()
    agent = Agent(
        model=model,
        system_prompt=SYSTEM,
        tools=[check_stock_tool, process_refund],
        interventions=[gate],
        callback_handler=None,
    )

    # 7.1 - Guide: sloppy argument, allowed through with feedback.
    print("--- 7.1  Guide: nudge, not veto ---")
    print("you: Is the webcam in stock?")
    print("shopbuddy: " + str(agent("Is the Logitech webcam in stock?")))

    # 7.2 - Deny: the disaster tool never fires when the order is on its way.
    print("\n--- 7.2  Deny: the tool does not run ---")
    print("you: Refund my order 8810, it's INR 349.")
    print("shopbuddy: " + str(agent("Refund my order 8810 please, INR 349.")))

    # 7.3 - Confirm: human in the loop, then resume.
    print("\n--- 7.3  Confirm: pause, human answers, resume ---")
    print("you: Refund my order 8823, it is INR 15999.")
    result = agent("Please refund order 8823 - INR 15999 to my card.")
    print(f"first call returned with stop_reason: {result.stop_reason!r}")
    for it in result.interrupts:
        print(f"  INTERRUPT {it.name}: {it.reason} waiting on: {it.response is None}")

    # simulate the human clicking YES on a support console
    for it in result.interrupts:
        it.response = "approved by human"

    print("resuming...")
    resumed = agent()  # re-calls the agent; the pending tool replays here
    print(f"shopbuddy (after human yes): {resumed}")


if __name__ == "__main__":
    main()
