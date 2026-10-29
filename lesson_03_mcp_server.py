"""The PixelMart *policy* MCP server - the server side of Lesson 3.

Concept: an MCP server is just a program that speaks the Model Context Protocol.
It owns an authoritative source of truth (here: store policies) and exposes
named tools over it. It runs in a SEPARATE process from the agent, so policies
can be versioned, deployed and audited without touching the agent.

mcp 2.x note: this used to be `from mcp.server.fastmcp import FastMCP`; in
mcp 2.1.1 it is `from mcp.server.mcpserver import MCPServer`.

Run it standalone (it blocks, speaking JSON over stdio):
    python lesson_03_mcp_server.py
"""

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("pixelmart-policies")

POLICIES = """REFUNDS: full refund if requested within 7 days of delivery, back to the
original payment method. Damaged items require a photo. Opened software is not refundable.
SHIPPING: standard delivery 3-5 working days, INR 99. Free above INR 1500.
Express delivery 1-2 working days, INR 199. We cannot ship to P.O. boxes.
WARRANTY: all PixelMart electronics carry a 1-year manufacturer warranty handled
by the brand, not by PixelMart. PixelMart is not the warranty issuer."""

OFF_HOURS_FINES = {
    "weekend processing": "Orders placed on weekends are processed the next working day.",
    "invoice": "Invoices are emailed automatically within 24 hours of dispatch.",
}


@mcp.tool()
def get_policy(topic: str) -> str:
    """Return the full PixelMart policy text for one topic: refund, shipping or warranty.

    Args:
        topic: Which policy to look up. One of: refund, shipping, warranty.
    """
    key = topic.strip().lower()
    if key in ("refund", "refunds"):
        return POLICIES.split("SHIPPING:")[0].strip()
    if key == "shipping":
        section = POLICIES.split("SHIPPING:")[1]
        return ("SHIPPING:" + section.split("WARRANTY:")[0]).strip()
    if key == "warranty":
        return ("WARRANTY:" + POLICIES.split("WARRANTY:")[1]).strip()
    return OFF_HOURS_FINES.get(
        key,
        f"No policy named {topic!r}. Known topics: refund, shipping, warranty.",
    )


if __name__ == "__main__":
    mcp.run()  # default transport is stdio: JSON in/out on stdin/stdout
