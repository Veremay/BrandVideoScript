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
        self.assertIn("analytics_meta", personas[0])

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
                    "platform_context": "抖音",
                    "ad_sensitivity": "high",
                    "trust_trigger": ["真实反应"],
                    "reject_trigger": ["硬广"],
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
