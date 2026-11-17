"""B8.1 Motion via a real MCP round trip (stdio server <-> client)."""

import asyncio

import pytest

from chromaswarm.mcp_motion.client import MotionError, build_effects, server_params
from chromaswarm.mcp_motion.server import build_effect, pick_effect


def test_mcp_round_trip_returns_scoped_reduced_motion_css():
    fx = asyncio.run(build_effects([("reveal", "hero"), ("parallax", "feature-story")], 600,
                                   "cubic-bezier(0.16, 1, 0.3, 1)", page="landing"))
    assert [f.effect for f in fx] == ["reveal", "parallax"] and all(f.kind == "2d-css" for f in fx)
    reveal, parallax = fx[0].css, fx[1].css
    assert '[data-swarm-page="landing"] [data-swarm-section="hero"]' in reveal
    assert "prefers-reduced-motion" in reveal and "prefers-reduced-motion" in parallax
    assert "to { opacity: 1" in reveal  # ends visible: B11 "stuck at opacity 0" stays green
    assert "animation-timeline: view()" in parallax and "@supports" in parallax


def test_unknown_effect_is_an_mcp_error():
    with pytest.raises(MotionError):
        asyncio.run(build_effects([("explode", "hero")], 600, "ease"))


def test_server_rejects_selector_injection():
    assert "error" in build_effect("reveal", 'hero"] body { display:none } [x="', 600, "ease")
    assert "error" in build_effect("reveal", "hero", 600, "ease; } body { display:none")


def test_plan_effects_map_to_catalogue():
    assert pick_effect("subtle entrance reveal") == "reveal"
    assert pick_effect("scroll-triggered image parallax") == "parallax"
    assert pick_effect("confetti") is None


def test_external_server_can_be_configured():
    p = server_params({"CHROMASWARM_MOTION_MCP": "npx some-motion-mcp --stdio"})
    assert p.command == "npx" and p.args == ["some-motion-mcp", "--stdio"]


def test_clone_effects_are_built_as_scoped_reduced_motion_safe_css():
    from chromaswarm.mcp_motion.server import BUILDERS, build_effect
    for effect in ("scroll-reveal", "marquee", "hover-lift", "hover-zoom", "hover-image", "underline-link",
                   "sticky-blur", "smooth-scroll"):
        out = build_effect(effect, "hero", 400, "ease", page="clone")
        assert "error" not in out and out["css"], effect
        if effect not in ("smooth-scroll",):
            assert '[data-swarm-page="clone"] [data-swarm-section="hero"]' in out["css"], effect
        if effect not in ("sticky-blur",):
            assert "prefers-reduced-motion" in out["css"], effect
    assert set(BUILDERS) >= {"reveal", "parallax", "stagger-cards"}  # the Creative effects are still there


def test_hover_and_reveal_readings_map_onto_effects():
    from chromaswarm.clone.motion import assign, hover_effects
    still = {"tf": "none", "shadow": "none", "bgSize": "auto", "deco": "none", "border": "0px none", "imgTf": "none",
             "visibleImages": 3, "top": 100}
    lifted = {**still, "tf": "matrix(1, 0, 0, 1, 0, -4)", "shadow": "rgba(0, 0, 0, 0.1) 0px 8px 24px 0px"}
    assert hover_effects("card", still, lifted) == ["hover-lift"]
    assert "hover-zoom" in hover_effects("card", still, {**still, "imgTf": "matrix(1.05, 0, 0, 1.05, 0, 0)"})
    assert hover_effects("row", still, {**still, "visibleImages": 4}) == ["hover-image"]
    assert hover_effects("link", still, {**still, "bgSize": "100% 1px"}) == ["underline-link"]
    assert hover_effects("button", still, still) == []
    blocks = [{"features": {"top": 0, "height": 500, "index": 0}}, {"features": {"top": 500, "height": 800, "index": 1}},
              {"features": {"top": 1300, "height": 300, "index": 2}}]
    post = {"revealed": [{"top": 600 + i * 10, "h": 50, "parent": 1} for i in range(4)] + [{"top": 1350, "h": 40, "parent": 2}],
            "marquee": [{"top": 1320, "h": 80}], "hover": [{"top": 700, "h": 100, "effects": ["hover-lift"]}],
            "sticky": True, "smooth": True, "libs": ["Lenis"], "unsupported": []}
    facts = assign(blocks, post, [{"top": 520, "h": 300, "drift": -40}])
    assert blocks[1]["features"]["motion"] == ["stagger-cards", "parallax", "hover-lift"]
    assert blocks[2]["features"]["motion"] == ["scroll-reveal", "marquee"] and blocks[0]["features"]["motion"] == []
    assert facts["smooth"] and facts["libs"] == ["Lenis"]
