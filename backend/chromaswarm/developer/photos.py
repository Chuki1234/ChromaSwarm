"""Stock photography for generated pages (FRONTEND_STANDARDS §1.3: never empty grey boxes).

Real photos are the single biggest difference between our pages and the modern
references (knowledge-base/MODERN_UI_REFERENCES.md, pattern 1). When the user
has not uploaded product photos, the page uses free-license Unsplash photos
picked by topic from what the user said (prompt, brand, audience), with the
domain as a fallback.

Every id below was taken from unsplash.com search with `license=free` (no
Unsplash+ images, which live on plus.unsplash.com) and checked by eye on
2026-11-13 for topic fit. The Unsplash License allows free commercial use and
hotlinking from images.unsplash.com. The first photo of each topic suits a wide
hero crop. `CHROMASWARM_STOCK_PHOTOS=0` turns stock photos off (tonal
placeholders instead), e.g. for offline work.
"""

from __future__ import annotations

import os
import re

from chromaswarm.agents.consultant import fold
from chromaswarm.state_machine.pipeline_state import Domain

CDN = "https://images.unsplash.com/"

# topic -> (keywords matched on accent-folded text, photo ids)
TOPICS: dict[str, tuple[list[str], list[str]]] = {
    "coffee": (["cà phê", "cafe", "coffee", "espresso", "rang xay", "barista"],
               ["photo-1497935586351-b67a49e012bf", "photo-1511920170033-f8396924c348", "photo-1447933601403-0c6688de566e",
                "photo-1587734195503-904fca47e0e9", "photo-1610632380989-680fe40816c6"]),
    "tea": (["trà", "matcha", "tea", "trà sữa"],
            ["photo-1565117661210-fd54898de423", "photo-1515823064-d6e0c04616a7", "photo-1766426910014-63a302fa137e",
             "photo-1589698272390-0501a07619bb", "photo-1785711571852-8edfd71e92ef", "photo-1624893578106-a98840591afc"]),
    "bakery": (["tiệm bánh", "bánh ngọt", "bánh mì", "bánh kem", "bakery", "pastry", "cake", "bánh"],
               ["photo-1568254183919-78a4f43a2877", "photo-1597528662465-55ece5734101", "photo-1608198093002-ad4e005484ec",
                "photo-1534432182912-63863115e106", "photo-1547398847-19d7560a6257", "photo-1583338917451-face2751d8d5"]),
    "restaurant": (["nhà hàng", "quán ăn", "món ăn", "ẩm thực", "đồ ăn", "restaurant", "food", "bistro"],
                   ["photo-1682264933304-1943bfa8df38", "photo-1663530761401-15eefb544889", "photo-1676471926534-d5c9771909fa",
                    "photo-1627858034922-72a657d6b3c2", "photo-1684568519316-f0fb02f7826b", "photo-1681270543584-8e541a1bb056"]),
    "fashion": (["thời trang", "quần áo", "áo", "váy", "đầm", "fashion", "clothing", "giày", "túi xách"],
                ["photo-1558769132-cb1aea458c5e", "photo-1767968037382-8eb9c564339f", "photo-1483985988355-763728e1935b",
                 "photo-1562157873-818bc0726f68", "photo-1601762603339-fd61e28b698a", "photo-1529139574466-a303027c1d8b"]),
    "furniture": (["nội thất", "sofa", "bàn ghế", "furniture", "interior", "decor", "trang trí nhà"],
                  ["photo-1724582586458-a51791349977", "photo-1758486561455-ebd0d3ba7423", "photo-1567016376408-0226e4d0c1ea",
                   "photo-1547587091-f883cf8f0c12", "photo-1523755231516-e43fd2e8dca5", "photo-1762544968153-b9b47435fefd"]),
    "skincare": (["mỹ phẩm", "skincare", "chăm sóc da", "serum", "cosmetic", "kem dưỡng", "son môi"],
                 ["photo-1608571423902-eed4a5ad8108", "photo-1580870069867-74c57ee1bb07", "photo-1620916566398-39f1143ab7be",
                  "photo-1552046122-03184de85e08", "photo-1785581778868-79100f7fe56c", "photo-1764694187667-f28a05a52c0e"]),
    "tech": (["máy tính", "laptop", "computer", "pc", "công nghệ", "điện tử", "màn hình", "linh kiện", "tech"],
             ["photo-1499951360447-b19be8fe80f5", "photo-1618410325698-018bb3eb2318", "photo-1575318634028-6a0cfcb60c59",
              "photo-1530893609608-32a9af3aa95c", "photo-1616868560403-b4675d3a545b", "photo-1626968361222-291e74711449"]),
    "audio": (["tai nghe", "loa", "âm thanh", "headphone", "speaker", "audio"],
              # dark, premium product shots: two saturated yellow flat-lays were dropped (design critic:
              # they clashed with precision-tech palettes)
              ["photo-1546435770-a3e426bf472b", "photo-1641048930621-ab5d225ae5b0", "photo-1618366712010-f4ae9c647dcb",
               "photo-1487215078519-e21cc028cb29", "photo-1583394838336-acd977736f90", "photo-1520170350707-b2da59970118"]),
    "spa": (["spa", "massage", "wellness", "xông hơi", "trị liệu"],
            ["photo-1773924093206-9a433a14bb44", "photo-1706795033917-dee116e7cba2", "photo-1600334089648-b0d9d3028eb2",
             "photo-1696841212541-449ca29397cc", "photo-1630168258841-ea0ae143ee1f", "photo-1729003702131-51807464dcec"]),
    "salon": (["salon", "cắt tóc", "làm tóc", "tóc", "barber", "nail", "làm đẹp"],
              ["photo-1781450090585-1a511b7066d9", "photo-1600948836101-f9ffda59d250", "photo-1580618672591-eb180b1a973f",
               "photo-1605497788044-5a32c7078486", "photo-1521590832167-7bcbfaa6381f", "photo-1634449571010-02389ed0f9b0"]),
    "fitness": (["gym", "fitness", "thể hình", "yoga", "tập luyện", "thể thao", "pt"],
                ["photo-1757924284732-4189190321cf", "photo-1571902943202-507ec2618e8f", "photo-1534438327276-14e5300c3a48",
                 "photo-1517836357463-d25dfeac3438", "photo-1623874514711-0f321325f318", "photo-1722925541142-5db2668ca492"]),
    "education": (["khóa học", "khoá học", "lớp học", "học online", "course", "edtech", "luyện thi", "tiếng anh", ],
                  ["photo-1522202176988-66273c2fd55f", "photo-1784359065403-93da31c36115", "photo-1516321497487-e288fb19713f",
                   "photo-1514369118554-e20d93546b30", "photo-1460518451285-97b6aa326961", "photo-1571260899304-425eee4c7efc"]),
    "office": (["saas", "phần mềm", "dashboard", "quản lý", "crm", "startup", "ứng dụng", "app"],
               ["photo-1522071820081-009f0129c71c", "photo-1758691737124-05c5bffe46f0", "photo-1603201667230-bd139210db18",
                "photo-1770777843445-2a1621b1201d", "photo-1553028826-f4804a6dba3b", "photo-1779896411967-c35d5dade32f"]),
    "hotel": (["khách sạn", "homestay", "resort", "hotel", "villa", "phòng nghỉ", "du lịch"],
              ["photo-1611892440504-42a792e24d32", "photo-1618773928121-c32242e63f39", "photo-1781572725438-ac8c41476752",
               "photo-1782890790046-2aefb0b503cb", "photo-1765547090903-348b711f0eee", "photo-1551882547-ff40c63fe5fa"]),
    "candle": (["nến thơm", "nến", "candle", "sáp thơm", "tinh dầu"],
               # checked by eye 2026-11-14 (license=free). Pillar candles first: the subject fills the frame, so
               # the 21:9 hero crop still shows candles (the amber-jar photo cropped to an empty wall).
               ["photo-1613068431228-8cb6a1e92573", "photo-1612293905607-b003de9e54fb", "photo-1605651202774-7d573fd3f12d",
                "photo-1772915022472-ffc1df2d6051", "photo-1572726729207-a78d6feb18d7", "photo-1759262151253-375c311347c7"]),
    "flowers": (["hoa", "điện hoa", "florist", "flower", "bó hoa"],
                ["photo-1572454591674-2739f30d8c40", "photo-1561848355-890d054dc55a", "photo-1523694576729-dc99e9c0f9b4",
                 "photo-1487530811176-3780de880c2d", "photo-1778101410311-6cca527142d6", "photo-1762969217496-32d784e7e557"]),
    "jewelry": (["trang sức", "nhẫn", "dây chuyền", "bông tai", "jewelry", "vàng bạc"],
                ["photo-1617038220319-276d3cfab638", "photo-1543294001-f7cd5d7fb516", "photo-1782400027969-a4970b076eb1",
                 "photo-1631982690223-8aa4be0a2497", "photo-1535632066927-ab7c9ab60908", "photo-1585960622850-ed33c41d6418"]),
    "studio": (["portfolio", "thiết kế", "designer", "studio", "hồ sơ cá nhân", "freelancer", "nhiếp ảnh"],
               ["photo-1487338875411-8880f74114a2", "photo-1504608245011-62d9758c1bb9", "photo-1509774251289-92e35f5f03ec",
                "photo-1551902675-a415b7df1ba1", "photo-1733381919300-e49929a82a5b", "photo-1677111105589-18eb5ca22aba"]),
}

