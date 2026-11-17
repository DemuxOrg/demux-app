"""Check Gmail access for a signed-in user. Prints counts only, never content.

cd backend && PYTHONPATH=. uv run python scripts/gmail_smoke.py you@gmail.com "newer_than:7d"
"""

import asyncio
import sys

from sqlalchemy import select

from app.auth.google import UserTokenProvider
from app.db.session import SessionLocal
from app.mail.gmail import GmailMailbox
from app.models.user import User


async def main(email: str, query: str) -> None:
    async with SessionLocal() as s:
        user = await s.scalar(select(User).where(User.email == email))
    if user is None:
        raise SystemExit(f"no user {email!r}: sign in at http://localhost:3000 first")
    box = GmailMailbox(UserTokenProvider(SessionLocal, user.id))
    try:
        ids = await box.search_ids(query, max_results=200)
        print(f"threads matching: {len(ids)}{'+' if len(ids) == 200 else ''}")
        if ids:
            thread = await box.get_thread(ids[0])
            chars = sum(len(m.body) for m in thread.messages)
            print(f"newest thread: {len(thread.messages)} messages, {chars} body chars")
    finally:
        await box.aclose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "newer_than:7d"))
