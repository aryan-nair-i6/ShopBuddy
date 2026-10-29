# Containerization for Lesson 11. IMPORTANT: this intentionally does NOT
# `pip install -r requirements.txt`, because pywin32==312 pins that file to
# Windows. This installs the Linux-safe runtime subset instead.
FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    strands-agents==1.57.0 \
    strands-agents-tools==0.8.9 \
    mcp==2.1.1 \
    openai==3.19.2 \
    python-dotenv==1.2.3

COPY Models/ ./Models/
COPY lesson_01_bare_agent.py .
COPY lesson_02_tools.py .
COPY lesson_03_mcp_server.py .
COPY lesson_03_mcp_tools.py .
COPY lesson_04_streaming.py .
COPY lesson_05_hooks.py .
COPY lesson_06_plugins_skills.py .
COPY lesson_07_steering.py .
COPY lesson_08_memory.py .
COPY lesson_09_multiagent.py .
COPY lesson_10_bare_evals.py .
COPY lesson_11_deploy.py .

ENV PYTHONUNBUFFERED=1

# The key is passed at runtime: docker run -e OPENAI_API_KEY=... (never baked in)
CMD ["python", "lesson_02_tools.py"]
