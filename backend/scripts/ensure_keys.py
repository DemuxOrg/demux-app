"""Fill missing secrets in an env file: `ensure_keys.py [ENV_FILE] [KEY | KEY@SOURCE ...]`.

Keys default to SECRET_KEY, TOKEN_ENCRYPTION_KEY (backend), BETTER_AUTH_SECRET (frontend
login) and INTERNAL_API_SECRET (frontend server → API sign-up check). `KEY@SOURCE`
copies the value from another env file instead of generating one, for secrets both sides
must share (`INTERNAL_API_SECRET@../.env`). Run by `make setup` / `make env`. Never
prints the keys.
"""

import secrets
import sys
from pathlib import Path

from cryptography.fernet import Fernet

MAKERS = {
    "SECRET_KEY": lambda: secrets.token_urlsafe(48),
    "TOKEN_ENCRYPTION_KEY": lambda: Fernet.generate_key().decode(),
    "BETTER_AUTH_SECRET": lambda: secrets.token_urlsafe(48),
    "INTERNAL_API_SECRET": lambda: secrets.token_urlsafe(48),
}


def value_in(text: str, key: str) -> str:
    return next(
        (ln.split("=", 1)[1].strip() for ln in text.splitlines() if ln.startswith(f"{key}=")), ""
    )


env = Path(sys.argv[1] if len(sys.argv) > 1 else "../.env")
wanted = sys.argv[2:] or list(MAKERS)
text = env.read_text() if env.exists() else ""
present = {line.split("=", 1)[0].strip() for line in text.splitlines() if "=" in line}
added = []
lines = []
for spec in wanted:
    key, _, source = spec.partition("@")
    if value_in(text, key):
        continue
    if source:
        new = value_in(Path(source).read_text(), key) if Path(source).exists() else ""
        if not new:
            continue  # nothing to copy yet; run again after the source has it
    else:
        new = MAKERS[key]()
    if key in present:
        text = "\n".join(ln for ln in text.splitlines() if not ln.startswith(f"{key}=")) + "\n"
    lines.append(f"{key}={new}")
    added.append(key)
if added:
    if text and not text.endswith("\n"):
        text += "\n"
    env.write_text(text + "\n".join(lines) + "\n")
print(f"keys added to {env}: {', '.join(added) or 'none'}")
