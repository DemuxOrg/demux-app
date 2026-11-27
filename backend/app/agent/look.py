"""Does the prompt already say how the workspace should look? (theme.md §7.15)

Plain code, no LLM. When it does, the build skips the look question and the interface
designer follows the prompt; when it doesn't, the first question moment asks the user,
and the answer goes to the designer. Demux's palettes are never used for this.

A colour word counts only when it is clearly about the look: next to a look word
("blue theme", "purple accents", "colours: navy"), or as "in <colour>" at the end of a
clause ("track bills in teal"). "Blue Bottle orders", "red flags" or "black friday" are
about the content, not the look.
"""

import re

COLOURS = (
    r"violet|purple|lilac|lavender|blue|navy|ocean|teal|green|turquoise|mint|olive|"
    r"pink|rose|red|crimson|orange|coral|amber|yellow|gold|golden|brown|beige|cream|"
    r"grey|gray|black|white|monochrome|neutral|pastel|earthy|warm|cool|vibrant"
)
LOOK_WORDS = r"colou?rs?|theme|themes|palette|look|accents?|style|tones?|scheme|vibe"

_PATTERNS = [
    # "blue theme", "purple accents", "warm colours", "earthy tones"
    rf"\b(?:{COLOURS})(?:[\s-]+(?:and|&)[\s-]+(?:{COLOURS}))?[\s-]+(?:{LOOK_WORDS})\b",
    # "theme: navy", "colours blue and gold", "accent colour teal"
    rf"\b(?:{LOOK_WORDS})\s*(?::|of|in|=)?\s*(?:{COLOURS})\b",
    # "track bills in teal", "… in navy and gold" (end of the clause)
    rf"\bin\s+(?:{COLOURS})(?:\s+(?:and|&)\s+(?:{COLOURS}))?\s*(?:$|[.,;!?)])",
    # light/dark and named styles
    r"\b(?:dark|light|night)[\s-]*(?:mode|theme|ui|look|background)\b",
    r"\b(?:minimal|minimalist|brutalist|retro|playful|elegant|corporate|editorial|"
    r"futuristic|neon|pastel|monochrome)\s+(?:look|style|theme|design|ui|aesthetic)\b",
]
_LOOK = re.compile("|".join(f"(?:{p})" for p in _PATTERNS), re.IGNORECASE)


def look_from_prompt(prompt: str) -> bool:
    """True when the prompt says how the workspace should look."""
    return bool(_LOOK.search(" ".join(prompt.split())))


# The look question's options (theme.md §7.15). The user may also type their own.
LOOK_DECIDE = "Let Demux decide"
LOOK_OPTIONS = [LOOK_DECIDE, "Light and calm", "Dark and focused", "Bold and colourful"]


def build_look_input(prompt: str) -> dict[str, str]:
    """The look part of a new build run's input."""
    return {"look_state": "from_prompt" if look_from_prompt(prompt) else "asking"}
