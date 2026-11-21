"""What this user has rejected on sight, kept as rules every reviewer (B9 eyes, B11 critic) checks.

Each line comes from a real complaint about a built page (2026-11-18/19). Add a line when the user
rejects something new; the reviewers then flag it on every later build.
"""

USER_DISLIKES = [
    "A colour gradient or flat colour block standing in for a photo or product image (looks unfinished, AI-made).",
    "Two rings around a focused input (an outline offset from a red or coloured border): one calm focus ring only.",
    "The page not filling the window, or not adapting when the window is resized.",
    "Decorative lines or 3D shapes crossing headline or paragraph text.",
    "A placeholder logo or the prompt sentence used as the brand name.",
    "Generic stock photos (office meetings, people at laptops) for a product that is not about offices.",
    "Copy that sounds machine-written: stock phrases (nâng tầm, đẳng cấp, seamless, unlock), formula lines "
    "(\"Sẵn sàng…?\", \"chỉ mất một phút\", \"không chỉ… mà còn\"), emoji, or ratings and client counts nobody supplied.",
    "A closing call-to-action or footer that looks bare (one line and a button floating on the left with empty space).",
]


def taste_block() -> str:
    return "This client has already rejected, so flag any of these as a problem:\n" + "\n".join(f"- {x}" for x in USER_DISLIKES)
