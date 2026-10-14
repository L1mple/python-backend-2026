import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from visualize import Journal, Timeline


class JournalTests(unittest.TestCase):
    """Rejects journals that cannot support the claimed isolation results."""

    def setUp(self) -> None:
        self.journal = Journal.load(Path(__file__).parent / "evidence" / "run-1.jsonl")

    def test_three_real_runs_have_the_same_observations(self) -> None:
        expected = [
            (event.case, event.tx, event.event, event.value)
            for event in self.journal.events
        ]
        for run in (2, 3):
            journal = Journal.load(
                Path(__file__).parent / "evidence" / f"run-{run}.jsonl"
            )
            observed = [
                (event.case, event.tx, event.event, event.value)
                for event in journal.events
            ]
            self.assertEqual(sorted(observed), sorted(expected))

    def test_corrupt_observation_is_rejected(self) -> None:
        events = [
            replace(event, value=100)
            if event.case == "dirty_ru" and event.event == "READ_2"
            else event
            for event in self.journal.events
        ]
        with self.assertRaisesRegex(ValueError, "observed values"):
            Journal(events).validate()

    def test_commit_after_second_read_is_rejected(self) -> None:
        events = list(self.journal.events)
        commit = next(
            i
            for i, event in enumerate(events)
            if event.case == "nonrepeatable_rc"
            and event.tx == "T2"
            and event.event == "COMMIT"
        )
        read = next(
            i
            for i, event in enumerate(events)
            if event.case == "nonrepeatable_rc" and event.event == "READ_2"
        )
        events[commit], events[read] = events[read], events[commit]
        events = [
            replace(event, seq=i, elapsed_ms=float(i))
            for i, event in enumerate(events, 1)
        ]
        with self.assertRaisesRegex(ValueError, "commit before"):
            Journal(events).validate()

    def test_missing_case_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "all six cases"):
            Journal(self.journal.events[:-9]).validate()

    def test_invalid_time_and_sequence_are_rejected(self) -> None:
        for changes in (
            {"elapsed_ms": float("nan")},
            {"elapsed_ms": -1},
            {"seq": 2},
            {"seq": True},
            {"value": True},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Journal(
                    [
                        replace(self.journal.events[0], **changes),
                        *self.journal.events[1:],
                    ]
                ).validate()

    def test_unknown_isolation_is_rejected(self) -> None:
        events = [
            replace(self.journal.events[0], isolation="SERIALIZABLE"),
            *self.journal.events[1:],
        ]
        with self.assertRaisesRegex(ValueError, "isolation level"):
            Journal(events).validate()

    def test_malformed_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.jsonl"
            for content in ("{", json.dumps({"seq": 1}), "[]"):
                path.write_text(content, encoding="utf-8")
                with (
                    self.subTest(content=content),
                    self.assertRaisesRegex(ValueError, "invalid journal event"),
                ):
                    Journal.load(path)

    def test_renderer_writes_png(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timeline.png"
            Timeline(self.journal).save(path)
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertGreater(path.stat().st_size, 10_000)


if __name__ == "__main__":
    unittest.main()
