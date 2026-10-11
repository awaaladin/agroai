"""Past conversations: chat messages grouped by time gaps, listed newest first, readable and private to the farmer."""
import asyncio
from datetime import timedelta

from sqlalchemy import select, update

from app.db.models import ChatMessageRow
from tests.conftest import auth_headers
from tests.test_accounts import user_headers


def _age_all_messages(client, minutes: int) -> None:
    """Move every saved chat message back in time, to create a gap before the next conversation."""
    db = client.app.state.db

    async def go():
        async with db.session() as s:
            rows = (await s.execute(select(ChatMessageRow.id, ChatMessageRow.created_at))).all()
            for rid, created in rows:
                await s.execute(update(ChatMessageRow).where(ChatMessageRow.id == rid)
                                .values(created_at=created - timedelta(minutes=minutes)))
            await s.commit()

    asyncio.run(go())


def test_conversations_are_grouped_titled_and_private(client):
    h, _ = user_headers(client)
    client.post("/v1/chat", headers=h, json={"message": "My cassava leaves are yellow, what should I check?"})
    client.post("/v1/chat", headers=h, json={"message": "Should I spray today?"})
    first = client.get("/v1/me/chats", headers=h).json()
    assert len(first) == 1 and first[0]["messages"] == 4
    assert first[0]["title"].startswith("My cassava leaves are yellow")

    # two hours later the farmer asks something new: that is a second conversation
    first_id = first[0]["id"]
    _age_all_messages(client, minutes=120)
    client.post("/v1/chat", headers=h, json={"message": "When should I plant yam?"})
    listing = client.get("/v1/me/chats", headers=h).json()
    assert [c["title"][:12] for c in listing] == ["When should ", "My cassava l"]  # newest first
    assert listing[1]["id"] == first_id

    turns = client.get(f"/v1/me/chats/{first_id}", headers=h).json()
    assert [t["role"] for t in turns] == ["farmer", "advisor", "farmer", "advisor"]

    # someone else cannot read it, and an unknown id is a plain 404
    other, _ = user_headers(client, phone="0803 765 4321")
    assert client.get(f"/v1/me/chats/{first_id}", headers=other).status_code == 404
    assert client.get("/v1/me/chats/999999", headers=h).status_code == 404
    assert client.get("/v1/me/chats", headers=other).json() == []


def test_guests_cannot_list_conversations(client):
    assert client.get("/v1/me/chats", headers=auth_headers(client)).status_code == 401
