
from sqlalchemy import delete, event, select, update

from transactions.database import (
    DirtySessionLocal,
    Product,
    dirty_engine,
    init_db,
)


@event.listens_for(dirty_engine, "connect")
def enable_read_uncommitted(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA read_uncommitted = 1")
    cursor.close()


PRODUCT_NAME = "Test product"
INITIAL_PRICE = 100.0
UPDATED_PRICE = 999.0


def prepare_data() -> None:
    with DirtySessionLocal() as session:
        session.execute(delete(Product))

        product = Product(
            name=PRODUCT_NAME,
            price=INITIAL_PRICE,
        )

        session.add(product)
        session.commit()


def demonstrate_dirty_read() -> None:
    print("\n========== DIRTY READ ==========\n")

    writer = DirtySessionLocal()
    reader = DirtySessionLocal()

    try:
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

        reader.begin()

        dirty_price = reader.scalar(
            select(Product.price).where(
                Product.name == PRODUCT_NAME
            )
        )

        print(f"\nTransaction B: read price = {dirty_price}")

        if dirty_price == UPDATED_PRICE:
            print("DIRTY READ DETECTED!")
        else:
            print("Dirty read was NOT detected.")

        writer.rollback()

        print("\nTransaction A: ROLLBACK")

        actual_price = reader.scalar(
            select(Product.price).where(
                Product.name == PRODUCT_NAME
            )
        )

        print(
            f"Transaction B: price after rollback = "
            f"{actual_price}"
        )

        if actual_price == INITIAL_PRICE:
            print("The uncommitted modification disappeared.")
        else:
            print("Unexpected database state.")

        reader.rollback()

    finally:
        writer.close()
        reader.close()


if __name__ == "__main__":
    init_db()
    prepare_data()
    demonstrate_dirty_read()
