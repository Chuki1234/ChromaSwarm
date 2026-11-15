"""Accuracy eval for the prompt reader (agents/brief.py) on the live LLM.

`uv run python -m chromaswarm.agents.brief_eval` — reads each prompt and compares the fields the
reader filled with the expected answers. Two kinds of error:
- WRONG: a field filled with a value the user did not say (the worse error: the user is never asked);
- MISSED: the user said it, the reader left it empty (the user is asked again — annoying, not harmful).
A field absent from `expect` must stay empty (anything filled there counts as WRONG).
"""

from __future__ import annotations

import sys
from pathlib import Path

from chromaswarm.agents.brief import Brief, build_brief_reader

FIELDS = ("page", "theme", "layout", "mode", "margins", "accent", "audience", "primary_cta", "assets_said")

# expect: field -> exact value, or "*" = any non-empty value (free text such as the audience)
CASES: list[tuple[str, str, dict]] = [
    ("du-y", "Làm landing page bán nến thơm handmade, phong cách sang trọng, bố cục kể chuyện, nền kem ấm, màu chủ đạo "
             "xanh rêu, thoáng đãng, khách là dân văn phòng 25-35 tuổi chủ yếu xem điện thoại, muốn họ bấm Đặt mua, dùng ảnh Unsplash",
     {"page": "landing", "theme": "editorial-luxury", "layout": "narrative", "mode": "warm-paper", "accent": "#5b6b2f",
      "margins": "airy", "audience": "*", "primary_cta": "Đặt mua", "assets_said": True}),
    ("mo-ho", "mình muốn làm web bán nến thơm handmade", {}),
    ("thieu", "web bán nến thơm cho dân văn phòng 25-35 tuổi, phong cách sang trọng",
     {"theme": "editorial-luxury", "audience": "*"}),
    ("khong-dau", "lam web ban giay sneaker phong cach ca tinh, nen toi, khach la sinh vien 18-25",
     {"theme": "neo-brutalist", "mode": "dark", "audience": "*"}),
    ("phu-dinh-nen", "shop mỹ phẩm, không muốn nền tối, thích tông sáng trong trẻo",
     {"mode": "light"}),
    ("phu-dinh-phong-cach", "web bán đồ gốm, đừng làm kiểu cá tính táo bạo, mình thích thân thiện gần gũi",
     {"theme": "warm-organic"}),
    ("toi-gian", "shop quần áo tối giản, nền trắng, khách là sinh viên",  # "tối giản" = minimalist style, not dark
     {"theme": "editorial-luxury", "mode": "light", "audience": "*"}),
    ("ca-phe-nau", "web bán cà phê nâu rang xay, giao diện hiện đại", {"theme": "precision-tech"}),
    ("spa", "trang đặt lịch spa, muốn khách bấm Đặt lịch ngay, tông tối sang trọng",
     {"theme": "editorial-luxury", "mode": "dark", "primary_cta": "Đặt lịch ngay"}),
    ("tieng-anh", "landing page for a SaaS project management tool, modern clean UI, dark mode, CTA Start free trial",
     {"page": "landing", "theme": "precision-tech", "mode": "dark", "primary_cta": "Start free trial"}),
    ("hex", "web bán trà, màu thương hiệu #2E7D32, nền giấy kem, khách hàng là người 30-50 tuổi",
     {"accent": "#2e7d32", "mode": "warm-paper", "audience": "*"}),
    ("chi-cta", "web khóa học tiếng Anh online, nút chính là Đăng ký học thử", {"primary_cta": "Đăng ký học thử"}),
    ("trang-chu", "làm trang chủ cho shop nội thất gỗ sồi, nhiều sản phẩm, xếp gọn", {"page": "home", "layout": "catalog", "margins": "dense"}),
    ("anh-lon", "web giới thiệu homestay Đà Lạt, ảnh lớn tràn màn hình, thoáng, ấm cúng",
     {"layout": "visual-first", "margins": "airy", "theme": "warm-organic"}),
    ("chua-co-anh", "shop hoa tươi, mình chưa có ảnh sản phẩm, phong cách dễ thương", {"assets_said": True, "theme": "warm-organic"}),
    ("lap-lung", "web bán laptop, có thể sang trọng hoặc hiện đại đều được", {}),
    ("loi-chinh-ta", "trang web bán máy tình, phong cach hien dai, nen sang", {"theme": "precision-tech", "mode": "light"}),
    ("ten-thuong-hieu-mau", "web bán cà phê thương hiệu Nâu Coffee, phong cách ấm áp", {"theme": "warm-organic"}),
    ("muc-tieu-chung", "làm website bán hàng chuyên nghiệp, đẹp, chuẩn SEO", {}),
    ("cta-va-doi-tuong", "portfolio nhiếp ảnh gia, khách là các cặp đôi sắp cưới, muốn họ bấm Liên hệ chụp ảnh",
     {"audience": "*", "primary_cta": "Liên hệ chụp ảnh"}),
]


def score(brief: Brief | None, expect: dict) -> tuple[list[str], list[str]]:
    wrong, missed = [], []
    for f in FIELDS:
        got = getattr(brief, f) if brief else None
        got = got or None
        want = expect.get(f)
        if want is None:
            if got:
                wrong.append(f"{f}={got!r}")
        elif got is None:
            missed.append(f)
        elif want != "*" and (got.lower() if isinstance(got, str) else got) != (want.lower() if isinstance(want, str) else want):
            wrong.append(f"{f}={got!r} (đúng: {want!r})")
    return wrong, missed


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    reader = build_brief_reader()
    total_wrong = total_missed = total_expected = 0
    for name, prompt, expect in CASES:
        b = reader(prompt)
        wrong, missed = score(b, expect)
        total_wrong += len(wrong)
        total_missed += len(missed)
        total_expected += len(expect)
        mark = "OK  " if not wrong and not missed else ("SAI " if wrong else "SÓT ")
        print(f"{mark}{name:22} sai={wrong or '-'} sót={missed or '-'}", flush=True)
    found = total_expected - total_missed
    print(f"\n{len(CASES)} câu · lấy đúng {found}/{total_expected} mục người dùng đã nói · "
          f"lấy SAI {total_wrong} · bỏ sót {total_missed}")
    return 1 if total_wrong else 0


if __name__ == "__main__":
    sys.exit(main())
