from transactions import (
    dirty_read,
    non_repeatable_read,
    phantom_read,
    serialization_anomaly,
)


def main() -> None:
    dirty_read.main()
    non_repeatable_read.main()
    phantom_read.main()
    serialization_anomaly.main()
    print("\nAll transaction isolation demonstrations passed.")


if __name__ == "__main__":
    main()
