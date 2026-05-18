import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.mongo import close_mongo, connect_mongo, get_database
from app.repositories.projects import create_project, get_project, patch_script


async def main() -> None:
    await connect_mongo()
    db = get_database()
    user_id = "phase0_probe"
    project = await create_project(db, user_id, "Phase 0 Probe")

    script = project["current_script"]
    script["rows"][0]["cells"][0]["value"] = "0-5"
    await patch_script(db, project["_id"], user_id, script)

    loaded = await get_project(db, project["_id"], user_id)
    assert loaded is not None
    assert loaded["current_script"]["rows"][0]["cells"][0]["value"] == "0-5"

    await db.projects.delete_one({"_id": project["_id"]})
    await db.users.delete_one({"_id": user_id})
    await close_mongo()
    print("mongo script roundtrip ok")


if __name__ == "__main__":
    asyncio.run(main())
