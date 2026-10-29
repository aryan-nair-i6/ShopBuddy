"""Lesson 6 - Plugins & skills: bundles of tools + hooks + know-how.

Concept: plugins=[<Plugin>]  with @tool/@hook methods inside, plus
strands.vended_plugins.skills.{Skill, AgentSkills}

THE WALL: Lessons 2-5 copied the same stock/order tools into every new agent.
Lesson 5 wanted the SAME audit trail everywhere. Tool + hook + "how to use it"
always travel together - yet each new agent got them pasted one by one, and
each paste is a drift risk: fix the docstring in one copy and the agent
registered yesterday stays wrong forever.

THE IDEA (two parts, deliberately kept apart):
  * A *plugin* is a class that BUNDLES things you already know - tools
    (@tool), hooks (@hook), custom wiring (init_agent) - under one name, and
    hands them to the agent in one line: plugins=[PixelMartPlugin()].
    Auto-discovery: the registry scans the class for @tool and @hook methods
    and registers them in declaration order. (NOTE: plugin tool methods take
    `self` first - inside the class they are ordinary methods.)
  * A *skill* is not code - it is KNOW-HOW: name + description + instructions.
    `Skill(name=..., description=..., instructions=...)`, installed via the
    `AgentSkills` plugin. The tool menu grows a skill surface the model can
    consult when the description matches the task; the instructions then steer
    HOW it acts. Tools teach the model WHAT exists; skills teach it what to DO.

WHAT'S GENUINELY NEW: the unit of reuse moved from "function" to "behavior
bundle". The model-menu interface stays identical - plugins only change where
the entries are declared.

MICROTASKS:
  6.1 Run block 6.1: the plugin with two tools + one hook, used in ONE line.
      Compare with Lessons 2-4 - same agent behavior, one less copy-paste.
  6.2 Read the @hook inside the plugin: same signature as Lesson 5's
      add_hook callbacks, same events. Nothing about hooks changed - only
      where they are declared.
  6.3 Run block 6.3: the AgentSkills plugin carrying ONE skill (returns
      escalation). Ask a question that matches its description and watch the
      instructions shape the reply. Then ask an off-topic one: no trigger, no
      instructions, plain answer.
LIBRARIES: strands-agents==1.57.0 (no new package).
"""

from strands import Agent, tool
from strands.hooks import BeforeModelCallEvent
from strands.plugins import Plugin, hook
from strands.vended_plugins.skills import AgentSkills, Skill

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


class PixelMartPlugin(Plugin):
    """Everything ShopBuddy needs to be ShopBuddy - in one class, one name."""

    name = "pixelmart-plugin"

    # -- tools (note: `self` first; these are class methods being described) --
    @tool
    def check_stock(self, sku: str) -> str:
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
    def check_order_status(self, order_id: str) -> str:
        """Look up the status of a customer order.

        Args:
            order_id: The order number, for example 8823
        """
        orders = {
            "8823": "Order 8823 shipped on 2026-09-24, arriving 2026-09-28",
            "8810": "Order 8810 is out for delivery today",
        }
        return orders.get(order_id, f"No order found with number '{order_id}'.")

    # -- hooks: identical shape to Lesson 5's add_hook callbacks ----------
    @hook
    def on_model_call(self, event: BeforeModelCallEvent) -> None:
        print(f"  [plugin {self.name}] model called")


def make_agent() -> Agent:
    """One agent, one plugin line - instead of a copied tool list."""
    return Agent(
        model=model,
        system_prompt=f"""You are a support assistant for PixelMart.

Products and prices (INR):
{CATALOG}

Stock, orders and policies live in your tools. Never guess.
Answer in 1-3 friendly sentences.""",
        plugins=[PixelMartPlugin()],
        callback_handler=None,
    )


def main() -> None:
    # 6.1 + 6.2 - tools AND a hook arrive from one bundle.
    print("--- 6.1  plugin bundle: tools + hook in one line ---")
    agent = make_agent()
    print("you: Is the Samsung SSD in stock?")
    print("shopbuddy: " + str(agent("Is the Samsung SSD in stock?")))

    # 6.3 - the Concept SPLIT: tools tell WHAT exists, skills tell what to DO.
    escalation_skill = Skill(
        name="returns-escalation",
        description="How to handle an angry customer whose refund is late.",
        instructions=(
            "When the customer is angry or swears about a late refund: (1) apologize "
            "ONCE, (2) give the exact policy - refunds are issued within 7 days of "
            "delivery, (3) offer to escalate to a human within 24 hours, (4) ask for "
            "the order number. Never blame the payment provider, ever."
        ),
    )
    skilled = Agent(
        model=model,
        system_prompt=f"""You are a support assistant for PixelMart.

Products and prices (INR):
{CATALOG}

Use your tools for stock and orders. Answer in 1-3 friendly sentences.""",
        plugins=[PixelMartPlugin(), AgentSkills(skills=[escalation_skill])],
        callback_handler=None,
    )
    print("\n--- 6.3  skill: angry-customer turn, with and without trigger ---")
    print("you: Where is my order? It's been 3 weeks, you people are thieves!")
    print("shopbuddy: " + str(skilled("Where is my order 8823? It's been 3 weeks, you people are thieves!")))
    print("\nyou (neutral): Where is my order 8810?")
    print("shopbuddy: " + str(skilled("Where is my order 8810?")))


if __name__ == "__main__":
    main()
