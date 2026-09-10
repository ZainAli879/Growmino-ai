from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.database import BusinessContextRepository  # noqa: E402


class FakeConnection:
    def __init__(self, row: dict) -> None:
        self.row = row
        self.queries: list[str] = []
        self.params: list[dict] = []

    def execute(self, query: str, params: dict | None = None):
        self.queries.append(query)
        self.params.append(params or {})
        return self

    def fetchall(self):
        return [self.row]

    def fetchone(self):
        return self.row


class DatabaseQueryTests(unittest.TestCase):
    def test_business_base_context_query_does_not_reference_weekly_schedule_table(self) -> None:
        business_id = uuid4()
        connection = FakeConnection(
            {
                "business_id": business_id,
                "business_name": "Velmora",
                "industry": "Fashion - Menswear",
                "description": "Modern apparel",
                "company_logo_url": "",
                "targeted_audience": "Young professionals",
                "targeted_location": "Lahore",
            }
        )

        @contextmanager
        def fake_database_connection(settings):
            yield connection

        with patch("app.database.database_connection", fake_database_connection):
            context = BusinessContextRepository(Settings(database_url="postgresql://app:pass@127.0.0.1:5432/business-management")).fetch_business_base_context(
                business_id=business_id,
                active_only=True,
            )

        executed_query = connection.queries[0]
        self.assertIsNotNone(context)
        self.assertEqual(context.business_id, business_id)
        self.assertNotIn("bws.", executed_query)
        self.assertNotIn("business_weekly_schedules", executed_query)
        self.assertIn("b.is_active = true", executed_query)
        self.assertEqual(connection.params[0], {"business_id": business_id})


if __name__ == "__main__":
    unittest.main()
