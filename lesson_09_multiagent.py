"""Lesson 9 - Multiagent: three different patterns for three different problems.

Concepts: agent-as-tool (Agent.as_tool()), GraphBuilder, Swarm.

THE WALL: One agent with fifteen tools violates its own menu: product, return,
billing and complaint tools all sit in ONE flat list, and the model picks
wrongly more and more often as the list grows. A support desk is naturally a
TEAM: a front line that routes, specialists who own one subject. The model
cannot see that structure if you give it three similarly-named tools.

THE IDEA - three patterns, and the problem each one solves (they are NOT
interchangeable):
  (1) AGENT-AS-TOOL: a specialist stays hidden behind one menu entry.
      `specialist.as_tool(name=..., description=...)` wraps a whole Agent
      into a single tool. The specialist keeps its own system prompt and its
      own tool list - the orchestrator never sees the specialist's internals.
      Problem solved: menu bloat and tool-adjacency confusion.
  (2) GRAPH (GraphBuilder): FIXED, hand-authored control flow. Nodes and
      edges are declared by you; an edge condition is a plain Python function
      over GraphState (verified fields: .task, .completed_nodes, .results,
      .execution_order, ...). Problem solved: compliance - the route must be
      triage -> billing OR returns -> close, with zero improvisation allowed.
  (3) SWARM: dynamic handoff, no fixed order. Every node can HAND OFF to a
      named teammate or FINISH the task. Problem solved: open questions where
      the right specialist only becomes obvious after listening.
  Hold the three in one line: (1) hides a capability, (2) fixes the route,
  (3) gives the agents the steering wheel.

WHAT'S GENUINELY NEW: the atom unchanged - Agent is still Agent. Graph and
Swarm are also invokables: call them like an agent, get a MultiAgentResult
(verified fields: .status, .results, .execution_count, .execution_time).
The multi-agent code does not call the model differently per pattern - the
PATTERN lives entirely in who may call whom, and when.

MICROTASKS:
  9.1 Run block 9.1: orchestrator + two hidden specialists via as_tool.
      Print the orchestrator's tool menu first: TWO entries, not ten.
  9.2 Read build_graph(): triage -> (billing | returns) -> goodbye. The route
      decision is YOUR Python, not the model's.
  9.3 Run block 9.3: the same three customer messages through the graph -
      execution order is visible and identical in shape every time.
  9.4 Run block 9.4: the same message through a swarm. No fixed order exists;
      watch the handoff chain choose its own path. Diff 9.3 vs 9.4: fixed vs
      emergent.

LIBRARIES: strands-agents==1.57.0 (no new package).
"""

from strands import Agent, tool
from strands.multiagent import GraphBuilder, Swarm

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

REFUND_POLICY = "Refunds within 7 days of delivery, back to the original payment method."


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


def named_agent(name: str, system_prompt: str, tools=None) -> Agent:
    """Small factory because every specialist is 90% copy-paste."""
    return Agent(
        name=name,
        model=model,
        system_prompt=system_prompt,
        tools=tools or [],
        callback_handler=None,
    )


def make_specialists():
    """Three specialists + one closer. Each owns its subject completely."""
    stock = named_agent(
        "stock-specialist",
        "You answer ONLY product availability. Use check_stock; never mention "
        "money, orders or policy. Answer in 1-2 sentences.",
        tools=[check_stock_tool],
    )
    billing = named_agent(
        "billing-specialist",
        f"You answer ONLY billing and refunds. The policy: {REFUND_POLICY} "
        "Never mention stock. Answer in 1-2 sentences.",
    )
    returns = named_agent(
        "returns-specialist",
        "You answer ONLY returns and cancellations: photo required for damage, "
        "opened software not returnable, 7-day window. Answer in 1-2 sentences.",
    )
    goodbye = named_agent(
        "goodbye",
        "Thank the customer in one short sentence and close.",
    )
    return stock, billing, returns, goodbye


def main() -> None:
    stock, billing, returns, goodbye = make_specialists()

    # -----------------------------------------------------------------------
    # 9.1 - pattern 1: agent-as-tool. Menu shrinks; internals stay hidden.
    # -----------------------------------------------------------------------
    print("--- 9.1  agent-as-tool: the menu, not the plumbing ---")
    orchestrator = Agent(
        name="shopbuddy",
        model=model,
        system_prompt=f"""You are ShopBuddy's front line for PixelMart.
Route: every stock question goes to the stock specialist tool, every
refund/billing question to the billing specialist tool. NEVER answer
specialist topics yourself. Keep one friendly sentence around the answer.

Catalog for your own answers (INR):
{CATALOG}""",
        tools=[
            stock.as_tool(
                name="ask_stock_specialist",
                description="Delegate ONE product-availability question to the stock specialist.",
            ),
            billing.as_tool(
                name="ask_billing_specialist",
                description="Delegate ONE billing/refund question to the billing specialist.",
            ),
        ],
        callback_handler=None,
    )
    menu = orchestrator.tool_registry.get_all_tools_config()
    print(f"orchestrator's tool menu: {[name for name in menu]}")
    print("\nyou: Is the Dell monitor in stock, and can I get a refund for order 8823?")
    answer = orchestrator("Is the Dell monitor in stock, and can I get a refund for order 8823?")
    print(f"shopbuddy: {answer}")

    # -----------------------------------------------------------------------
    # 9.2 - the graph: the route is authored, conditions are your Python.
    # -----------------------------------------------------------------------
    def build_graph():
        builder = GraphBuilder()
        builder.add_node(billing, "billing")
        builder.add_node(returns, "returns")
        builder.add_node(goodbye, "goodbye")
        # entry point is decided here, BEFORE any text exists, by looking at
        # only the task - this is the "fixed flow" part.
        builder.set_entry_point("billing")
        # ...but supports branching too: which specialist sees the message
        # first is decided by edge conditions reading GraphState.
        def route(state) -> bool:  # GraphState -> bool
            return "refund" in state.task.lower() if isinstance(state.task, str) else False

        builder.add_edge("billing", "goodbye")
        builder.add_edge("billing", "returns", condition=route)
        builder.set_max_node_executions(10)
        return builder.build()

    # -----------------------------------------------------------------------
    # 9.3 - run the graph on three messages; watch the FIXED shape.
    # -----------------------------------------------------------------------
    print("\n--- 9.3  graph: three messages, fixed waves ---")
    graph = build_graph()
    messages = [
        "I need a refund for order 8823.",
        "How do I return a damaged keyboard?",
        "Thanks, that's all.",
    ]
    for question in messages:
        result = graph(question)
        print(f"\nyou: {question}")
        order = list(result.results)
        print(f"  execution order: {order}")
        print(f"  status: {result.status}  executions: {result.execution_count}  {result.execution_time:.1f}s")
        print(f"  final: {str(result)[:400]}")

    # -----------------------------------------------------------------------
    # 9.4 - pattern 3: swarm. No fixed order; handoffs are emergent.
    # -----------------------------------------------------------------------
    print("\n--- 9.4  swarm: dynamic handoff, no fixed route ---")
    swarm = Swarm(nodes=[stock, billing, returns], entry_point=stock, max_handoffs=8)
    question = "Is the power bank in stock, and can I still return my webcam?"
    result = swarm(question)
    print(f"you: {question}")
    print(f"  execution order: {list(result.results)}")
    print(f"  status: {result.status}  executions: {result.execution_count}  {result.execution_time:.1f}s")
    print(f"  final: {str(result)[:400]}")
    print("\ndiff 9.3 vs 9.4: the graph's order was authored; the swarm's order emerged.")


if __name__ == "__main__":
    main()
