import os

# Keep the suite offline and deterministic even when backend/.env configures a
# real model: load_dotenv never overrides a variable that is already set.
os.environ["CHROMASWARM_LLM_MODEL"] = ""
# The WebSocket tests drive the real app module: no Next.js builds or browser windows there.
os.environ["CHROMASWARM_BUILD"] = "0"
# Sessions in memory: the suite never writes workspaces/.state/sessions.sqlite.
os.environ["CHROMASWARM_STATE_DB"] = ""
# Fail on any checkpoint type missing from graph.SERDE's allowlist (it would be dropped on resume).
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
