"""Lesson 8 - Persistent memory: two different ideas beginners always conflate.

Concept: session_manager=FileSessionManager(...)  and  memory_manager=MemoryManager(...)

THE WALL: Every lesson so far built a NEW agent in a NEW process and its
`agent.messages` died with the process. Two consequences.
  (1) A customer chats with ShopBuddy, closes the tab, comes back tomorrow -
      Lesson 1's "the agent keeps the conversation" is true within a run and
      worthless across runs.
  (2) ShopBuddy learns nothing long-term: if a customer mentions "I only buy
      Logitech gear, my laptop has USB-A ports only", that lives exactly one
      session. Restart = zero knowledge, forever. Nothing accumulates.

THE IDEA - the split this lesson exists for:
  * A SESSION is a replayable transcript: the ordered message history.
    FileSessionManager(session_id=...) writes it to disk and reloads the
    EXACT messages for that id. A new agent with the same id can "continue"
    the chat. It is storage of a conversation, not understanding.
  * MEMORY is extracted, reusable FACTS: not "turn 3 said X" but "prefers
    Logitech" - decontextualized, searchable, injectable into ANY future
    conversation by relevance. MemoryManager(stores=[...]) with a
    FileMemoryStore backed by LocalFileStorage gives two directions:
      - ADD: the agent gets a memory-add tool; facts are written explicitly
        when the user hands them over (that is 8.4).
      - INJECT: relevant stored facts are silently attached to future
        prompts (the defaults already enable this), so a brand-new session
        still starts knowing those facts (that is 8.5).
    One sentence to hold: sessions preserve the CONVERSATION; memory
    preserves the UNDERSTANDING about the customer.

WHAT'S GENUINELY NEW: Lesson 1's `agent.messages` was a free-floating list
that died with the process. Both `session_manager=` and `memory_manager=` are
storage backends wired through Agent(...) parameters: nothing about the loop
changed; persistence is a one-line constructor property. (S3SessionManager
and the Bedrock-knowledge-base vended store are the same ideas hosted
elsewhere - the migration is Cloud, not code.)

MICROTASKS:
  8.1 Run block 8.1: two questions in one agent backed by a file session.
      Then look in ./memory/sessions - one directory per session id.
  8.2 Run block 8.2: a BRAND-NEW agent object, same session_id. It knows the
      transcript because it replays the file - before any model call.
  8.3 Run block 8.3: memory store wired. Print the tool list: the manager
      contributed a tool the agent did not have in Lessons 2-7.
  8.4 Run block 8.4: ask ShopBuddy to REMEMBER a fact; watch the add tool
      being chosen, then check ./memory/memory_store on disk.
  8.5 Run block 8.5: a NEW session and a NEW agent instance - "What do you
      know about me?" is answered from injected facts, not from a transcript.

LIBRARIES: strands-agents==1.57.0 (+ boto3 only if you later choose the S3
session manager - not used by this lesson).
"""

import shutil

from strands import Agent
from strands.memory import MemoryManager
from strands.memory import MemoryToolConfig
from strands.session.file_session_manager import FileSessionManager
from strands.storage.local_file_storage import LocalFileStorage
from strands.vended_memory_stores import FileMemoryStore

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

SESSION_ID = "shopbuddy-lesson-08"
SESSIONS_DIR = "./memory/sessions"
MEMORY_DIR = "./memory/memory_store"

SYSTEM = f"""You are a support assistant for PixelMart.

Products and prices (INR):
{CATALOG}

Answer in 1-3 friendly sentences. If a fact about the customer was given to
you (memory or conversation), use it rather than asking again."""


def ask(agent, label, question):
    print(f"\n--- {label} ---")
    print(f"you: {question}")
    result = agent(question)
    print(f"shopbuddy: {result}")


def build_session_agent() -> Agent:
    """A ShopBuddy whose whole conversation survives restarts."""
    return Agent(
        model=model,
        system_prompt=SYSTEM,
        session_manager=FileSessionManager(session_id=SESSION_ID, storage_dir=SESSIONS_DIR),
        callback_handler=None,
    )


def build_memory_agent() -> Agent:
    """A ShopBuddy with a fact store; the add tool writes, injection reads."""
    facts = FileMemoryStore(
        name="pixelmart-customer-facts",
        description="Long-term facts about individual PixelMart customers.",
        storage=LocalFileStorage(MEMORY_DIR),
    )
    manager = MemoryManager(
        stores=[facts],
        add_tool_config=MemoryToolConfig(
            name="remember_customer_fact",
            description="Store one durable fact about THIS customer for future conversations.",
        ),
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM + "\nUse the memory add tool for durable customer preferences and constraints.",
        memory_manager=manager,
        callback_handler=None,
    )


def main() -> None:
    # 0. clean slate so the lesson is repeatable
    shutil.rmtree(SESSIONS_DIR, ignore_errors=True)
    shutil.rmtree(MEMORY_DIR, ignore_errors=True)

    # 8.1 - write the session
    first = build_session_agent()
    ask(first, "8.1 session: the preference", "I only buy Logitech gear. Do you have mice?")
    ask(first, "8.1 session: follow-up", "Great - and do they make keyboards too?")

    # 8.2 - read the session with a brand-new agent object
    print("\n--- 8.2  a new agent replays the SAME session id ---")
    second = build_session_agent()
    print(f"messages restored from disk without a single model call: {len(second.messages)}")
    result = second("Which brand did I say I prefer?")
    print("you: Which brand did I say I prefer?")
    print(f"shopbuddy: {result}")

    # 8.3 - memory wiring, and what it adds to the menu
    print("\n--- 8.3  memory manager: what the wiring contributes ---")
    third = build_memory_agent()
    specs = third.tool_registry.get_all_tools_config()
    for name, spec in sorted(specs.items()):
        print(f"  tool: {name}")
        print(f"        {spec['description'][:90]}...")

    # 8.4 - hand it a fact; the add tool fires
    ask(third, "8.4 add memory", "I only buy Logitech gear - remember that for next time.")

    # 8.5 - a NEW session + NEW agent: memory injects the fact anyway
    print("\n--- 8.5  a fresh session still knows the fact ---")
    fourth = build_memory_agent()
    ask(fourth, "8.5 injection", "What do you know about my brand preferences?")
    print("\nthe split, restated: 8.2 replayed WORDS; 8.5 reused a FACT.")


if __name__ == "__main__":
    main()
