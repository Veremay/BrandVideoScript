import unittest

from app.services.agents.audience_agent import run_audience_agent
from app.services.persona_analytics import PersonaAnalyticsContext, StubPersonaAnalyticsProvider


class PersonaProvisionTest(unittest.IsolatedAsyncioTestCase):
    async def test_stub_provider_returns_system_generated_persona(self) -> None:
        provider = StubPersonaAnalyticsProvider()
        personas = await provider.generate_personas(
            PersonaAnalyticsContext(project_id="project_1", platform_context="douyin")
        )
        self.assertEqual(len(personas), 1)
        self.assertEqual(personas[0]["data_source"], "system_generated")
        self.assertEqual(personas[0]["job"], "测试职业")
        self.assertIn("analytics_meta", personas[0])

    async def test_file_provider_loads_default_personas(self) -> None:
        from app.services.persona_analytics import FilePersonaAnalyticsProvider

        provider = FilePersonaAnalyticsProvider()
        personas = await provider.generate_personas(
            PersonaAnalyticsContext(project_id="project_1", platform_context="xiaohongshu")
        )
        self.assertGreaterEqual(len(personas), 1)
        self.assertEqual(personas[0]["data_source"], "imported_data")
        self.assertTrue(personas[0].get("name"))
        self.assertTrue(personas[0].get("job"))
        self.assertTrue(personas[0].get("explanation"))
        self.assertTrue(personas[0].get("reason"))
        self.assertTrue(personas[0].get("personal_experiences"))
        self.assertTrue(personas[0].get("characteristic_values"))

    async def test_audience_agent_requires_active_persona(self) -> None:
        project = {
            "_id": "project_aud",
            "platform_context": "douyin",
            "personas": [],
            "active_persona_id": None,
            "current_script": {"columns": [], "rows": []},
        }
        with self.assertRaises(ValueError):
            await run_audience_agent(project)

    async def test_audience_agent_produces_audience_source_nodes(self) -> None:
        project = {
            "_id": "project_aud",
            "platform_context": "douyin",
            "personas": [
                {
                    "persona_id": "persona_1",
                    "name": "快节奏观众",
                    "job": "大学生",
                    "explanation": "偏好真实反应",
                    "reason": "寻找共鸣",
                    "personal_experiences": [],
                    "characteristic_values": {},
                }
            ],
            "active_persona_id": "persona_1",
            "current_script_version_id": "ver_1",
            "current_script": {"columns": [], "rows": []},
        }
        result = await run_audience_agent(project)
        sources = {node.get("source_type") for node in result.get("proposed_nodes", [])}
        self.assertTrue(sources.intersection({"audience_persona", "audience_simulation"}))


if __name__ == "__main__":
    unittest.main()
