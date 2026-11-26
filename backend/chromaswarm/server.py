"""Start the backend with subprocess support on Windows.

Run from backend/: python -m chromaswarm.server
"""

from __future__ import annotations

import argparse
import logging
import sys

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ChromaSwarm Studio's backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    reload = args.reload and sys.platform != "win32"
    if args.reload and not reload:
        logging.getLogger("uvicorn.error").warning(
            "Windows: reload disabled so Playwright and build subprocesses work. Restart after editing backend code.")
    uvicorn.run("chromaswarm.main:app", host=args.host, port=args.port,
                reload=reload)


if __name__ == "__main__":
    main()