# No keyword hit: a topic that matches the domain's default sample copy.
# A shop selling something we have no photos for gets neutral placeholders, never another product's
# photos: a candle shop full of sofas scored worse with the critic than plain tonal frames.
DOMAIN_TOPIC: dict[Domain, str] = {
    Domain.SAAS: "office",
    Domain.BOOKING: "spa",
    Domain.EDTECH: "education",
    Domain.PORTFOLIO: "studio",
}


def enabled() -> bool:
    return os.environ.get("CHROMASWARM_STOCK_PHOTOS", "1") != "0"


def _find(word: str, text: str, folded: str) -> re.Match | None:
    """Exact (with diacritics) match always; accent-folded match only for long or multi-word
    keywords, because folding short words collides: trà~"kiểm tra", nhẫn~"nhận", hoa~"hàng hóa"."""
    if m := re.search(rf"\b{re.escape(word.lower())}\b", text):
        return m
    if " " in word or len(fold(word)) >= 6:
        return re.search(rf"\b{re.escape(fold(word))}\b", folded)
    return None


# Phrases that contain a topic keyword but are not about it: "thương mại điện tử" (e-commerce)
# is not electronics, "ứng dụng" in "ứng dụng thanh toán" is not an app product, etc.
NOT_TOPICS = re.compile(r"thương mại điện tử|thuong mai dien tu|e-?commerce|sàn điện tử|ví điện tử|hóa đơn điện tử|"
                        r"hoá đơn điện tử|chữ ký điện tử|thư điện tử|giao diện|màn hình điện thoại", re.I)


