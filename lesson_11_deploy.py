"""Lesson 11 - Deploy to cloud: observability first, migration second.

Concept: strands.telemetry (OpenTelemetry) + trace_attributes= + the S3/Bedrock/
container migration checklist.

NOTE: this repo runs on OpenAI `gpt-4o-mini` on purpose, so this lesson is a
DELIBERATE migration story, not a drift into "you should be on Bedrock".

THE WALL: Lessons 1-10 produced a locally-run, locally-observed agent. Three
walls close it shut as a real product:
  (1) Nobody but you saw a trace. A support agent in production needs its
      turns, tool calls, token spend and failures shipped to something
      queryable by OTHERS - not a print statement in a lesson file.
  (2) All the SessionManager work of Lesson 8 wrote into ./memory - without
      the laptop, the memory is gone.
  (3) The repo requires your .venv, your Python, your .env key name - it
      cannot survive a `docker run`.

THE IDEA: three layers, in dependency order:
  (a) OBSERVABILITY - the code does not change location; it starts emitting
      telemetry. Strands already instruments its own loop with OpenTelemetry;
      you only choose to REGISTER providers that ship somewhere. The SDK
      console exporter writes spans/metrics to stdout - zero infrastructure,
      the very first rung.
  (b) MEMORY TO THE CLOUD - Lesson 8's persistence moved from
      FileSessionManager to S3SessionManager (boto3 requirement already in
      requirements.txt). One constructor line.
  (c) MODEL TO THE CLOUD - Models/llmOpenAIModel -> models.bedrock.BedrockModel
      with an inference profile id; nothing else changes: the same Agent,
      the same tools.
  Containerization wraps all three: a Dockerfile installing a LINUX-SAFE
  subset of the deps (see the file; requirements.txt itself cannot run on
  Linux because pywin32==312 is Windows-only by design).

VERIFIED (1.57.0): Agent accepts `trace_attributes=` (a Mapping of primitives)
which is attached to the invocation trace. `strands.telemetry` registers
against the GLOBAL OpenTelemetry providers, so a provider must be set before
any Agent emits.

MICROTASKS:
 11.1 Run 11.1 (no key required): register console providers, force a flush,
      remind yourself what stdio telemetry looks like before Classroom
      - the "shape" an OTLP backend would receive.
 11.2 Run 11.2 (key required): one traced question. Console prints
      attributes; this is EXACTLY the payload an OTLP endpoint receives.
 11.3 Read the migration checklist printed at the end - it is the actual
      hand-off to a real deployment: 3 constructor lines + Dockerfile +
      (optionally) Bedrock.
LIBRARIES: opentelemetry-api/sdk (already in requirements.txt), boto3 (only
for the S3 option).
"""

from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

# (a) PROVIDERS FIRST, verified: strands.telemetry reads the global providers.
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)
meter_provider = MeterProvider(
    metric_readers=[PeriodicExportingMetricReader(ConsoleMetricExporter())]
)

from strands import Agent, tool  # noqa: E402  (import AFTER the provider exists)

from Models.llmModels import model  # noqa: E402

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


SYSTEM = f"""You are a support assistant for PixelMart.

Products and prices (INR):
{CATALOG}

Stock lives in tools. Never guess. Answer in 1-3 friendly sentences."""


def main() -> None:
    # 11.1 - the span shape, zero infrastructure. If an OTLP endpoint were set
    # (env OTEL_EXPORTER_OTLP_*), the SAME spans go THERE instead of stdout.
    print("--- 11.1 console span exporter: the shape of a trace ---")
    tracer = trace.get_tracer("shopbuddy.manual")
    with tracer.start_as_current_span("manual.smoke.span") as span:
        span.set_attribute("pixelmart.demo", True)
        print("(span printed above by the ConsoleSpanExporter)")
    meter_provider.force_flush()

    # 11.2 - one agent turn, traced. The attribute payload an OTLP backend
    # would receive is the very thing a support dashboard queries.
    print("\n--- 11.2  one traced agent turn ---")
    agent = Agent(
        model=model,
        system_prompt=SYSTEM,
        tools=[check_stock_tool],
        callback_handler=None,
        trace_attributes={"pixelmart.environment": "local", "pixelmart.lesson": 11},
    )
    result = agent("Is the Samsung SSD in stock?")
    print(f"shopbuddy: {result}")
    meter_provider.force_flush()

    # 11.3 - the migration checklist, as text, because the cloud pieces need
    # AWS credentials this repo does not ship with.
    print("""
--- 11.3  the real deployment checklist (no AWS creds in this repo) ---

OBSERVE FOR REAL
  export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=https://<your-otel-collector>/v1/metrics
  export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://<your-otel-collector>/v1/traces
  (the Console exporters go away; the spans/metrics stay identical)

SESSIONS TO S3 (one constructor line; boto3 already a requirement)
  from strands.session.s3_session_manager import S3SessionManager
  session_manager = S3SessionManager(session_id=SESSION_ID, bucket="pixelmart-sessions")
  ...Agent(..., session_manager=session_manager)

BEDROCK MODEL SWAP (Models/llmModels sibling)
  from strands.models.bedrock import BedrockModel
  model = BedrockModel(model_id="anthropic.claude-3-5-haiku-20241022-v1:0")
  (.env does not carry OPENAI_API_KEY any more; the Agent code is unchanged)

CONTAINERIZE
  see Dockerfile - it intentionally does NOT pip install -r requirements.txt,
  because pywin32==312 makes that file Windows-only by design. It installs
  the Linux-safe runtime subset instead:

    python:3.13-slim
    RUN pip install strands-agents==1.57.0 strands-agents-tools==0.8.9 \\
            mcp==2.1.1 openai==3.19.2 python-dotenv==1.2.3
    COPY lesson_*.py Models/ ./
    ENV PYTHONUNBUFFERED=1
    CMD ["python", "lesson_04_streaming.py"]
    (OPENAI_API_KEY arrives as -e, never baked in)
""")


if __name__ == "__main__":
    main()
