"""Stock photo topic picking (developer/photos.py)."""

import pytest

from chromaswarm.developer import photos
from chromaswarm.state_machine.pipeline_state import Domain

CASES = [
    ("Trang web bán máy tình", Domain.ECOMMERCE, "tech"),           # typo in the diacritics still matches
    ("web ban may tinh xach tay", Domain.ECOMMERCE, "tech"),        # typed without diacritics
    ("mở tiệm cà phê online", Domain.ECOMMERCE, "coffee"),
    ("trang cho quán cafe của tôi", Domain.BOOKING, "coffee"),
    ("shop thời trang nữ", Domain.ECOMMERCE, "fashion"),
    ("tiệm hoa tươi", Domain.ECOMMERCE, "flowers"),
    ("web bán nhẫn cưới", Domain.ECOMMERCE, "jewelry"),
    ("đặt lịch cắt tóc nam", Domain.BOOKING, "salon"),
    ("khóa học tiếng Anh online", Domain.EDTECH, "education"),
    ("web bán trà sữa", Domain.ECOMMERCE, "tea"),
    ("homestay Đà Lạt", Domain.BOOKING, "hotel"),
    ("mỹ phẩm thiên nhiên", Domain.ECOMMERCE, "skincare"),
    ("portfolio cho designer", Domain.PORTFOLIO, "studio"),
    # folding short words must not collide: tra~"kiểm tra", nhan~"nhận", hoa~"hóa", vay~"váy"
    ("kiểm tra hàng trước khi nhận", Domain.ECOMMERCE, "furniture"),
    ("phần mềm quản lý kho, tự động hóa", Domain.SAAS, "office"),
    ("vay vốn nhanh", Domain.SAAS, "office"),
]


@pytest.mark.parametrize("text, domain, topic", CASES)
def test_topic(text, domain, topic):
    assert photos.pick_topic(text, domain) == topic


def test_every_topic_has_enough_free_unsplash_photos():
    for topic, (_, ids) in photos.TOPICS.items():
        assert len(ids) >= 5, topic
        assert all(i.startswith("photo-") for i in ids), topic  # images.unsplash.com ids, never plus.unsplash.com
    assert len({i for _, ids in photos.TOPICS.values() for i in ids}) == sum(len(ids) for _, ids in photos.TOPICS.values())


def test_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("CHROMASWARM_STOCK_PHOTOS", "0")
    assert photos.stock_photos("web bán cà phê", Domain.ECOMMERCE) == []
