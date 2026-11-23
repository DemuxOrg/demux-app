"""The five palettes a generated app can use (frontend/theme.md §10.3).

A palette sets the accent family and the order of chart series / category dots, nothing
else: neutrals, status colours, type and radii are fixed. The shell turns this table into
CSS and the API lists it for the frontend's palette tiles. The user picks one while the
workspace is built (setup step "Your look", docs/UI_GENERATION_PLAN.md); it is not changed
afterwards. Values are checked against theme.md and for contrast in tests/test_palettes.py.
"""

from dataclasses import dataclass
from typing import Literal, get_args

PaletteId = Literal["violet", "ocean", "teal", "rose", "graphite"]
PALETTE_IDS: tuple[str, ...] = get_args(PaletteId)
DEFAULT_PALETTE: PaletteId = "violet"

# Category colours (`--dmx-cat-*`), the same in every palette.
CATEGORY: dict[str, str] = {
    "blue": "#5EA7F4",
    "lavender": "#9A8BF7",
    "pink": "#E0679A",
    "green": "#2FB36B",
    "amber": "#F5A524",
    "purple": "#9A7BF7",
}
SERIES_OTHER = "#AEB8C6"


@dataclass(frozen=True)
class Palette:
    id: str
    name: str
    hint: str  # the colours this palette covers, in words
    accent: str
    hover: str
    ink: str
    soft: str
    line: str
    tint: str
    series: tuple[str, str, str, str]  # series 2-5, as CATEGORY names

    @property
    def series_hex(self) -> list[str]:
        """Series 1-5 as hex values (series 1 is the accent)."""
        return [self.accent, *(CATEGORY[c] for c in self.series)]


# fmt: off
PALETTES: dict[str, Palette] = {
    p.id: p
    for p in (
        Palette(
            "violet", "Violet", "purple, violet, the Demux default",
            "#6A3DF0", "#5A2FDC", "#4B24C9", "#EEE9FE", "#C9BCFB", "#FBFAFF",
            ("blue", "pink", "green", "amber"),
        ),
        Palette(
            "ocean", "Ocean", "blue, navy",
            "#0E67B0", "#0B5794", "#0A4A80", "#E1F0FB", "#ADD3F0", "#F7FBFE",
            ("lavender", "pink", "green", "amber"),
        ),
        Palette(
            "teal", "Teal", "teal, turquoise, green, mint",
            "#0F766E", "#0B615A", "#0A5650", "#DDF3EF", "#A6DCD3", "#F6FCFB",
            ("amber", "lavender", "pink", "blue"),
        ),
        Palette(
            "rose", "Rose", "pink, red, magenta, warm colours",
            "#C02C6C", "#A6235C", "#921C50", "#FCE6EF", "#F2B8CF", "#FFF9FB",
            ("blue", "green", "amber", "lavender"),
        ),
        Palette(
            "graphite", "Graphite", "grey, black, dark, neutral, minimal",
            "#2E3D54", "#1E2A3D", "#1E2A3D", "#E6EAF0", "#C3CCD8", "#F9FAFC",
            ("blue", "amber", "green", "pink"),
        ),
    )
}
# fmt: on
assert tuple(PALETTES) == PALETTE_IDS


def valid_palette(value: str | None) -> PaletteId:
    """The id itself when known, else the default (never fails on stored values)."""
    return value if value in PALETTE_IDS else DEFAULT_PALETTE  # type: ignore[return-value]


def _vars(p: Palette) -> str:
    series = "".join(f"--dmx-series-{i}:{v};" for i, v in enumerate(p.series_hex[1:], start=2))
    return (
        f"--dmx-accent:{p.accent};--dmx-accent-hover:{p.hover};--dmx-accent-ink:{p.ink};"
        f"--dmx-accent-soft:{p.soft};--dmx-accent-line:{p.line};--dmx-accent-tint:{p.tint};"
        f"{series}"
    )


def palette_css() -> str:
    """The default palette on :root, each palette on :root[data-palette=…], and the
    tokens derived from the accent (they follow whichever palette is active)."""
    rules = [
        ":root{" + _vars(PALETTES[DEFAULT_PALETTE]) + "--dmx-series-1:var(--dmx-accent);"
        "--dmx-accent-ring:color-mix(in srgb,var(--dmx-accent) 22%,transparent);"
        "--dmx-accent-glow:color-mix(in srgb,var(--dmx-accent) 8%,transparent)}"
    ]
    rules += [f':root[data-palette="{p.id}"]{{{_vars(p)}}}' for p in PALETTES.values()]
    return "\n".join(rules)
