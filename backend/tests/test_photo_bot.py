"""Photo bot: queries from the brief, free-license search, vision check validated in code."""

import pytest

from chromaswarm.developer.content import build_copy
from chromaswarm.developer.photo_bot import PhotoBot, check_keep, credit_line
from chromaswarm.state_machine.pipeline_state import Domain, PipelineState, Pillars


def state(**kw) -> PipelineState:
    return PipelineState(session_id="b", raw_prompt="landing page bán trà ô long Đài Loan", domain=Domain.ECOMMERCE,
                         selected_page="landing", pillars=Pillars(theme="editorial-luxury", layout="narrative",
                                                                   color="warm-paper", margins="airy",
                                                                   scope="Dân văn phòng, muốn họ bấm Đặt mua"), **kw)


class Chat:
    model = "fake"

    def __init__(self, reply):
        self.reply, self.images = reply, None

    def complete_json(self, system, user, images=None, max_tokens=1500):
        self.images = images
        return self.reply


def found(n):
    return [{"url": f"https://x/{i}.jpg", "thumb": f"https://x/t{i}.jpg", "creator": f"A{i}", "license": "CC BY",
             "source": "", "needs_credit": i % 2 == 0} for i in range(n)]


CURATED = ["https://images.unsplash.com/c1?q=80", "https://images.unsplash.com/c2?q=80"]


@pytest.fixture(autouse=True)
def curated(monkeypatch):
    monkeypatch.setattr("chromaswarm.developer.photo_bot.stock_photos", lambda text, domain: CURATED)


SHOW = lambda cs: [(c, c["thumb"]) for c in cs]
PLAN = {"queries": ["oolong tea leaves", "taiwan tea plantation"], "must_show": "oolong tea", "must_not": "matcha"}


def test_one_approved_photo_leads_and_curated_photos_fill():
    out = PhotoBot(Chat(PLAN), Chat({"keep": [12]}), searcher=lambda q: found(10), fetcher=SHOW)(state())
    assert out[0]["url"] == "https://x/9.jpg" and len(out) == 3
    assert all(x["url"].startswith("https://images.unsplash.com/") for x in out[1:])


def test_without_curated_photos_one_approved_photo_is_enough_and_a_second_look_is_taken(monkeypatch):
    monkeypatch.setattr("chromaswarm.developer.photo_bot.stock_photos", lambda text, domain: [])

    class TwoLooks(Chat):
        def __init__(self):
            super().__init__(None)
            self.calls = 0

        def complete_json(self, system, user, images=None, max_tokens=1500):
            self.calls += 1
            return {"keep": []} if self.calls == 1 else {"keep": [4]}
    vision = TwoLooks()
    out = PhotoBot(Chat(PLAN), vision, searcher=lambda q: found(6), fetcher=SHOW)(state())
    assert vision.calls == 2 and [x["url"] for x in out] == ["https://x/3.jpg"]


def test_bot_keeps_the_photos_the_vision_model_approved_in_its_order():
    vision = Chat({"keep": [7, 4, 4, 11, 99, 3], "why": "ok"})
    bot = PhotoBot(Chat(PLAN), vision, searcher=lambda q: found(10), fetcher=SHOW)
    out = bot(state())
    assert [x["url"] for x in out] == ["https://x/4.jpg", "https://x/1.jpg", "https://x/8.jpg", "https://x/0.jpg"]
    assert len(vision.images) == 12  # it looked at every candidate


@pytest.mark.parametrize("plan, n, keep", [
    ({"queries": []}, 10, [1, 2, 3]),          # no queries
    (PLAN, 0, [1, 2]),                          # too few candidates (only the 2 curated ones)
    (PLAN, 10, []),                             # nothing approved
    (PLAN, 10, "all"),                          # malformed verdict
])
def test_bot_falls_back_to_curated_photos(plan, n, keep):
    assert PhotoBot(Chat(plan), Chat({"keep": keep}), searcher=lambda q: found(n), fetcher=SHOW)(state()) is None


def test_check_keep_bounds():
    assert check_keep({"keep": ["3", 1, 2, 2]}, 3) == [2, 0, 1]
    with pytest.raises(ValueError):
        check_keep({"keep": [7, 8, 9]}, 3)
    assert check_keep({"keep": [2]}, 3) == [1]  # one approved photo is kept; curated photos fill the rest


def test_page_uses_bot_photos_and_credits_cc_by_authors():
    st = state(page_photos=found(4))
    copy = build_copy(st)
    assert copy.images == [f"https://x/{i}.jpg" for i in range(4)]
    assert "A0" in copy.footer_line and "A2" in copy.footer_line and "A1" not in copy.footer_line
    assert credit_line([{"creator": "B", "needs_credit": False}]) == ""
    assert build_copy(state()).images[0].startswith("https://images.unsplash.com/")  # no bot -> curated
