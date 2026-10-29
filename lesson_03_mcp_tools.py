"""Lesson 3 - Tools that live in ANOTHER process (MCP).

Concept: MCPClient (client/server split) + tools=[*mcp_client.list_tools_sync()]

THE WALL: Lesson 2 put stock and order tools next to the agent, in the same
file. That works until the data's real owner is someone else - policy text is
owned by the compliance team, gets edited without code changes, and must be
audited. Copy-pasting policy into a lesson's Python copied it out of the team
that owns it. Also: a support agent would eventually need MANY such sources;
pasting all future tools into one agent file does not scale.

THE IDEA: the Model Context Protocol (MCP) is a rulebook for tools you hand
over to someone else. A *server* is an ordinary program (here a small Python
file) that keeps its own tools and speaks JSON-RPC over stdio. A *client*
spawns the server, learns its menu (a handshake), and passes the menu on as if
the tools were local. A copy-forward of Lesson 2's launcher:

    server process --JSON-RPC over stdio--> client (MCPClient) --> Agent

The client stays INSIDE `with mcp_client:` - the server process is alive only
in that block. Same mental model as `open()`.

WHAT'S GENUINELY NEW: the loop, tools and registry are IDENTICAL. Only the
source of the tool list changed - the registry accepts not only functions and
modules (Lesson 2) but also fully-declared, already-running remote tools:
`MCPAgentTool` objects, i.e. `mcp_client.list_tools_sync()`.

GOTCHAS (verified on this machine):
  1. mcp 2.x renamed FastMCP -> MCPServer. `mcp.server.fastmcp` raises
     ModuleNotFoundError in mcp==2.1.1.
  2. You cannot pass `tools=[mcp_client]` itself to Agent() while the client is
     already inside its `with` block - the registry would call start() an
     second time. Pass the listed tools: `tools=[*mcp_client.list_tools_sync()]`.
  3. Listed tools are `MCPAgentTool` objects; their name lives on
     `.tool_name`, not `.name`.

MICROTASKS:
  3.1 Read lesson_03_mcp_server.py. Run it standalone: `python lesson_03_mcp_server.py`
      It prints nothing and blocks - that is the server waiting for JSON.
      Ctrl+C to quit.
  3.2 Run this file's 3.2 block: it spawns the server, does the handshake, and
      prints the menu it discovered - the same shape as lesson 2.2's spec.
  3.3 Ask a refund question: the tool lives in a different process, but the
      model cannot tell - same loop, same toolResult blocks.
  3.4 Ask a mix: refactor policy (MCP) and stock (local) in ONE agent. Two
      sources, zero dispatch code: the model routes.

LIBRARIES: mcp==2.1.1 (already in requirements.txt).
"""

import json
import sys  # for the server process executable

from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

from strands import Agent, tool
from strands.tools.mcp import MCPClient

from Models.llmModels import model  # noqa: E402  (must load .env before the model is built)

# ---------------------------------------------------------------------------
# The LOCAL tools copied forward from Lesson 2 (standalone rule).
# They stay local: stock and orders are *our* data, fake-in-process.
# ---------------------------------------------------------------------------
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


def _stock_lookup(sku: str) -> str:
    inventory = {
        "SKU-EXT-SSD-1TB": "23 in stock, restock expected next week",
        "SKU-MON-27-DEL": "8 in stock",
        "SKU-MSE-LOG-01": "142 in stock",
    }
    return inventory.get(sku, f"No product found with SKU '{sku}'.")


@tool
def check_stock_tool(sku: str) -> str:
    """Check current stock for a PixelMart product.

    Args:
        sku: The product SKU code, for example SKU-EXT-SSD-1TB
    """
    return _stock_lookup(sku)


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


def build_agent(mcp_client: "MCPClient") -> Agent:  # noqa: F821 (type only)
    """One agent whose tools come from BOTH a local file and a remote server."""
    return Agent(
        model=model,
        system_prompt=f"""You are a support assistant for PixelMart.

Products and prices (INR):
{CATALOG}

Stock, orders and policies live in tools. Never guess policies, prices,
stock or order details - look them up. If no tool can answer, say so plainly.
Answer in 1-3 friendly sentences.""",
        # THE line that is new vs Lesson 2: the tool list now contains
        # declared MCPAgentTool objects learned from the server's handshake.
        tools=[*mcp_client.list_tools_sync(), check_stock_tool, check_order_status],
        callback_handler=None,  # silence the default printer again
    )


def main() -> None:
    # -----------------------------------------------------------------------
    # 3.2 the handshake happens HERE, at constructor time: this lambda is the
    # spawn instruction. It is called once, when we enter `with mcp_client:`.
    # -----------------------------------------------------------------------
    print("--- 3.2  spawn server, handshake, list tools ---")
    mcp_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command=sys.executable,  # run the server with THIS venv's python
                args=["lesson_03_mcp_server.py"],
            )
        )
    )
    # open a session to the server (same mental model as opening a file)
    with mcp_client:
        menu = mcp_client.list_tools_sync()
        print("\n--- 3.2  the menu the agent will see ---")
        print(f"tools discovered from the server: {[t.tool_name for t in menu]}")
        print(json.dumps(menu[0].tool_spec, indent=2, default=str))

        # -------------------------------------------------------------------
        # 3.3 - one agent, mixed sources. The model sees one flat menu.
        # -------------------------------------------------------------------
        agent = build_agent(mcp_client)
        print("\n--- 3.3  policy question (answer lives on the server) ---")
        print("you: Can I return an opened USB-C cable?")
        result = agent("Can I return an opened USB-C cable?")
        print(f"shopbuddy: {result}")

        print("\n--- 3.4  mixed: MCP policy + local stock in one agent ---")
        print("you: How much is the power bank, and when does my order 8823 arrive?")
        result = agent("How much is the power bank, and when does my order 8823 arrive?")
        print(f"shopbuddy: {result}")
    # exiting the with-block KILLS the server process. The next lesson's
    # streaming step never sees it again; the connection is per-invocation.


if __name__ == "__main__":
    main()
