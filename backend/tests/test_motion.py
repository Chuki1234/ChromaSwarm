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
