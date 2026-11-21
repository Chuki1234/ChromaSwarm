"""Publishing a built page (after B12): a live link on Vercel, or the code in a GitHub repository.

Both run only when the user clicks the button in the Studio, with a token the user put in
backend/.env themselves (VERCEL_TOKEN, GITHUB_TOKEN); ChromaSwarm never creates accounts or
tokens. The files sent are exactly the template export (developer/template.py): no node_modules,
no build output, no .env. The token travels in a request header only, never in a URL, a log or
a git remote.
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import shutil
import tempfile
import unicodedata
from pathlib import Path

import httpx
from pydantic import BaseModel

from chromaswarm.developer.template import SKIP_DIRS, SKIP_FILES

VERCEL_API = "https://api.vercel.com"
GITHUB_API = "https://api.github.com"
MAX_BYTES = 40 * 1024 * 1024  # inline deployment payload cap
DESCRIPTION = "Trang dựng bằng ChromaSwarm"
REPO_NAME = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class PublishError(RuntimeError):
    """A failure the Studio shows as is (Vietnamese, no secrets)."""


class Published(BaseModel):
    target: str  # vercel | github
    url: str
    state: str = "ready"  # vercel: ready | building | error
    detail: str = ""


def app_files(app_dir: Path) -> list[tuple[str, bytes]]:
    out, total = [], 0
    for path in sorted(app_dir.rglob("*")):
        rel = path.relative_to(app_dir)
        if path.is_dir() or path.is_symlink() or SKIP_DIRS & set(rel.parts) or SKIP_FILES.search(path.name):
            continue
        if path.name.startswith(".env"):
            continue
        data = path.read_bytes()
        total += len(data)
        if total > MAX_BYTES:
            raise PublishError("Trang có quá nhiều dữ liệu để xuất bản trực tiếp (trên 40 MB) — bạn giảm dung lượng ảnh nhé.")
        out.append((rel.as_posix(), data))
    return out


def slug(name: str) -> str:
    """URL-safe project name: "Cây cảnh mini" -> "cay-canh-mini"."""
    folded = unicodedata.normalize("NFD", name.lower().replace("đ", "d"))
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    s = re.sub(r"[^a-z0-9-]+", "-", folded).strip("-")
    return (s or "chromaswarm-site")[:90]


def token(name: str, env: dict[str, str] | None = None) -> str:
    value = (dict(os.environ if env is None else env).get(name) or "").strip()
    if not value:
        where = {"VERCEL_TOKEN": "vercel.com/account/tokens", "GITHUB_TOKEN": "github.com/settings/tokens (quyền repo)"}[name]
        raise PublishError(f"Chưa có {name}. Bạn tạo token ở {where}, thêm dòng {name}=... vào backend/.env rồi khởi động lại backend.")
    return value


# ----------------------------------------------------------------- Vercel

async def vercel(app_dir: Path, name: str, env: dict[str, str] | None = None,
                 client: httpx.AsyncClient | None = None, wait_s: float = 120, poll_s: float = 3) -> Published:
    """Create a production deployment from the app's files and wait until Vercel has built it."""
    tok = token("VERCEL_TOKEN", env)
    team = (dict(os.environ if env is None else env).get("VERCEL_TEAM_ID") or "").strip()
    params = {"teamId": team} if team else {}
    files = [{"file": rel, "data": base64.b64encode(data).decode(), "encoding": "base64"} for rel, data in app_files(app_dir)]
    body = {"name": slug(name), "files": files, "target": "production",
            "projectSettings": {"framework": "nextjs"}}
    own = client is None
    client = client or httpx.AsyncClient(timeout=60)
    headers = {"Authorization": f"Bearer {tok}"}
    try:
        r = await client.post(f"{VERCEL_API}/v13/deployments", params=params, json=body, headers=headers)
        if r.status_code in (401, 403):
            raise PublishError("Vercel từ chối token (hết hạn hoặc thiếu quyền). Bạn tạo token mới rồi thử lại.")
        if r.status_code >= 400:
            raise PublishError(f"Vercel báo lỗi {r.status_code}: {_message(r)}")
        dep = r.json()
        url = "https://" + dep["url"]
        deadline = asyncio.get_running_loop().time() + wait_s
        state = dep.get("readyState", "QUEUED")
        while state not in ("READY", "ERROR", "CANCELED") and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(poll_s)
            s = await client.get(f"{VERCEL_API}/v13/deployments/{dep['id']}", params=params, headers=headers)
            if s.status_code < 400:
                state = s.json().get("readyState", state)
        alias = next(iter(dep.get("alias") or []), None)
        if state == "READY":
            return Published(target="vercel", url=f"https://{alias}" if alias else url)
        if state in ("ERROR", "CANCELED"):
            return Published(target="vercel", url=url, state="error",
                             detail="Vercel dựng trang không thành công — mở link để xem nhật ký dựng.")
        return Published(target="vercel", url=url, state="building", detail="Vercel vẫn đang dựng trang, mở link sau ít phút.")
    except httpx.HTTPError as e:
        raise PublishError(f"Không kết nối được tới Vercel: {type(e).__name__}") from None
    finally:
        if own:
            await client.aclose()


