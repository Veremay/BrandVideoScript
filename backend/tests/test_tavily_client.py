import unittest

from app.services.tavily_client import TavilyClient


class TavilyClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_search_returns_mock_payload_when_mock_enabled(self):
        client = TavilyClient()
        response = await client.search(query="EV brand campaign trends", mock=True)

        self.assertTrue(response["mock"])
        self.assertEqual(response["payload"]["query"], "EV brand campaign trends")
        self.assertEqual(response["results"], [])

    async def test_extract_returns_mock_payload_when_mock_enabled(self):
        client = TavilyClient()
        response = await client.extract(urls=["https://example.com/docs"], mock=True)

        self.assertTrue(response["mock"])
        self.assertEqual(response["payload"]["urls"], ["https://example.com/docs"])
        self.assertEqual(response["results"], [])