def pick_topic(text: str, domain: Domain | None) -> str | None:
    """The topic the user talks about most (keyword hits); the earliest mention breaks a tie.
    Domain fallback when nothing matches."""
    text = NOT_TOPICS.sub(" ", text)
    low, folded = text.lower(), fold(text)
    scores: dict[str, list] = {}
    for topic, (words, _) in TOPICS.items():
        for w in words:
            hits = list(re.finditer(rf"\b{re.escape(w.lower())}\b", low)) or (
                [m] if (m := _find(w, low, folded)) else [])
            if hits:
                s = scores.setdefault(topic, [0, len(low), 0])
                s[0] += len(hits)
                s[1] = min(s[1], hits[0].start())
                s[2] = max(s[2], len(w))
    if scores:
        # most hits, then earliest mention, then the longer (more specific) keyword
        return min(scores, key=lambda t: (-scores[t][0], scores[t][1], -scores[t][2]))
    return DOMAIN_TOPIC.get(domain) if domain else None


def stock_photos(text: str, domain: Domain | None) -> list[str]:
    """Base URLs (the Art component adds width / srcset parameters)."""
    if not enabled():
        return []
    topic = pick_topic(text, domain)
    if not topic:
        return []
    return [f"{CDN}{pid}?auto=format&fit=crop&q=80" for pid in TOPICS[topic][1]]
