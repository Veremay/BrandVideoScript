"""Export activity logs for one project to a JSON file.

Usage:
  uv run python scripts/export_activity_logs.py --project-id PROJECT_ID --user-id USER_ID
  uv run python scripts/export_activity_logs.py --project-id PROJECT_ID --user-id USER_ID --out my_logs.json
  uv run python scripts/export_activity_logs.py --project-id PROJECT_ID --user-id USER_ID --event-type mutation
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.mongo import close_mongo, connect_mongo, get_database
from app.repositories.activity_logs import list_project_activity_logs
from app.repositories.projects import get_project


async def export_logs(
    *,
    project_id: str,
    user_id: str,
    out_path: Path,
    event_type: str | None,
    action: str | None,
    limit: int,
) -> int:
    await connect_mongo()
    try:
        db = get_database()
        project = await get_project(db, project_id, user_id)
        if project is None:
            raise SystemExit(f"Project not found: project_id={project_id} user_id={user_id}")

        events = await list_project_activity_logs(
            db,
            project_id,
            event_type=event_type,
            action=action,
            limit=limit,
        )
        payload = {
            "project_id": project_id,
            "user_id": user_id,
            "title": project.get("title"),
            "count": len(events),
            "events": events,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(events)
    finally:
        await close_mongo()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export BrandVideo activity logs for one project")
    parser.add_argument("--project-id", required=True, help="Project id, e.g. project_abc123")
    parser.add_argument("--user-id", required=True, help="Owner user id")
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default: activity_logs_<project_id>.json)",
    )
    parser.add_argument(
        "--event-type",
        default=None,
        help="Filter by event_type (e.g. mutation, http). Default: export all types",
    )
    parser.add_argument("--action", default=None, help="Optional exact action filter")
    parser.add_argument("--limit", type=int, default=5000, help="Max events to export")
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else Path(f"activity_logs_{args.project_id}.json")
    event_type = None
    if isinstance(args.event_type, str):
        stripped = args.event_type.strip()
        if stripped and stripped.lower() != "all":
            event_type = stripped
    count = asyncio.run(
        export_logs(
            project_id=args.project_id.strip(),
            user_id=args.user_id.strip(),
            out_path=out_path,
            event_type=event_type,
            action=args.action,
            limit=args.limit,
        )
    )
    print(f"Wrote {count} events to {out_path.resolve()}")


if __name__ == "__main__":
    main()
