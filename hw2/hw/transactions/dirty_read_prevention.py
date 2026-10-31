
from sqlalchemy import delete, select, update
from sqlalchemy.exc import OperationalError

from transactions.database import (
    DirtySessionLocal,
    Product,
    init_db,
)


PRODUCT_NAME = "Test product"
INITIAL_PRICE = 100.0
UPDATED_PRICE = 999.0


def prepare_data() -> None:
    with DirtySessionLocal() as session:
        session.execute(delete(Product))
        session.add(
            Product(
                name=PRODUCT_NAME,
                price=INITIAL_PRICE,
            )
        )
        session.commit()


def demonstrate_dirty_read_prevention() -> None:
    print("\n========== DIRTY READ PREVENTION ==========\n")

    writer = DirtySessionLocal()
    reader = DirtySessionLocal()

    try:
        reader.connection().exec_driver_sql(
            "PRAGMA read_uncommitted = 0"
        )

        writer.begin()

        writer.execute(
            update(Product)
            .where(Product.name == PRODUCT_NAME)
            .values(price=UPDATED_PRICE)
        )

        print(
            f"Transaction A: changed price "
            f"from {INITIAL_PRICE} to {UPDATED_PRICE}"
        )
        print("Transaction A: changes are NOT committed")

        try:
            price = reader.scalar(
                select(Product.price).where(
                    Product.name == PRODUCT_NAME
                )
            )

            print(f"\nTransaction B: read price = {price}")

            if price == UPDATED_PRICE:
                print("ERROR: DIRTY READ DETECTED!")
            else:
                print("No dirty read: uncommitted value is invisible.")

        except OperationalError as error:
            print("\nTransaction B: read was blocked.")
            print(f"SQLite message: {error}")

            print(
                "No dirty read: SQLite prevented access "
                "to the locked table."
            )

        finally:
            reader.rollback()

        writer.rollback()
        print("\nTransaction A: ROLLBACK")

        with DirtySessionLocal() as check_session:
            actual_price = check_session.scalar(
                select(Product.price).where(
                    Product.name == PRODUCT_NAME
                )
            )

        print(f"Committed price after rollback = {actual_price}")

        assert actual_price == INITIAL_PRICE

        print("SUCCESS: dirty read was prevented.")

    finally:
        writer.close()
        reader.close()


if __name__ == "__main__":
    init_db()
    prepare_data()
    demonstrate_dirty_read_prevention()
