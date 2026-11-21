"""Template export: the generated app as a zip the user can unpack, fill in (content/, public/images/)
and run with `npm install && npm run dev` — no ChromaSwarm needed."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

SKIP_DIRS = {"node_modules", ".next", ".turbo", ".git", "data"}  # data/: received orders (customers' phone numbers)
SKIP_FILES = re.compile(r"(\.tsbuildinfo|\.log|\.DS_Store)$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def template_zip(app_dir: Path, folder: str = "trang-web") -> bytes:
    """Zip of `app_dir` without installed packages or build output, under one top-level folder."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(app_dir.rglob("*")):
            rel = path.relative_to(app_dir)
            if path.is_dir() or SKIP_DIRS & set(rel.parts) or SKIP_FILES.search(path.name) or path.is_symlink():
                continue
            z.write(path, f"{folder}/{rel.as_posix()}")
        z.writestr(f"{folder}/public/images/.gitkeep", "")  # where the user's photos go
    return buf.getvalue()


def app_dir_for(root: Path, session_id: str) -> Path | None:
    """The session's generated app, or None for an unknown or unsafe session id."""
    if not SAFE_ID.match(session_id):
        return None
    path = (root / session_id / "app").resolve()
    if root.resolve() not in path.parents or not (path / "package.json").is_file():
        return None
    return path
