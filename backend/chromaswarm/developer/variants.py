"""Hand-written composition variants per section template, picked by the B9 eyes.

When the section eye rejects a section, the build first tries these instead of asking a model to
write CSS: in every live run the model's own CSS made the page worse or broke QA, while these are
written once, against the templates' real markup, inside the design system (they pass the same
`stylist.validate_css` as the model's would — tested). Each variant is tried, shot at 1440 and 375,
judged again, and kept only when the verdict improves — the same loop, but every option is safe.
"""

from __future__ import annotations

from pydantic import BaseModel


class Variant(BaseModel):
    name: str
    label: str  # Vietnamese, shown in the Studio / notices
    css: str  # `{sel}` = the section's [data-swarm-section="…"] selector

    def for_section(self, section_id: str) -> str:
        return self.css.replace("{sel}", f'[data-swarm-section="{section_id}"]').strip()


D = "@media (min-width: 1024px)"

VARIANTS: dict[str, list[Variant]] = {
    "hero-centered": [
        Variant(name="copy-left-ui-right", label="chữ bên trái, giao diện bên phải", css=f"""
{D} {{
{{sel}} .hero-centered {{ display: grid; grid-template-columns: 5fr 7fr; grid-template-rows: 1fr auto auto auto auto 1fr;
  column-gap: 64px; row-gap: 24px; align-items: center; text-align: left; }}
{{sel}} .hero-centered > .eyebrow {{ grid-column: 1; grid-row: 2; }}
{{sel}} .hero-centered > .t-display {{ grid-column: 1; grid-row: 3; }}
{{sel}} .hero-centered > .t-lead {{ grid-column: 1; grid-row: 4; }}
{{sel}} .hero-centered > .row {{ grid-column: 1; grid-row: 5; }}
{{sel}} .hero-panel {{ grid-column: 2; grid-row: 1 / 7; margin-top: 0; }}
{{sel}} .t-display {{ font-size: var(--text-h1); }}
{{sel}} .hero-centered > .row {{ justify-content: flex-start; }}
}}"""),
        Variant(name="editorial-left", label="căn trái kiểu tạp chí", css="""
{sel} .hero-centered { align-items: flex-start; text-align: left; }
{sel} .hero-centered > .row { justify-content: flex-start; }
{sel} .t-lead { max-width: 52ch; }"""),
    ],
    "split-7-5": [
        Variant(name="visual-first", label="hình bên trái, chữ bên phải", css=f"""
{D} {{
{{sel}} .split > :first-child {{ order: 2; }}
}}"""),
        Variant(name="wide-visual", label="hình rộng hơn chữ", css=f"""
{D} {{
{{sel}} .split {{ grid-template-columns: 5fr 7fr; }}
}}"""),
    ],
    "inline-metrics": [
        Variant(name="ruled", label="số liệu chia bằng đường mảnh", css="""
{sel} .metrics { gap: 0; border-top: 1px solid var(--border-subtle); }
{sel} .metric { padding-block: 24px; padding-inline: 24px; border-left: 1px solid var(--border-subtle); }
{sel} .metric dd { margin-top: 4px; }"""),
        Variant(name="lead-figure", label="một con số dẫn dắt", css=f"""
{D} {{
{{sel}} .metrics {{ grid-template-columns: 2fr 1fr 1fr 1fr; align-items: end; }}
{{sel}} .metric:first-child dt {{ font-size: var(--text-h1); }}
}}"""),
    ],
    "alternating-z": [
        Variant(name="one-side", label="ảnh cùng một phía, không zig-zag", css=f"""
{{sel}} .z-rows {{ gap: 64px; }}
{D} {{
{{sel}} .split.is-flipped > :first-child {{ order: 0; }}
{{sel}} .split {{ grid-template-columns: 1fr 1fr; }}
}}"""),
        Variant(name="tight-rows", label="các hàng gần nhau, chữ rộng hơn", css=f"""
{{sel}} .z-rows {{ gap: 48px; }}
{D} {{
{{sel}} .split {{ grid-template-columns: 6fr 6fr; }}
}}"""),
    ],
    "bento": [
        Variant(name="even-grid", label="lưới đều 3 cột", css=f"""
{D} {{
{{sel}} .bento {{ grid-template-columns: repeat(3, 1fr); }}
{{sel}} .bento-wide {{ grid-column: auto; }}
}}"""),
    ],
    "accordion": [
        Variant(name="stacked", label="tiêu đề trên, câu hỏi dưới", css=f"""
{D} {{
{{sel}} .split {{ grid-template-columns: 1fr; }}
}}
{{sel}} .faq {{ max-width: 72ch; }}"""),
        Variant(name="narrow-head", label="cột tiêu đề hẹp hơn", css=f"""
{D} {{
{{sel}} .split {{ grid-template-columns: 4fr 8fr; }}
}}"""),
    ],
    "full-bleed-band": [
        Variant(name="stacked", label="lời mời trên, nút dưới", css=f"""
{D} {{
{{sel}} .band {{ grid-template-columns: 1fr; align-items: start; }}
}}
{{sel}} .band .t-h2 {{ max-width: 28ch; }}"""),
        Variant(name="large-ask", label="lời mời cỡ lớn", css="""
{sel} .band .t-h2 { font-size: var(--text-h1); max-width: 18ch; }"""),
    ],
}


def variants_for(structure: str) -> list[Variant]:
    return VARIANTS.get(structure, [])
