"""The user's own files (B4): logo, product photos and reference screenshots.

Files arrive through `POST /sessions/{id}/uploads` and are kept in
`workspaces/<session>/uploads/`. Only raster images are accepted, recognised by
their first bytes (never by the name or the browser's content type): an SVG can
carry script, so a vector logo must be exported as PNG first. Names are made
here (kind + content hash), so a client can never choose a path.

At B9 the uploaded photos and logo are copied into the generated app's
`public/images/`, and the page uses them before any stock or bot photo.
"""

from __future__ import annotations

import hashlib
import re
import struct
from pathlib import Path

from pydantic import BaseModel

KINDS = ("logo", "product-image", "reference")  # what the Studio may upload
GENERATED = "generated"  # written by developer/image_gen.py, never through the upload API
MAX_BYTES = 8 * 1024 * 1024
MAX_FILES = 40  # per session
NAME = re.compile(r"^(logo|product-image|reference|generated)-[0-9a-f]{12}\.(png|jpg|webp|gif)$")
SAFE_SESSION = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
MEDIA = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}


class UploadError(ValueError):
    """A file that is refused, with a message the Studio shows as is."""


class Upload(BaseModel):
    name: str
    kind: str
    path: str  # relative to the session folder: "uploads/<name>"
    width: int | None = None
    height: int | None = None
    bytes: int


def sniff(data: bytes) -> str | None:
    """Image type from the file's own first bytes."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def dimensions(data: bytes, ext: str) -> tuple[int, int] | None:
    """Width and height read from the header (no image library needed); None when unreadable."""
    try:
        if ext == "png":
            return struct.unpack(">II", data[16:24])
        if ext == "gif":
            return struct.unpack("<HH", data[6:10])
        if ext == "webp":
            chunk = data[12:16]
            if chunk == b"VP8X":
                return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
            if chunk == b"VP8 ":
                w, h = struct.unpack("<HH", data[26:30])
                return w & 0x3FFF, h & 0x3FFF
            if chunk == b"VP8L":
                b = int.from_bytes(data[21:25], "little")
                return 1 + (b & 0x3FFF), 1 + ((b >> 14) & 0x3FFF)
        if ext == "jpg":
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    except (struct.error, IndexError):
        return None
    return None


def folder(root: Path, session_id: str) -> Path:
    if not SAFE_SESSION.match(session_id):
        raise UploadError("Phiên làm việc không hợp lệ.")
    return root / session_id / "uploads"


def save(root: Path, session_id: str, kind: str, data: bytes, *, generated: bool = False) -> Upload:
    if kind not in KINDS and not (generated and kind == GENERATED):
        raise UploadError(f"Loại tài nguyên không hợp lệ: {kind!r}.")
    if not data:
        raise UploadError("File rỗng.")
    if len(data) > MAX_BYTES:
        raise UploadError(f"File lớn hơn {MAX_BYTES // (1024 * 1024)} MB — bạn nén ảnh rồi gửi lại nhé.")
    ext = sniff(data)
    if ext is None:
        raise UploadError("Chỉ nhận ảnh PNG, JPG, WebP hoặc GIF. Logo dạng SVG: xuất sang PNG rồi gửi.")
    target = folder(root, session_id)
    target.mkdir(parents=True, exist_ok=True)
    name = f"{kind}-{hashlib.sha256(data).hexdigest()[:12]}.{ext}"
    path = target / name
    if not path.exists():
        if len(list(target.iterdir())) >= MAX_FILES:
            raise UploadError(f"Mỗi phiên nhận tối đa {MAX_FILES} file.")
        path.write_bytes(data)
    size = dimensions(data, ext)
    return Upload(name=name, kind=kind, path=f"uploads/{name}", bytes=len(data),
                  width=size[0] if size else None, height=size[1] if size else None)


def resolve(root: Path, session_id: str, name_or_path: str) -> Path | None:
    """The stored file for a name or "uploads/<name>" given back by the client; None when it is not one."""
    name = name_or_path.removeprefix("uploads/")
    if not NAME.match(name):
        return None
    try:
        path = folder(root, session_id) / name
    except UploadError:
        return None
    return path if path.is_file() else None


def public_path(name_or_path: str) -> str:
    """Where an uploaded file is served inside the generated app."""
    return "/images/" + name_or_path.removeprefix("uploads/")


def media_type(path: Path) -> str:
    return MEDIA.get(path.suffix.lstrip("."), "application/octet-stream")


def is_upload(text: str) -> bool:
    return bool(NAME.match((text or "").strip().removeprefix("uploads/")))


def own_files(state, kind: str) -> list[str]:
    """Uploaded files of one kind among the B4 assets ("uploads/<name>"), in the order given."""
    out = [a.path_or_text.strip() for a in state.assets if a.kind == kind and is_upload(a.path_or_text)]
    return list(dict.fromkeys(p if p.startswith("uploads/") else f"uploads/{p}" for p in out))


def shared_photos(state) -> list[str]:
    """The uploaded photos for the page at large (hero, gallery, cards without their own photo).

    A photo the user attached to one line of their list (B4 real content) belongs to that item only:
    it is left out here, so one product's photo is never repeated on every other card."""
    attached = {i.get("image") for i in (state.real_content or {}).get("items", []) if isinstance(i, dict)}
    return [f for f in own_files(state, "product-image") if f not in attached]
