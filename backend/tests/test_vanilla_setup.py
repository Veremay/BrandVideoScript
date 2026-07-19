import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.repositories.projects import update_vanilla_setup_stage


class VanillaSetupStageTests(unittest.IsolatedAsyncioTestCase):
    async def test_advances_vanilla_setup_to_conflicts(self) -> None:
        current = {
            "_id": "project-1",
            "user_id": "user-1",
            "mode": "vanilla",
            "vanilla_setup_stage": "requirements",
        }
        saved = {**current, "vanilla_setup_stage": "conflicts"}
        db = MagicMock()
        db.projects.update_one = AsyncMock()

        with patch(
            "app.repositories.projects.get_project",
            new=AsyncMock(side_effect=[current, saved]),
        ):
            result = await update_vanilla_setup_stage(
                db, "project-1", "user-1", "conflicts"
            )

        self.assertEqual(result, saved)
        db.projects.update_one.assert_awaited_once()

    async def test_rejects_skipping_conflicts(self) -> None:
        project = {
            "_id": "project-1",
            "user_id": "user-1",
            "mode": "vanilla",
            "vanilla_setup_stage": "requirements",
        }
        db = MagicMock()
        db.projects.update_one = AsyncMock()

        with patch(
            "app.repositories.projects.get_project",
            new=AsyncMock(return_value=project),
        ):
            with self.assertRaisesRegex(ValueError, "Cannot move vanilla setup"):
                await update_vanilla_setup_stage(
                    db, "project-1", "user-1", "complete"
                )

        db.projects.update_one.assert_not_awaited()

    async def test_completes_setup_after_conflicts(self) -> None:
        current = {
            "_id": "project-1",
            "user_id": "user-1",
            "mode": "vanilla",
            "vanilla_setup_stage": "conflicts",
        }
        saved = {**current, "vanilla_setup_stage": "complete"}
        db = MagicMock()
        db.projects.update_one = AsyncMock()

        with patch(
            "app.repositories.projects.get_project",
            new=AsyncMock(side_effect=[current, saved]),
        ):
            result = await update_vanilla_setup_stage(
                db, "project-1", "user-1", "complete"
            )

        self.assertEqual(result, saved)

    async def test_rejects_moving_completed_setup_backwards(self) -> None:
        project = {
            "_id": "project-1",
            "user_id": "user-1",
            "mode": "vanilla",
            "vanilla_setup_stage": "complete",
        }
        db = MagicMock()
        db.projects.update_one = AsyncMock()

        with patch(
            "app.repositories.projects.get_project",
            new=AsyncMock(return_value=project),
        ):
            with self.assertRaisesRegex(ValueError, "Cannot move vanilla setup"):
                await update_vanilla_setup_stage(
                    db, "project-1", "user-1", "requirements"
                )

        db.projects.update_one.assert_not_awaited()

    async def test_saves_manual_setup_panel_data(self) -> None:
        project = {
            "_id": "project-1",
            "user_id": "user-1",
            "mode": "vanilla",
            "vanilla_setup_stage": "requirements",
            "vanilla_setup_data": {
                "brand_requirements": "Old requirements",
                "conflicts": "",
            },
        }
        db = MagicMock()
        db.projects.update_one = AsyncMock()

        with patch(
            "app.repositories.projects.get_project",
            new=AsyncMock(side_effect=[project, project]),
        ):
            await update_vanilla_setup_stage(
                db,
                "project-1",
                "user-1",
                "requirements",
                {
                    "brand_requirements": "Show the product before the CTA",
                    "conflicts": "",
                },
            )

        update = db.projects.update_one.await_args.args[1]["$set"]
        self.assertEqual(
            update["vanilla_setup_data"]["brand_requirements"],
            "Show the product before the CTA",
        )

    async def test_rejects_full_mode(self) -> None:
        project = {
            "_id": "project-1",
            "user_id": "user-1",
            "mode": "full",
            "vanilla_setup_stage": "requirements",
        }
        db = MagicMock()
        db.projects.update_one = AsyncMock()

        with patch(
            "app.repositories.projects.get_project",
            new=AsyncMock(return_value=project),
        ):
            with self.assertRaisesRegex(ValueError, "only available in vanilla mode"):
                await update_vanilla_setup_stage(
                    db, "project-1", "user-1", "conflicts"
                )

        db.projects.update_one.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
