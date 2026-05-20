import unittest
from copy import deepcopy
from typing import Any

from app.models.script import default_script
from app.repositories.projects import (
    apply_expert_suggestion,
    build_expert_hunk,
    build_expert_suggestion,
    save_expert_suggestions,
    update_expert_suggestion_status,
)


def _seeded_project() -> dict[str, Any]:
    script = default_script()
    # Populate row cells deterministically.
    row = script["rows"][0]
    cells_by_column = {cell["column_id"]: cell for cell in row["cells"]}
    cells_by_column["col_scene"]["value"] = "原始画面"
    cells_by_column["col_notes"]["value"] = "原始备注"
    cells_by_column["col_duration"]["value"] = "0-5"
    return {
        "_id": "p1",
        "user_id": "u1",
        "current_script": script,
        "expert_suggestions": [],
        "stale": {"brand": False, "audience": False, "expert": True},
        "brand_insights": [],
        "audience_analysis": {},
        "brand_research": {"entity": {}, "research_summary": ""},
    }


class _FakeUpdateOne:
    def __init__(self, store: dict) -> None:
        self.store = store

    async def __call__(self, filter_query: dict, update: dict) -> None:
        document = self.store.get(filter_query["_id"])
        if document is None or document.get("user_id") != filter_query["user_id"]:
            return
        for key, value in (update.get("$set") or {}).items():
            if "." in key:
                head, tail = key.split(".", 1)
                document.setdefault(head, {})[tail] = value
            else:
                document[key] = value


class _FakeFindOne:
    def __init__(self, store: dict) -> None:
        self.store = store

    async def __call__(self, query: dict, projection: dict | None = None) -> dict | None:
        document = self.store.get(query.get("_id"))
        if document is None:
            return None
        if "user_id" in query and document.get("user_id") != query["user_id"]:
            return None
        if "project_id" in query and document.get("project_id") != query["project_id"]:
            return None
        return deepcopy(document)


class _FakeInsertOne:
    def __init__(self, store: dict) -> None:
        self.store = store

    async def __call__(self, document: dict) -> None:
        self.store[document["_id"]] = deepcopy(document)


class _FakeProjectsCollection:
    def __init__(self, store: dict) -> None:
        self.update_one = _FakeUpdateOne(store)
        self.find_one = _FakeFindOne(store)


class _FakeSnapshotsCollection:
    def __init__(self, store: dict) -> None:
        self.insert_one = _FakeInsertOne(store)
        self.find_one = _FakeFindOne(store)


class _FakeDB:
    def __init__(self, project: dict) -> None:
        self.projects_store: dict[str, dict] = {project["_id"]: deepcopy(project)}
        self.snapshots_store: dict[str, dict] = {}
        self.projects = _FakeProjectsCollection(self.projects_store)
        self.script_snapshots = _FakeSnapshotsCollection(self.snapshots_store)


class ExpertBuilderTest(unittest.TestCase):
    def test_build_hunk_validates_required_fields(self):
        with self.assertRaises(ValueError):
            build_expert_hunk(row_id="", column_id="col", old="a", new="b")
        with self.assertRaises(ValueError):
            build_expert_hunk(row_id="row", column_id="", old="a", new="b")

    def test_build_suggestion_normalizes_direction_and_assigns_ids(self):
        hunk = build_expert_hunk(row_id="row_1", column_id="col_scene", old="A", new="B", reason="r")
        suggestion = build_expert_suggestion(
            title=" 方案 ",
            direction="invalid",
            description="d",
            target_problem="t",
            rationale="r",
            brand_tradeoff="b",
            audience_tradeoff="a",
            creator_tradeoff="c",
            risk="risk",
            explanation_to_brand="exp",
            hunks=[hunk],
        )
        self.assertTrue(suggestion["suggestion_id"].startswith("suggestion_"))
        self.assertEqual(suggestion["direction"], "custom")
        self.assertEqual(suggestion["title"], "方案")
        self.assertEqual(suggestion["status"], "draft")
        self.assertEqual(len(suggestion["hunks"]), 1)
        self.assertTrue(suggestion["hunks"][0]["hunk_id"].startswith("hunk_"))

    def test_build_suggestion_requires_hunk(self):
        with self.assertRaises(ValueError):
            build_expert_suggestion(
                title="x",
                direction="balanced",
                description="",
                target_problem="",
                rationale="",
                brand_tradeoff="",
                audience_tradeoff="",
                creator_tradeoff="",
                risk="",
                explanation_to_brand="",
                hunks=[],
            )