def _message(r: httpx.Response) -> str:
    try:
        data = r.json()
    except ValueError:
        return r.text[:160]
    err = data.get("error") if isinstance(data, dict) else None
    return str((err or {}).get("message") if isinstance(err, dict) else data.get("message") or data)[:160]


# ----------------------------------------------------------------- GitHub

async def github(app_dir: Path, name: str, env: dict[str, str] | None = None,
                 client: httpx.AsyncClient | None = None, git=None) -> Published:
    """A private repository under the token's account (created if missing) with the app as one commit."""
    tok = token("GITHUB_TOKEN", env)
    repo = slug(name)
    if not REPO_NAME.match(repo):
        raise PublishError("Tên repository không hợp lệ.")
    own = client is None
    client = client or httpx.AsyncClient(timeout=30)
    headers = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    try:
        me = await client.get(f"{GITHUB_API}/user", headers=headers)
        if me.status_code in (401, 403):
            raise PublishError("GitHub từ chối token (hết hạn hoặc thiếu quyền repo).")
        owner = me.json()["login"]
        r = await client.post(f"{GITHUB_API}/user/repos", headers=headers,
                              json={"name": repo, "private": True, "description": DESCRIPTION})
        if r.status_code == 422:  # the name is taken: only a repository this tool made is updated
            r = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=headers)
            if r.status_code < 400 and r.json().get("description") != DESCRIPTION:
                raise PublishError(f"Tài khoản GitHub đã có repository “{repo}” không do ChromaSwarm tạo — "
                                   "Chroma không ghi đè. Bạn đặt tên khác rồi thử lại.")
        if r.status_code >= 400:
            raise PublishError(f"GitHub báo lỗi {r.status_code}: {_message(r)}")
        info = r.json()
    except httpx.HTTPError as e:
        raise PublishError(f"Không kết nối được tới GitHub: {type(e).__name__}") from None
    finally:
        if own:
            await client.aclose()
    await (git or push_with_git)(app_dir, info["clone_url"], tok, info.get("default_branch") or "main")
    return Published(target="github", url=info["html_url"])


async def push_with_git(app_dir: Path, clone_url: str, tok: str, branch: str) -> None:
    """Copy the app's files to a fresh folder, commit them and push. The token goes in an
    http.extraHeader for this one command, never in the remote URL or the repository config."""
    if not shutil.which("git"):
        raise PublishError("Máy chủ chưa cài git.")
    basic = base64.b64encode(f"x-access-token:{tok}".encode()).decode()
    with tempfile.TemporaryDirectory(prefix="chromaswarm-publish-") as tmp:
        root = Path(tmp)
        for rel, data in app_files(app_dir):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(data)
        (root / ".gitignore").write_text("node_modules/\n.next/\n.env*\ndata/\n", encoding="utf-8")
        steps = [["git", "init", "-q", "-b", branch], ["git", "add", "-A"],
                 ["git", "-c", "user.name=ChromaSwarm", "-c", "user.email=chromaswarm@users.noreply.github.com",
                  "commit", "-q", "-m", "Trang dựng bằng ChromaSwarm"],
                 ["git", "-c", f"http.extraHeader=Authorization: Basic {basic}", "push", "-q", "--force", clone_url, f"HEAD:{branch}"]]
        for cmd in steps:
            proc = await asyncio.create_subprocess_exec(*cmd, cwd=root, stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.STDOUT,
                                                        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
            out, _ = await proc.communicate()
            if proc.returncode:
                text = out.decode(errors="replace").replace(tok, "***").replace(basic, "***")
                raise PublishError(f"Đẩy code lên GitHub không thành công: {text[-200:]}")
