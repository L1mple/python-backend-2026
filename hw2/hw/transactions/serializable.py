from sqlalchemy import delete, select, update
from sqlalchemy.exc import OperationalError

from transactions.database import (
    Product,
    SessionLocal,
    init_db,
)


PRODUCT_NAME = "Test product"
INITIAL_PRICE = 100.0
UPDATED_PRICE = 200.0
CONFLICTING_PRICE = 150.0


def prepare_data() -> None:
    with SessionLocal() as session:
        session.execute(delete(Product))
        session.add(
            Product(
                name=PRODUCT_NAME,
                price=INITIAL_PRICE,
            )
        )
        session.commit()


def demonstrate_serializable() -> None:
    print("\n========== SERIALIZABLE ==========\n")

    transaction_a = SessionLocal()
    transaction_b = SessionLocal()

    try:
        transaction_a.begin()

        initial_price = transaction_a.scalar(
            select(Product.price).where(
                Product.name == PRODUCT_NAME
            )
        )

        print(f"Transaction A: read price = {initial_price}")

        transaction_b.begin()

        transaction_b.execute(
            update(Product)
            .where(Product.name == PRODUCT_NAME)
            .values(price=UPDATED_PRICE)
        )

        transaction_b.commit()

        print(
            f"Transaction B: updated price to {UPDATED_PRICE}"
        )
        print("Transaction B: COMMIT")

        print(
            f"\nTransaction A: trying to update price "
            f"to {CONFLICTING_PRICE}"
        )

        try:
            transaction_a.execute(
                update(Product)
                .where(Product.name == PRODUCT_NAME)
                .values(price=CONFLICTING_PRICE)
            )

            transaction_a.commit()

            print("Transaction A: UPDATE succeeded.")

        except OperationalError as error:
            print("Transaction A: UPDATE was rejected.")
            print(f"SQLite message: {error.orig}")

            transaction_a.rollback()

            print("Transaction A: ROLLBACK")
            print("Concurrent modification conflict detected.")

        with SessionLocal() as check_session:
            final_price = check_session.scalar(
                select(Product.price).where(
                    Product.name == PRODUCT_NAME
                )
            )

        print(f"\nFinal committed price = {final_price}")

        assert final_price == UPDATED_PRICE

        print("SUCCESS: stale transaction could not overwrite "
              "committed data.")

    finally:
        transaction_a.close()
        transaction_b.close()


if __name__ == "__main__":
    init_db()
    prepare_data()
    demonstrate_serializable()