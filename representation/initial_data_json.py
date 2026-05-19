"""Serialize export results to the initial-data JSON fixture format."""

from __future__ import annotations

import json

from application.use_cases.export_user_data import ExportUserDataResult
from infra.initial_data_format import build_document


class InitialDataJsonBytes:
    def serialize(self, result: ExportUserDataResult) -> bytes:
        goals = [goal for week in result.weeks for goal in week.goals]
        records = [record for week in result.weeks for record in week.records]
        document = build_document(result.user_id, goals, records)
        return json.dumps(document, indent=2).encode("utf-8")
