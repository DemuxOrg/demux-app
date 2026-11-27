"""Palettes (frontend/theme.md §10.3): contrast, the same values as theme.md, the shell's
CSS and live switching through the bridge, and that chat edits cannot change it."""

import re
from pathlib import Path

import pytest

from app.agent.palettes import DEFAULT_PALETTE, PALETTE_IDS, PALETTES, palette_css
from app.agent.shell import build_srcdoc
from app.agent.tools import tools_for
from tests.helpers import GOOD_APP

THEME = Path(__file__).resolve().parents[2] / "frontend" / "theme.md"
WHITE = "#FFFFFF"


def _luminance(hex_colour: str) -> float:
    r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))

    def f(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("pid", PALETTE_IDS)
def test_palette_text_pairs_meet_wcag_aa(pid):
    p = PALETTES[pid]
    assert contrast(WHITE, p.accent) >= 4.5  # primary button text, links on white
    assert contrast(WHITE, p.hover) >= 4.5
    assert contrast(p.ink, p.soft) >= 4.5  # "Updated" tag, selected chip
    assert contrast(p.accent, p.tint) >= 4.5  # a link inside a just-updated record


def test_palettes_match_theme_md():
    if not THEME.exists():
        pytest.skip("frontend/theme.md is not available here")
    text = THEME.read_text()
    section = text[text.index("### 10.3") : text.index("### 10.4")]
    for p in PALETTES.values():
        row = re.search(rf"^\| (?:\*\*)?{p.name}(?:\*\*)?(?: \(default\))? \| `#.*$", section, re.M)
        assert row, f"{p.name} row missing in theme.md §10.3"
        assert re.findall(r"#[0-9A-F]{6}", row.group(0)) == [
            p.accent,
            p.hover,
            p.ink,
            p.soft,
            p.line,
            p.tint,
        ]
        series = re.search(rf"^\| {p.name} \| ([a-z ·]+) \|$", section, re.M)
        assert series, f"{p.name} series row missing in theme.md §10.3"
        assert tuple(s.strip() for s in series.group(1).split("·")) == p.series


def test_shell_css_and_srcdoc():
    css = palette_css()
    for pid in PALETTE_IDS:
        assert f':root[data-palette="{pid}"]' in css
    assert 'data-palette="teal"' in build_srcdoc("<p>x</p>", "teal")
    assert f'data-palette="{DEFAULT_PALETTE}"' in build_srcdoc("<p>x</p>")
    assert f'data-palette="{DEFAULT_PALETTE}"' in build_srcdoc("<p>x</p>", '"><script>')


async def test_bridge_switches_palette_live():
    """The frontend sends `demux:palette`; the running app recolours without a reload,
    and unknown ids are ignored."""
    from playwright.async_api import async_playwright

    app = GOOD_APP + '<button class="btn primary" id="probe">Probe</button>'
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page()
        await page.set_content(build_srcdoc(app), wait_until="load")

        async def colours(palette: str) -> tuple[str, str]:
            await page.evaluate(
                "(p) => window.postMessage({type: 'demux:palette', palette: p}, '*')", palette
            )
            await page.wait_for_timeout(300)  # .btn eases its colour over 150ms
            return await page.evaluate(
                """() => [
                  getComputedStyle(document.getElementById('probe')).backgroundColor,
                  getComputedStyle(document.documentElement)
                    .getPropertyValue('--dmx-series-1').trim(),
                ]"""
            )

        teal = await colours("teal")
        ignored = await colours("neon")
        rose = await colours("rose")
        await browser.close()

    assert teal == ["rgb(15, 118, 110)", PALETTES["teal"].accent]
    assert ignored == teal
    assert rose == ["rgb(192, 44, 108)", PALETTES["rose"].accent]


def test_no_phase_can_change_the_palette():
    for phase in ("design", "process", "edit"):
        assert "set_palette" not in [t.name for t in tools_for(phase)]
