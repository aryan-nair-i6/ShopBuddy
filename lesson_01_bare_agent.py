"""Lesson 1 - The bare ShopBuddy agent.

Concept: Agent(model=..., system_prompt=...)

There are no tools in this lesson. The loop still runs - it just answers in
one pass because the model has no way to ask for anything.

Catalog here is the CANONICAL PixelMart catalog. test.py has its own
throwaway demo catalog; ignore it.
"""

from strands import Agent

from Models.llmModels import model

SYSTEM_PROMPT = """You are a support assistant for PixelMart, an online electronics retailer.

Products and prices (all prices in INR):
- Wireless Mouse, Logitech - 799
- USB-C Cable (1m), Anker - 349
- Bluetooth Earbuds, boAt - 1499
- 27-inch Monitor, Dell - 15999
- Mechanical Keyboard, Redragon - 2499
- Power Bank 20000mAh, Mi - 1799
- External SSD 1TB, Samsung - 6499
- Smartwatch, Noise - 2999
- Laptop Stand, AmazonBasics - 899
- Webcam 1080p, Logitech - 3499

The ten items above are the entire catalog. You have no access to any other
system, so you cannot check stock levels, order status, delivery dates, or
process refunds or returns.

If you don't know something, say so plainly. Never invent prices, stock
levels, or order details. Answer in 1-3 friendly sentences."""


def ask(agent: Agent, label: str, question: str) -> None:
    """Send one question and print the reply under a label."""
    print(f"\n--- {label} ---")
    print(f"you: {question}")
    result = agent(question)
    print(f"shopbuddy: {result}")


def main() -> None:
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        # Strands installs a PrintingCallbackHandler by default, so every reply is
        # already echoed to the console. Passing None silences it so our own
        # print() is the only output. Lesson 4 replaces this with a real handler.
        callback_handler=None,
    )

    # 1.2 / 1.5 - out of scope entirely. Should refuse.
    ask(agent, "1.2  out of scope", "What is the weather today?")

    # 1.3 - a real catalog question. Should quote 15999.
    ask(agent, "1.3  catalog lookup", "How much is the 27-inch Dell monitor?")

    # 1.4 - follow-up. Answers WITHOUT us resending the first question,
    # because the agent keeps the conversation in agent.messages.
    ask(agent, "1.4  follow up", "Do you have any mice?")

    print(f"\nconversation turns stored by the agent: {len(agent.messages)} messages")

    # 1.5 - the tempting one. The product IS in the catalog, so the model
    # wants to answer - but stock was never in the prompt. Should refuse.
    ask(agent, "1.5  tempting gap", "Is the Samsung SSD in stock?")


if __name__ == "__main__":
    main()
