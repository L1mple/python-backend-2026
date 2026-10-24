import io
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from runner import Coordination, IsolationLab, Journal, SCENARIOS


class CoordinationTests(unittest.TestCase):
    """Checks bounded waits and peer release after a worker failure."""

    def test_missing_phase_times_out(self):
        coordination = Coordination(timeout=0.01)
        with self.assertRaises(TimeoutError):
            coordination.wait(coordination.changed)

    def test_failure_releases_waiting_peer(self):
        coordination = Coordination(timeout=2)

        def fail():
            raise ValueError("writer failed")

        with ThreadPoolExecutor(max_workers=2) as workers:
            peer = workers.submit(coordination.run, coordination.wait, coordination.changed)
            failed = workers.submit(coordination.run, fail)
            with self.assertRaisesRegex(ValueError, "writer failed"):
                failed.result(timeout=1)
            with self.assertRaisesRegex(RuntimeError, "other transaction failed"):
                peer.result(timeout=1)


@unittest.skipUnless(Path("/lab/h2.jar").exists(), "real H2 runs in the lab image")
class TransactionFailureTests(unittest.TestCase):
    """Checks rollback and absence of PASS after a failed real observation."""

    def test_wrong_observation_rolls_back_writer(self):
        output = io.StringIO()
        scenario = replace(SCENARIOS[0], name="failed_observation", expected=0)
        lab = IsolationLab(Journal(output), Path("/lab/h2.jar"))
        with self.assertRaisesRegex(AssertionError, "expected 0, observed 200"):
            lab.run(scenario)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertFalse(any(row["event"] == "PASS" for row in rows))
        connection = lab.connect("jdbc:h2:mem:failed_observation;LOCK_TIMEOUT=5000")
        try:
            self.assertEqual(lab.scalar(connection, scenario), 100)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
