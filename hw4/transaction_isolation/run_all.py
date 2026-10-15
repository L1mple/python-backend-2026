from transaction_isolation.dirty_read import main as dirty_read
from transaction_isolation.non_repeatable_read import main as non_repeatable_read
from transaction_isolation.phantom_read import main as phantom_read
from transaction_isolation.serialization import main as serialization


def main() -> None:
    dirty_read()
    non_repeatable_read()
    phantom_read()
    serialization()


if __name__ == "__main__":
    main()
