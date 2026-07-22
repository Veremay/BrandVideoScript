import unittest

from app.services.agents.expert_agent import (
    _format_creator_setup_for_schemes,
    _pick_target_positions,
)


class VanillaModificationSchemeContextTests(unittest.TestCase):
    def test_format_creator_setup_includes_requirements_conflicts_persona(self) -> None:
        project = {
            "mode": "vanilla",
            "active_persona_id": "p1",
            "personas": [
                {
                    "persona_id": "p1",
                    "name": "Alex",
                    "job": "Creator",
                    "explanation": "Cares about pacing",
                }
            ],
            "vanilla_setup_data": {
                "brand_requirements": "Show logo once",
                "conflicts": "Logo vs. story flow",
            },
        }
        text = _format_creator_setup_for_schemes(project)
        self.assertIn("Show logo once", text)
        self.assertIn("Logo vs. story flow", text)
        self.assertIn("Alex", text)

    def test_vanilla_mode_skips_auto_picked_positions(self) -> None:
        project = {
            "mode": "vanilla",
            "rationale_nodes": [
                {"node_id": "pos_1", "node_type": "position", "title": "Leftover"},
            ],
            "consideration_queue": ["pos_1"],
        }
        self.assertEqual(_pick_target_positions(project, []), [])
        self.assertEqual(_pick_target_positions(project, None), [])


if __name__ == "__main__":
    unittest.main()
