"""Structure clone of a picture/text-led page (portfolios, galleries): what the user should bring.

A structure clone never copies the owner's photos or words, so on a page whose look is mostly its
photos and copy the rebuild looks clearly different. Before planning, Chroma says so and lists the
slots the reference fills — the big hero picture, one per project, the portrait, the name and lines —
so the user can bring similar photos and words of their own and get close to the reference.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

from pydantic import BaseModel

from chromaswarm.agents.planner import Section

MEDIA_SHARE_HIGH = 0.35  # over a third of the page area is pictures
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGES = 24
_IMAGE_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/avif": ".avif", "image/gif": ".gif"}


class Slot(BaseModel):
    id: str
    label: str
    count: int
    hint: str


TEXT_FIELDS = [
    ("name", "Tên của bạn / thương hiệu"),
    ("headline", "Câu tiêu đề lớn ở đầu trang (bạn làm gì, cho ai)"),
    ("intro", "Một hai câu giới thiệu"),
    ("projects", "Tên các dự án / sản phẩm, mỗi dòng một tên"),
    ("email", "Email liên hệ"),
]


def image_slots(sections: list[Section]) -> list[Slot]:
    """Picture slots of the rebuild, in page order (the order photos are used in)."""
    out: list[Slot] = []
    for s in sections:
        k = s.structure
        if k in ("full-bleed-image", "split-7-5"):
            out.append(Slot(id=s.id, label="Ảnh lớn đầu trang", count=1, hint="ngang, khoảng 1600×1000px"))
        elif k == "feature-showcase":
            out.append(Slot(id=s.id, label="Ảnh dự án nổi bật", count=1, hint="ngang 16:7, ảnh chụp sản phẩm / màn hình"))
        elif k in ("bento", "grid-4", "horizontal-scroller"):
            out.append(Slot(id=s.id, label="Ảnh thẻ dự án / sản phẩm", count=max(3, min(s.count or 4, 8)), hint="4:3 hoặc vuông"))
        elif k == "gallery":
            out.append(Slot(id=s.id, label="Ảnh thư viện", count=max(3, min(s.count or 6, 12)), hint="4:3"))
        elif k == "alternating-z":
            out.append(Slot(id=s.id, label="Ảnh minh hoạ từng đoạn", count=3, hint="3:2"))
        elif k == "list-rows" and "hover-image" in s.motion:
            out.append(Slot(id=s.id, label="Ảnh xem trước khi rê chuột lên từng dòng", count=5, hint="4:3"))
    return out


def needs_content(sections: list[Section], media_share: float, portfolio: bool) -> bool:
    """The reference's look depends on its own photos and words: warn and ask for similar ones."""
    pictures = sum(sl.count for sl in image_slots(sections))
    # Many picture slots alone is not enough (feature cards with small illustrations): pictures must also
    # take a real share of the page.
    # Only pages whose look IS their photos (portfolios, galleries): elsewhere the rebuild keeps exact-size
    # skeletons where the owner's pictures were, and nobody is asked for product screenshots.
    return portfolio or media_share >= MEDIA_SHARE_HIGH


def warning(sections: list[Section], media_share: float) -> str:
    pictures = sum(sl.count for sl in image_slots(sections))
    share = f"khoảng {round(media_share * 100)}% diện tích trang là ảnh, " if media_share >= 0.05 else ""
    return (f"Trang mẫu dựa nhiều vào ảnh và chữ: {share}{pictures} chỗ đặt ảnh cùng tên, tiêu đề và mô tả dự án. "
            "Chroma không chép ảnh và nội dung của chủ trang, nên nếu để trống, bản dựng giữ đúng bố cục và hiệu ứng "
            "nhưng nhìn sẽ khác trang mẫu ở chính những phần này. Để giống gần như hoàn toàn, bạn thêm ảnh và nội dung "
            "tương tự của mình theo từng chỗ bên dưới (điền được bao nhiêu thì dùng bấy nhiêu; chỗ trống dùng ảnh và "
            "chữ mẫu, sửa sau trong thư mục content/).")


_DATA_URL = re.compile(r"^data:(image/[a-z+]+);base64,(.+)$", re.S)


def save_images(images: list[dict], folder: Path) -> list[str]:
    """Write the user's photos (data URLs from the Studio) to `folder`; returns the file names in order.
    Anything that is not a reasonably sized image is skipped."""
    folder.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for i, img in enumerate(images[:MAX_IMAGES]):
        m = _DATA_URL.match(str(img.get("data") or ""))
        if not m or m.group(1) not in _IMAGE_EXT:
            continue
        try:
            raw = base64.b64decode(m.group(2), validate=True)
        except ValueError:
            continue
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            continue
        slot = re.sub(r"[^a-z0-9-]", "", str(img.get("slot") or "anh"))[:40] or "anh"
        name = f"{i + 1:02d}-{slot}{_IMAGE_EXT[m.group(1)]}"
        (folder / name).write_bytes(raw)
        names.append(name)
    return names


def clean_texts(texts: dict) -> dict[str, str]:
    keep = {k for k, _ in TEXT_FIELDS}
    return {k: str(v).strip()[:600] for k, v in (texts or {}).items() if k in keep and str(v).strip()}