class ExpertSuggestionPersistenceTest(unittest.IsolatedAsyncioTestCase):
    async def test_save_expert_suggestions_appends_and_clears_stale(self):
        project = _seeded_project()
        db = _FakeDB(project)
        hunk = build_expert_hunk(
            row_id=project["current_script"]["rows"][0]["row_id"],
            column_id="col_scene",
            old="原始画面",
            new="新画面",
        )
        suggestion = build_expert_suggestion(
            title="方案 A",
            direction="balanced",
            description="d",
            target_problem="t",
            rationale="r",
            brand_tradeoff="b",
            audience_tradeoff="a",
            creator_tradeoff="c",
            risk="risk",
            explanation_to_brand="exp",
            hunks=[hunk],
        )

        updated = await save_expert_suggestions(
            db,
            "p1",
            "u1",
            [suggestion],
            based_on_brand_insight_ids=["insight_1"],
            based_on_audience_analysis_id="analysis_1",
        )
        assert updated is not None
        self.assertEqual(len(updated["expert_suggestions"]), 1)
        self.assertFalse(updated["stale"]["expert"])
        self.assertEqual(updated["expert_suggestions"][0]["based_on_brand_insight_ids"], ["insight_1"])
        self.assertEqual(updated["expert_suggestions"][0]["based_on_audience_analysis_id"], "analysis_1")

    async def test_update_status_changes_only_target(self):
        project = _seeded_project()
        hunk = build_expert_hunk(
            row_id=project["current_script"]["rows"][0]["row_id"],
            column_id="col_scene",
            old="原始画面",
            new="新画面",
        )
        suggestion = build_expert_suggestion(
            title="方案 A",
            direction="balanced",
            description="",
            target_problem="",
            rationale="",
            brand_tradeoff="",
            audience_tradeoff="",
            creator_tradeoff="",
            risk="",
            explanation_to_brand="",
            hunks=[hunk],
        )
        project["expert_suggestions"] = [suggestion]
        db = _FakeDB(project)

        updated = await update_expert_suggestion_status(
            db,
            "p1",
            "u1",
            suggestion["suggestion_id"],
            status="dismissed",
        )
        assert updated is not None
        self.assertEqual(updated["expert_suggestions"][0]["status"], "dismissed")

    async def test_update_status_rejects_unknown_id(self):
        project = _seeded_project()
        db = _FakeDB(project)
        with self.assertRaises(ValueError):
            await update_expert_suggestion_status(
                db,
                "p1",
                "u1",
                "suggestion_missing",
                status="dismissed",
            )


