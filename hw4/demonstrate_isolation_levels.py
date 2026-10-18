import os
from typing import NamedTuple

from psycopg.errors import SerializationFailure
from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.exc import OperationalError

DEFAULT_DATABASE_URL = "postgresql+psycopg://shop:shop@localhost:5432/shop"

demo_metadata = MetaData()
demo_items_table = Table(
    "isolation_demo_items",
    demo_metadata,
    Column(
        "id",
        Integer,
        primary_key=True,
    ),
    Column(
        "name",
        String,
        nullable=False,
    ),
    Column(
        "price",
        Float,
        nullable=False,
    ),
    Column(
        "deleted",
        Boolean,
        nullable=False,
    ),
)
SELECT_PRICE_OF_KETTLE = select(demo_items_table.c.price).where(demo_items_table.c.id == 1)


class AnomalyCheckResult(NamedTuple):
    anomaly_name: str
    isolation_level: str
    anomaly_happened: bool
    observation: str


class IsolationLevelsDemonstration:
    def __init__(
        self,
        database_url: str,
    ) -> None:
        self.engine = create_engine(database_url)
        demo_metadata.create_all(bind=self.engine)

    def check_dirty_read(
        self,
        isolation_level: str,
    ) -> AnomalyCheckResult:
        self._reset_demo_items()
        with (
            self._connect(isolation_level="READ COMMITTED") as writer_connection,
            self._connect(isolation_level=isolation_level) as reader_connection,
        ):
            writer_connection.begin()
            writer_connection.execute(
                update(demo_items_table).where(demo_items_table.c.id == 1).values(price=500.0),
            )
            reader_connection.begin()
            price_seen_by_reader = reader_connection.scalar(SELECT_PRICE_OF_KETTLE)
            writer_connection.rollback()
            reader_connection.commit()
        return AnomalyCheckResult(
            anomaly_name="dirty read",
            isolation_level=isolation_level,
            anomaly_happened=price_seen_by_reader == 500.0,
            observation=f"writer set price 100 -> 500 without commit, reader saw {price_seen_by_reader}",
        )

    def check_non_repeatable_read(
        self,
        isolation_level: str,
    ) -> AnomalyCheckResult:
        self._reset_demo_items()
        with (
            self._connect(isolation_level=isolation_level) as reader_connection,
            self._connect(isolation_level="READ COMMITTED") as writer_connection,
        ):
            reader_connection.begin()
            first_price_seen_by_reader = reader_connection.scalar(SELECT_PRICE_OF_KETTLE)
            writer_connection.begin()
            writer_connection.execute(
                update(demo_items_table).where(demo_items_table.c.id == 1).values(price=200.0),
            )
            writer_connection.commit()
            second_price_seen_by_reader = reader_connection.scalar(SELECT_PRICE_OF_KETTLE)
            reader_connection.commit()
        return AnomalyCheckResult(
            anomaly_name="non-repeatable read",
            isolation_level=isolation_level,
            anomaly_happened=first_price_seen_by_reader != second_price_seen_by_reader,
            observation=(
                f"reader saw price {first_price_seen_by_reader}, writer committed 200, "
                f"reader saw {second_price_seen_by_reader}"
            ),
        )

    def check_phantom_read(
        self,
        isolation_level: str,
    ) -> AnomalyCheckResult:
        self._reset_demo_items()
        count_items_cheaper_than_1000 = (
            select(func.count()).select_from(demo_items_table).where(demo_items_table.c.price < 1000.0)
        )
        with (
            self._connect(isolation_level=isolation_level) as reader_connection,
            self._connect(isolation_level="READ COMMITTED") as writer_connection,
        ):
            reader_connection.begin()
            first_count_seen_by_reader = reader_connection.scalar(count_items_cheaper_than_1000)
            writer_connection.begin()
            writer_connection.execute(
                insert(demo_items_table).values(
                    id=3,
                    name="toaster",
                    price=300.0,
                    deleted=False,
                ),
            )
            writer_connection.commit()
            second_count_seen_by_reader = reader_connection.scalar(count_items_cheaper_than_1000)
            reader_connection.commit()
        return AnomalyCheckResult(
            anomaly_name="phantom read",
            isolation_level=isolation_level,
            anomaly_happened=first_count_seen_by_reader != second_count_seen_by_reader,
            observation=(
                f"reader counted {first_count_seen_by_reader} items cheaper than 1000, writer inserted one, "
                f"reader counted {second_count_seen_by_reader}"
            ),
        )

    def check_serialization_anomaly(
        self,
        isolation_level: str,
    ) -> AnomalyCheckResult:
        # Write skew: the shop must keep at least one item on sale. Each transaction sees two items on sale
        # and removes a different one, so each is valid alone, but together they remove both.
        self._reset_demo_items()
        count_items_on_sale = (
            select(func.count()).select_from(demo_items_table).where(demo_items_table.c.deleted.is_(False))
        )
        with (
            self._connect(isolation_level=isolation_level) as first_connection,
            self._connect(isolation_level=isolation_level) as second_connection,
        ):
            first_connection.begin()
            second_connection.begin()
            items_on_sale_seen_by_first = first_connection.scalar(count_items_on_sale)
            items_on_sale_seen_by_second = second_connection.scalar(count_items_on_sale)
            if items_on_sale_seen_by_first > 1:
                first_connection.execute(
                    update(demo_items_table).where(demo_items_table.c.id == 1).values(deleted=True),
                )
            if items_on_sale_seen_by_second > 1:
                second_connection.execute(
                    update(demo_items_table).where(demo_items_table.c.id == 2).values(deleted=True),
                )
            first_connection.commit()
            try:
                second_connection.commit()
                outcome_of_second_transaction = "committed"
            except OperationalError as commit_error:
                if not isinstance(commit_error.orig, SerializationFailure):
                    raise
                outcome_of_second_transaction = "rolled back with a serialization failure"
        with self.engine.connect() as checking_connection:
            items_left_on_sale = checking_connection.scalar(count_items_on_sale)
        return AnomalyCheckResult(
            anomaly_name="serialization anomaly",
            isolation_level=isolation_level,
            anomaly_happened=items_left_on_sale == 0,
            observation=(
                f"both saw {items_on_sale_seen_by_first} and {items_on_sale_seen_by_second} items on sale "
                f"and removed one each, second transaction {outcome_of_second_transaction}, "
                f"items left on sale: {items_left_on_sale}"
            ),
        )

    def _connect(
        self,
        isolation_level: str,
    ) -> Connection:
        return self.engine.connect().execution_options(isolation_level=isolation_level)

    def _reset_demo_items(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(delete(demo_items_table))
            connection.execute(
                insert(demo_items_table),
                [
                    {"id": 1, "name": "kettle", "price": 100.0, "deleted": False},
                    {"id": 2, "name": "mug", "price": 50.0, "deleted": False},
                ],
            )


def main() -> None:
    demonstration = IsolationLevelsDemonstration(
        database_url=os.environ.get(
            "DATABASE_URL",
            DEFAULT_DATABASE_URL,
        ),
    )
    # Postgres runs READ UNCOMMITTED as READ COMMITTED and has no phantoms on REPEATABLE READ,
    # so the phantom is shown on READ COMMITTED and the serialization anomaly on REPEATABLE READ
    anomaly_check_results = [
        demonstration.check_dirty_read(isolation_level="READ UNCOMMITTED"),
        demonstration.check_dirty_read(isolation_level="READ COMMITTED"),
        demonstration.check_non_repeatable_read(isolation_level="READ COMMITTED"),
        demonstration.check_non_repeatable_read(isolation_level="REPEATABLE READ"),
        demonstration.check_phantom_read(isolation_level="READ COMMITTED"),
        demonstration.check_phantom_read(isolation_level="REPEATABLE READ"),
        demonstration.check_phantom_read(isolation_level="SERIALIZABLE"),
        demonstration.check_serialization_anomaly(isolation_level="REPEATABLE READ"),
        demonstration.check_serialization_anomaly(isolation_level="SERIALIZABLE"),
    ]
    for anomaly_check_result in anomaly_check_results:
        anomaly_status = "YES" if anomaly_check_result.anomaly_happened else "no"
        print(
            f"{anomaly_check_result.anomaly_name:<22} {anomaly_check_result.isolation_level:<17} "
            f"anomaly: {anomaly_status:<4} {anomaly_check_result.observation}"
        )


if __name__ == "__main__":
    main()
