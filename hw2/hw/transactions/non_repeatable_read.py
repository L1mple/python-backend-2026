
from sqlalchemy import delete, select, update

from transactions.database import (
    Product,
    SessionLocal,
    init_db,
)


PRODUCT_NAME = "Test product"
INITIAL_PRICE = 100.0
UPDATED_PRICE = 200.0


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


def demonstrate_non_repeatable_read() -> None:
    print("\n========== NON-REPEATABLE READ ==========\n")

    transaction_a = SessionLocal()
    transaction_b = SessionLocal()

    try:
        transaction_a.begin()

        first_price = transaction_a.scalar(
            select(Product.price).where(
                Product.name == PRODUCT_NAME
            )
        )

        print(f"Transaction A: first read = {first_price}")

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

        second_price = transaction_a.scalar(
            select(Product.price).where(
                Product.name == PRODUCT_NAME
            )
        )

        print(f"\nTransaction A: second read = {second_price}")

        if first_price == second_price:
            print("No non-repeatable read detected.")
            print("Transaction A sees its original snapshot.")
        else:
            print("NON-REPEATABLE READ DETECTED!")

        assert first_price == INITIAL_PRICE
        assert second_price == INITIAL_PRICE

        transaction_a.commit()

        print("\nTransaction A: COMMIT")
        print("SUCCESS: SQLite preserved the read snapshot.")

    finally:
        transaction_a.close()
        transaction_b.close()


if __name__ == "__main__":
    init_db()
    prepare_data()
    demonstrate_non_repeatable_read()
