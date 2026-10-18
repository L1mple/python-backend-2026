import pytest

from isolation.scenarios import SCENARIOS


@pytest.mark.parametrize(
    "run, expected",
    [(run, expected) for _, run, expected, _ in SCENARIOS],
    ids=[title for title, *_ in SCENARIOS],
)
def test_isolation_scenario(run, expected: bool) -> None:
    assert run() is expected
