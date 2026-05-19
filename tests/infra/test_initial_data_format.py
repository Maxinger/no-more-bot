import json
import unittest
from pathlib import Path

from application.use_cases.export_user_data import ExportUserDataCommand, ExportUserDataUseCase
from domain.user import User
from infra import InMemoryRepositories
from infra.dev.initial_data_json_loader import apply_initial_data_fixture
from infra.initial_data_format import build_document
from representation.initial_data_json import InitialDataJsonBytes

_REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = _REPO_ROOT / "tests" / "initial-data.json"


def week_payload_without_number(block: dict) -> dict:
    return {key: value for key, value in block.items() if key != "week"}


class InitialDataFormatTest(unittest.TestCase):
    def test_build_document_matches_fixture_shape(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        repositories = InMemoryRepositories()
        apply_initial_data_fixture(repositories, json_path=FIXTURE_PATH)

        export = ExportUserDataUseCase(repositories.goals, repositories.records).handle(
            ExportUserDataCommand(user=User(fixture["user_id"]))
        )
        goals = [goal for week in export.weeks for goal in week.goals]
        records = [record for week in export.weeks for record in week.records]
        document = build_document(fixture["user_id"], goals, records)

        self.assertEqual(document["user_id"], fixture["user_id"])
        self.assertEqual(len(document["weeks"]), len(fixture["weeks"]))
        for exported, original in zip(document["weeks"], fixture["weeks"], strict=True):
            self.assertEqual(exported["startDate"], original["startDate"])
            self.assertEqual(exported.get("goals"), original.get("goals"))
            self.assertEqual(exported.get("data"), original.get("data"))

    def test_roundtrip_through_use_case_and_serializer(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        repositories = InMemoryRepositories()
        apply_initial_data_fixture(repositories, json_path=FIXTURE_PATH)

        export = ExportUserDataUseCase(repositories.goals, repositories.records).handle(
            ExportUserDataCommand(user=User(fixture["user_id"]))
        )
        exported = json.loads(InitialDataJsonBytes().serialize(export).decode("utf-8"))

        self.assertEqual(exported["user_id"], fixture["user_id"])
        self.assertEqual(len(exported["weeks"]), len(fixture["weeks"]))

        exported_by_start = {
            block["startDate"]: week_payload_without_number(block) for block in exported["weeks"]
        }
        fixture_by_start = {
            block["startDate"]: week_payload_without_number(block) for block in fixture["weeks"]
        }
        self.assertEqual(exported_by_start, fixture_by_start)


if __name__ == "__main__":
    unittest.main()