class ApplyExpertSuggestionTest(unittest.IsolatedAsyncioTestCase):
    async def _setup_with_suggestion(self) -> tuple[_FakeDB, dict, dict]:
        project = _seeded_project()
        row_id = project["current_script"]["rows"][0]["row_id"]
        hunks = [
            build_expert_hunk(row_id=row_id, column_id="col_scene", old="原始画面", new="新画面"),
            build_expert_hunk(row_id=row_id, column_id="col_notes", old="原始备注", new="新备注"),
        ]
        suggestion = build_expert_suggestion(
            title="方案 A",
            direction="balanced",
            description="",
            target_problem="",
            rationale="",
            brand_tradeoff="",
            audience_tradeoff="",
            creator_tradeoff="",
            risk="",
            explanation_to_brand="",
            hunks=hunks,
        )
        project["expert_suggestions"] = [suggestion]
        project["stale"]["expert"] = True
        db = _FakeDB(project)
        return db, suggestion, project

    async def test_apply_succeeds_for_matching_cells(self):
        db, suggestion, project = await self._setup_with_suggestion()
        accepted = [hunk["hunk_id"] for hunk in suggestion["hunks"]]

        result = await apply_expert_suggestion(
            db,
            "p1",
            "u1",
            suggestion["suggestion_id"],
            accepted_hunk_ids=accepted,
        )
        self.assertEqual(result["applied_hunk_count"], 2)
        self.assertEqual(set(result["applied_hunk_ids"]), set(accepted))
        self.assertEqual(result["conflict_hunk_ids"], [])
        self.assertTrue(result["before_snapshot_id"].startswith("snapshot_"))
        self.assertTrue(result["after_snapshot_id"].startswith("snapshot_"))

        refreshed = result["project"]
        cells = {cell["column_id"]: cell["value"] for cell in refreshed["current_script"]["rows"][0]["cells"]}
        self.assertEqual(cells["col_scene"], "新画面")
        self.assertEqual(cells["col_notes"], "新备注")
        self.assertFalse(refreshed["stale"]["expert"])
        self.assertEqual(refreshed["expert_suggestions"][0]["status"], "applied")

    async def test_partial_apply_marks_status_partially_applied(self):
        db, suggestion, project = await self._setup_with_suggestion()
        # Accept only the first hunk; the second remains rejected by the user.
        result = await apply_expert_suggestion(
            db,
            "p1",
            "u1",
            suggestion["suggestion_id"],
            accepted_hunk_ids=[suggestion["hunks"][0]["hunk_id"]],
            rejected_hunk_ids=[suggestion["hunks"][1]["hunk_id"]],
        )
        self.assertEqual(result["applied_hunk_count"], 1)
        self.assertEqual(result["project"]["expert_suggestions"][0]["status"], "partially_applied")

    async def test_apply_reports_conflict_when_cell_changed(self):
        db, suggestion, project = await self._setup_with_suggestion()
        # Manually mutate the live script so the hunk.old no longer matches.
        live = db.projects_store["p1"]
        for cell in live["current_script"]["rows"][0]["cells"]:
            if cell["column_id"] == "col_scene":
                cell["value"] = "已被人工修改"
                break

        accepted = [hunk["hunk_id"] for hunk in suggestion["hunks"]]
        result = await apply_expert_suggestion(
            db,
            "p1",
            "u1",
            suggestion["suggestion_id"],
            accepted_hunk_ids=accepted,
        )
        # Only the second hunk should apply; the first becomes conflict.
        self.assertEqual(result["applied_hunk_count"], 1)
        self.assertIn(suggestion["hunks"][0]["hunk_id"], result["conflict_hunk_ids"])
        self.assertEqual(result["project"]["expert_suggestions"][0]["status"], "partially_applied")

    async def test_apply_with_all_conflicts_does_not_write_after_snapshot(self):
        db, suggestion, project = await self._setup_with_suggestion()
        # Mutate both cells so every hunk conflicts.
        live = db.projects_store["p1"]
        for cell in live["current_script"]["rows"][0]["cells"]:
            if cell["column_id"] in {"col_scene", "col_notes"}:
                cell["value"] = "drifted"

        accepted = [hunk["hunk_id"] for hunk in suggestion["hunks"]]
        result = await apply_expert_suggestion(
            db,
            "p1",
            "u1",
            suggestion["suggestion_id"],
            accepted_hunk_ids=accepted,
        )
        self.assertEqual(result["applied_hunk_count"], 0)
        self.assertEqual(set(result["conflict_hunk_ids"]), set(accepted))
        # No after_snapshot written when nothing applied.
        self.assertIsNone(result["after_snapshot_id"])

    async def test_apply_unknown_suggestion_raises(self):
        db, _, _ = await self._setup_with_suggestion()
        with self.assertRaises(ValueError):
            await apply_expert_suggestion(
                db,
                "p1",
                "u1",
                "suggestion_missing",
                accepted_hunk_ids=[],
            )


if __name__ == "__main__":
    unittest.main()
