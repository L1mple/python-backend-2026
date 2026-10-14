import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

from matplotlib.figure import Figure

SCENARIOS = {
    "dirty_ru": ("READ_UNCOMMITTED", 100, 200),
    "dirty_rc": ("READ_COMMITTED", 100, 100),
    "nonrepeatable_rc": ("READ_COMMITTED", 100, 200),
    "nonrepeatable_rr": ("REPEATABLE_READ", 100, 100),
    "phantom_rr": ("REPEATABLE_READ", 1, 1),
    "phantom_serializable": ("SERIALIZABLE", 1, 1),
}


@dataclass(frozen=True, slots=True)
class Event:
    """One ordered observation from the JDBC runner."""

    seq: int
    case: str
    isolation: str
    tx: str
    event: str
    value: int | None
    elapsed_ms: float


class Journal:
    """Validates measured events and their transaction ordering."""

    def __init__(self, events: list[Event]) -> None:
        self.events = events

    @classmethod
    def load(cls, path: Path) -> "Journal":
        events = []
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            try:
                events.append(Event(**json.loads(line)))
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"{path}:{line_number}: invalid journal event"
                ) from error
        journal = cls(events)
        journal.validate()
        return journal

    def validate(self) -> None:
        previous_time = 0.0
        case_order = []
        for sequence, event in enumerate(self.events, 1):
            if type(event.seq) is not int or event.seq != sequence:
                raise ValueError("journal sequence must be consecutive from 1")
            if type(event.elapsed_ms) not in (int, float) or not math.isfinite(
                event.elapsed_ms
            ):
                raise ValueError("elapsed_ms must be a finite number")
            if event.elapsed_ms < previous_time:
                raise ValueError("elapsed_ms must be nonnegative and monotonic")
            previous_time = event.elapsed_ms
            if not isinstance(event.case, str) or event.case not in SCENARIOS:
                raise ValueError("unknown isolation case")
            if event.isolation != SCENARIOS[event.case][0] or event.tx not in (
                "T1",
                "T2",
                "LAB",
            ):
                raise ValueError("unexpected isolation level or transaction")
            if event.value is not None and type(event.value) is not int:
                raise ValueError("event value must be an integer or null")
            if not case_order or event.case != case_order[-1]:
                case_order.append(event.case)
        if case_order != list(SCENARIOS):
            raise ValueError("journal must contain all six cases in runner order")

        for case, (_, initial, expected) in SCENARIOS.items():
            self.validate_case(case, initial, expected)

    def validate_case(self, case: str, initial: int, expected: int) -> None:
        events = [event for event in self.events if event.case == case]
        dirty = case.startswith("dirty_")
        phantom = case.startswith("phantom_")
        expected_reader = [("BEGIN", None), ("READ_1", initial), ("READ_2", expected)]
        if dirty:
            expected_reader.append(("READ_AFTER_ROLLBACK", 100))
        expected_reader.append(("COMMIT", None))
        expected_writer = [
            ("BEGIN", None),
            ("INSERT" if phantom else "UPDATE", 150 if phantom else 200),
            ("ROLLBACK" if dirty else "COMMIT", None),
        ]
        for tx, expected_events in (
            ("T1", expected_reader),
            ("T2", expected_writer),
            ("LAB", [("PASS", expected)]),
        ):
            observed = [
                (event.event, event.value) for event in events if event.tx == tx
            ]
            if observed != expected_events:
                raise ValueError(f"{case}: unexpected {tx} events or observed values")

        reader = [event.seq for event in events if event.tx == "T1"]
        writer = [event.seq for event in events if event.tx == "T2"]
        if not reader[1] < writer[1] < reader[2]:
            raise ValueError(
                f"{case}: writer change must occur between reader observations"
            )
        if dirty and not reader[2] < writer[2] < reader[3]:
            raise ValueError(f"{case}: rollback must follow the dirty observation")
        if not dirty and not writer[2] < reader[2]:
            raise ValueError(f"{case}: writer must commit before the second read")
        if events[-1].tx != "LAB":
            raise ValueError(f"{case}: PASS must follow both completed transactions")


class Timeline:
    """Draws six transaction timelines from a validated journal."""

    def __init__(self, journal: Journal) -> None:
        self.journal = journal

    def save(self, destination: Path) -> None:
        self.journal.validate()
        figure = Figure(figsize=(16, 16), layout="constrained")
        axes = figure.subplots(3, 2)
        for axis, (case, (isolation, initial, expected)) in zip(
            axes.flat, SCENARIOS.items()
        ):
            events = [
                event
                for event in self.journal.events
                if event.case == case and event.tx != "LAB"
            ]
            origin = events[0].elapsed_ms
            for tx, y, color in (("T1", 1, "#2166ac"), ("T2", 0, "#b35806")):
                transaction = [event for event in events if event.tx == tx]
                times = [event.elapsed_ms - origin for event in transaction]
                axis.plot(
                    times,
                    [y] * len(times),
                    "o-",
                    color=color,
                    linewidth=2,
                    markersize=5,
                )
                for event, elapsed in zip(transaction, times):
                    label = (
                        "AFTER ROLLBACK"
                        if event.event == "READ_AFTER_ROLLBACK"
                        else event.event.replace("_", " ")
                    )
                    if event.value is not None:
                        label += f" = {event.value}"
                    above = bool(y) != (event.event in ("COMMIT", "ROLLBACK"))
                    axis.annotate(
                        label,
                        (elapsed, y),
                        xytext=(
                            -4 if event.event == "READ_2" else 4,
                            10 if above else -10,
                        ),
                        textcoords="offset points",
                        rotation=90,
                        va="bottom" if above else "top",
                        ha="center",
                        fontsize=8,
                        color=color,
                    )
            result = (
                "phantom absent on this H2 version"
                if case == "phantom_rr"
                else "verified observation"
            )
            axis.set_title(
                f"{case}\n{isolation}: read {initial} → {expected}\n{result}"
            )
            axis.set_yticks([0, 1], ["T2 writer", "T1 reader"])
            axis.set_ylim(-1.4, 2.4)
            axis.set_xlabel("Measured milliseconds since this case began")
            axis.grid(axis="x", alpha=0.2)
            axis.margins(x=0.12)
        figure.suptitle(
            "H2 2.5.252 / Python + JDBC / two transactions",
            fontsize=15,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(destination, dpi=160)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("journal", type=Path)
    parser.add_argument("png", type=Path)
    args = parser.parse_args()
    Timeline(Journal.load(args.journal)).save(args.png)


if __name__ == "__main__":
    main()
