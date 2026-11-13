"""Append SECRET_KEY and TOKEN_ENCRYPTION_KEY to the repo-root .env if missing.

Run by `make setup`. Never prints the keys.
"""

import secrets
import sys
from pathlib import Path

from cryptography.fernet import Fernet

env = Path(sys.argv[1] if len(sys.argv) > 1 else "../.env")
text = env.read_text() if env.exists() else ""
present = {line.split("=", 1)[0].strip() for line in text.splitlines() if "=" in line}
added = []
lines = []
for key, make in (
    ("SECRET_KEY", lambda: secrets.token_urlsafe(48)),
    ("TOKEN_ENCRYPTION_KEY", lambda: Fernet.generate_key().decode()),
):
    current = next(
        (ln.split("=", 1)[1].strip() for ln in text.splitlines() if ln.startswith(f"{key}=")), ""
    )
    if not current:
        if key in present:
            text = "\n".join(ln for ln in text.splitlines() if not ln.startswith(f"{key}=")) + "\n"
        lines.append(f"{key}={make()}")
        added.append(key)
if added:
    if text and not text.endswith("\n"):
        text += "\n"
    env.write_text(text + "\n".join(lines) + "\n")
print(f"keys added to {env}: {', '.join(added) or 'none'}")
