from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import new_id, now_iso


VALID_AGENT_TYPES = {"brand", "audience", "expert"}
VALID_ROLES = {"user", "assistant", "system"}


def build_agent_message(
    *,
    project_id: str,
    user_id: str,
    agent_type: str,
    role: str,
    content: str,
    quotes: list[dict],
) -> dict:
    if agent_type not in VALID_AGENT_TYPES:
        raise ValueError("Invalid agent type")
    if role not in VALID_ROLES:
        raise ValueError("Invalid message role")
    if not content.strip():
        raise ValueError("Message content cannot be empty")

    return {
        "_id": new_id("msg"),
        "project_id": project_id,
        "user_id": user_id,
        "agent_type": agent_type,
        "role": role,
        "content": content.strip(),
        "quotes": quotes,
        "created_at": now_iso(),
    }


def serialize_agent_message(document: dict) -> dict:
    document["_id"] = str(document["_id"])
    return document


def sort_recent_messages(messages: list[dict]) -> list[dict]:
    return sorted(messages, key=lambda message: message.get("created_at", ""))


async def create_agent_message(
    db: AsyncIOMotorDatabase,
    *,
    project_id: str,
    user_id: str,
    agent_type: str,
    role: str,
    content: str,
    quotes: list[dict],
) -> dict:
    message = build_agent_message(
        project_id=project_id,
        user_id=user_id,
        agent_type=agent_type,
        role=role,
        content=content,
        quotes=quotes,
    )
    await db.agent_messages.insert_one(message)
    return serialize_agent_message(message)


async def list_agent_messages(
    db: AsyncIOMotorDatabase,
    *,
    project_id: str,
    user_id: str,
    agent_type: str,
    limit: int = 20,
) -> list[dict]:
    cursor = (
        db.agent_messages.find({"project_id": project_id, "user_id": user_id, "agent_type": agent_type})
        .sort("created_at", -1)
        .limit(limit)
    )
    newest_first = [serialize_agent_message(message) async for message in cursor]
    return sort_recent_messages(newest_first)
