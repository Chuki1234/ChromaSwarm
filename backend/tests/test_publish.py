"""Publishing (developer/publish.py) against fake Vercel and GitHub APIs — no network, no real token."""

import asyncio
import base64
import json

import httpx
import pytest

from chromaswarm.developer import publish


def app(tmp_path):
    root = tmp_path / "app"
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text("{}")
    (root / "app" / "page.tsx").write_text("export default function P() { return null; }")
    (root / ".env.local").write_text("SECRET=1")
    (root / "node_modules" / "x").mkdir(parents=True, exist_ok=True)
    (root / "node_modules" / "x" / "i.js").write_text("big")
    return root


def test_only_template_files_are_sent(tmp_path):
    names = [rel for rel, _ in publish.app_files(app(tmp_path))]
    assert names == ["app/page.tsx", "package.json"]


def test_missing_token_explains_where_to_put_it(tmp_path):
    with pytest.raises(publish.PublishError, match="VERCEL_TOKEN=.*backend/.env"):
        asyncio.run(publish.vercel(app(tmp_path), "Shop", env={}))


def test_vercel_deploys_and_waits_until_ready(tmp_path):
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        assert req.headers["authorization"] == "Bearer tok-1" and "tok-1" not in str(req.url)
        if req.method == "POST":
            body = json.loads(req.content)
            assert body["name"] == "cay-canh-mini" and body["projectSettings"]["framework"] == "nextjs"
            assert {f["file"] for f in body["files"]} == {"app/page.tsx", "package.json"}
            assert base64.b64decode(body["files"][1]["data"]) == b"{}"
            return httpx.Response(200, json={"id": "dpl_1", "url": "cay-canh-mini-abc.vercel.app", "readyState": "BUILDING",
                                             "alias": ["cay-canh-mini.vercel.app"]})
        return httpx.Response(200, json={"readyState": "READY"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    out = asyncio.run(publish.vercel(app(tmp_path), "Cây cảnh mini", env={"VERCEL_TOKEN": "tok-1"}, client=client, poll_s=0))
    assert out.url == "https://cay-canh-mini.vercel.app" and out.state == "ready" and len(seen) == 2


def test_vercel_rejected_token_is_explained(tmp_path):
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(403, json={})))
    with pytest.raises(publish.PublishError, match="token"):
        asyncio.run(publish.vercel(app(tmp_path), "x", env={"VERCEL_TOKEN": "t"}, client=client))


def gh(existing_description=None):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/user":
            return httpx.Response(200, json={"login": "me"})
        if req.method == "POST":
            if existing_description is not None:
                return httpx.Response(422, json={"message": "name already exists"})
            assert json.loads(req.content)["private"] is True
            return httpx.Response(201, json={"clone_url": "https://github.com/me/shop.git", "html_url": "https://github.com/me/shop"})
        return httpx.Response(200, json={"clone_url": "https://github.com/me/shop.git", "html_url": "https://github.com/me/shop",
                                         "description": existing_description})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_github_creates_a_private_repo_and_pushes(tmp_path):
    pushed = []

    async def git(app_dir, url, tok, branch):
        pushed.append((url, tok, branch))

    out = asyncio.run(publish.github(app(tmp_path), "Shop", env={"GITHUB_TOKEN": "g"}, client=gh(), git=git))
    assert out.url == "https://github.com/me/shop" and pushed == [("https://github.com/me/shop.git", "g", "main")]


def test_github_never_overwrites_a_repo_it_did_not_make(tmp_path):
    async def git(*a):
        raise AssertionError("must not push")

    with pytest.raises(publish.PublishError, match="không ghi đè"):
        asyncio.run(publish.github(app(tmp_path), "Shop", env={"GITHUB_TOKEN": "g"}, client=gh("my real project"), git=git))
    pushed = []

    async def ok(*a):
        pushed.append(a)

    asyncio.run(publish.github(app(tmp_path), "Shop", env={"GITHUB_TOKEN": "g"}, client=gh(publish.DESCRIPTION), git=ok))
    assert pushed  # our own earlier export is updated


def test_git_push_keeps_the_token_out_of_the_remote(tmp_path):
    bare = tmp_path / "remote.git"
    asyncio.run(_git("init", "-q", "--bare", str(bare)))
    asyncio.run(publish.push_with_git(app(tmp_path), str(bare), "secret-token", "main"))
    log = asyncio.run(_git("--git-dir", str(bare), "log", "--format=%s", "main"))
    files = asyncio.run(_git("--git-dir", str(bare), "ls-tree", "-r", "--name-only", "main"))
    assert "ChromaSwarm" in log and ".env.local" not in files and "app/page.tsx" in files
    assert "secret-token" not in (bare / "config").read_text()


async def _git(*args):
    proc = await asyncio.create_subprocess_exec("git", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await proc.communicate()
    assert proc.returncode == 0, out
    return out.decode()
