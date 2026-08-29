from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import unittest

from insight_desk.production_replay_v2 import run_recorded_production_replay
from scripts import phase11_daily_production as production


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "phase5_real_source_replay_v1.json"


class ReplayIdentityDiagnosticTempTests(unittest.TestCase):
    def test_dump_actual_replay_canonical_economy_fields(self) -> None:
        original_runtime = production.production_v2_runtime
        snapshot: dict[str, object] = {}

        @contextmanager
        def capturing_runtime(core_module):
            with original_runtime(core_module) as registry:
                try:
                    yield registry
                finally:
                    snapshot["events"] = [
                        {
                            "event_id": event.event_id,
                            "topic": event.topic,
                            "actor": event.actor,
                            "action": event.action,
                            "object": event.object,
                            "event_time": event.event_time,
                            "participants": list(event.participants),
                            "temporal_state": getattr(event.temporal_state, "value", event.temporal_state),
                            "certainty": getattr(event.certainty, "value", event.certainty),
                            "location": event.location,
                            "cause": event.cause,
                            "parent_event_id": event.parent_event_id,
                        }
                        for event in registry.events_by_id.values()
                        if event.topic == "economy"
                    ]
                    snapshot["parent_events"] = [
                        {
                            "event_id": event.event_id,
                            "actor": event.actor,
                            "action": event.action,
                            "object": event.object,
                            "event_time": event.event_time,
                            "participants": list(event.participants),
                        }
                        for event in registry.parent_events_by_id.values()
                    ]
                    snapshot["current_identity_relation"] = registry.current_identity_relation

        production.production_v2_runtime = capturing_runtime
        try:
            with tempfile.TemporaryDirectory() as tmp:
                run_recorded_production_replay(
                    fixture_path=FIXTURE,
                    work_dir=Path(tmp),
                )
        finally:
            production.production_v2_runtime = original_runtime

        self.fail("REPLAY_CANONICAL_DIAGNOSTIC=" + json.dumps(snapshot, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
