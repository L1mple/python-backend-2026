
from sqlalchemy import delete, select

from transactions.database import (
    Product,
    SessionLocal,
    init_db,
)


PRICE_LIMIT = 100.0


def prepare_data() -> None:
    with SessionLocal() as session:
        session.execute(delete(Product))

        session.add_all([
            Product(name="Product 1", price=150.0),
            Product(name="Product 2", price=200.0),
            Product(name="Product 3", price=50.0),
        ])

        session.commit()


def get_expensive_products(session):
    return session.scalars(
        select(Product).where(Product.price > PRICE_LIMIT)
    ).all()


def demonstrate_phantom_read() -> None:
    print("\n========== PHANTOM READ ==========\n")

    transaction_a = SessionLocal()
    transaction_b = SessionLocal()

    try:
        transaction_a.begin()

        first_result = get_expensive_products(transaction_a)
        first_names = {product.name for product in first_result}

        print("Transaction A: first SELECT")
        print(f"Products: {sorted(first_names)}")
        print(f"Count: {len(first_names)}")

        transaction_b.begin()

        transaction_b.add(
            Product(
                name="New Product",
                price=150.0,
            )
        )

        transaction_b.commit()

        print("\nTransaction B: inserted New Product (150.0)")
        print("Transaction B: COMMIT")

        second_result = get_expensive_products(transaction_a)
        second_names = {product.name for product in second_result}

        print("\nTransaction A: second SELECT")
        print(f"Products: {sorted(second_names)}")
        print(f"Count: {len(second_names)}")

        if first_names == second_names:
            print("\nNo phantom read detected.")
            print("Transaction A sees its original snapshot.")
        else:
            print("\nPHANTOM READ DETECTED!")

        assert first_names == {"Product 1", "Product 2"}
        assert second_names == first_names

        transaction_a.commit()

        print("\nTransaction A: COMMIT")
        print("SUCCESS: SQLite preserved the read snapshot.")

    finally:
        transaction_a.close()
        transaction_b.close()


if __name__ == "__main__":
    init_db()
    prepare_data()
    demonstrate_phantom_read()
