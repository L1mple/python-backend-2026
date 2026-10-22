"""
Коротенькое демо, специализированное под магазин.
"""


from psycopg import Connection, IsolationLevel
from psycopg.errors import SerializationFailure

from shop_api.database import connect


RU = IsolationLevel.READ_UNCOMMITTED
RC = IsolationLevel.READ_COMMITTED
RR = IsolationLevel.REPEATABLE_READ
SER = IsolationLevel.SERIALIZABLE
LEVEL_NAMES = {
    RU: "Чтение незавершённых данных (READ UNCOMMITTED)",
    RC: "Чтение зафиксированных данных (READ COMMITTED)",
    RR: "Повторяемое чтение (REPEATABLE READ)",
    SER: "Сериализуемый уровень (SERIALIZABLE)",
}


def reset() -> None:
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS isolation_demo_payment_methods (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                enabled BOOLEAN NOT NULL
            )
        """)
        db.execute("TRUNCATE isolation_demo_payment_methods")
        db.execute("""
            INSERT INTO isolation_demo_payment_methods (id, name, enabled)
            VALUES (1, 'Банковская карта', TRUE), (2, 'СБП', TRUE)
        """)


def scalar(db: Connection, query: str):
    row = db.execute(query).fetchone()
    return next(iter(row.values()))


def dirty_read(level: IsolationLevel) -> None:
    reset()

    with connect() as writer, connect() as reader:
        writer.isolation_level = RC
        reader.isolation_level = level

        writer.execute("""
            UPDATE isolation_demo_payment_methods
            SET enabled = FALSE
            WHERE id = 1
        """)
        observed = scalar(
            reader,
            "SELECT enabled FROM isolation_demo_payment_methods WHERE id = 1",
        )
        writer.rollback()
        after_rollback = scalar(
            reader,
            "SELECT enabled FROM isolation_demo_payment_methods WHERE id = 1",
        )
        assert observed is True, "Прочитано незакоммиченное изменение"
        assert after_rollback is True

        print(
            f"{LEVEL_NAMES[level]} - грязное чтение: Т1 отключила оплату картой "
            "без фиксации; Т2 видит её до отката Т1: "
            f"{ 'доступна' if observed else 'недоступна'}, после отката: "
            f"{ 'доступна' if after_rollback else 'недоступна'}. "
            "Незавершённое изменение не видно."
        )


def repeated_read(level: IsolationLevel, *, phantom: bool) -> None:
    reset()

    if phantom:
        query = """
            SELECT COUNT(*)
            FROM isolation_demo_payment_methods
            WHERE enabled = TRUE
        """
        mutation = """
            INSERT INTO isolation_demo_payment_methods (id, name, enabled)
            VALUES (3, 'Оплата по счёту', TRUE)
        """
    else:
        query = """
            SELECT enabled
            FROM isolation_demo_payment_methods
            WHERE id = 1
        """
        mutation = """
            UPDATE isolation_demo_payment_methods
            SET enabled = FALSE
            WHERE id = 1
        """

    with connect() as reader, connect() as writer:
        reader.isolation_level = level
        writer.isolation_level = RC

        before = scalar(reader, query)
        writer.execute(mutation)
        writer.commit()
        after = scalar(reader, query)
        changed = before != after
        assert changed == (level == RC)
        if phantom:
            visibility = "Новая строка видна." if changed else "Новая строка не видна."
            print(
                f"{LEVEL_NAMES[level]} - фантомное чтение: Т2 добавила способ "
                "оплаты по счёту и зафиксировала изменение; Т1 насчитала "
                "доступных способов до/после: "
                f"{before} -> {after}. {visibility}"
            )
        else:
            result = "Значение изменилось." if changed else "Значение не изменилось."
            print(
                f"{LEVEL_NAMES[level]} - неповторяемое чтение: Т2 отключила "
                "оплату картой и зафиксировала изменение; Т1 видит её до/после: "
                f"{'доступна' if before else 'недоступна'} -> {'доступна' if after else 'недоступна'}. "
                f"{result}"
            )


def write_skew(level: IsolationLevel) -> None:
    reset()

    count_query = """
        SELECT COUNT(*)
        FROM isolation_demo_payment_methods
        WHERE enabled = TRUE
    """
    update_query = """
        UPDATE isolation_demo_payment_methods
        SET enabled = FALSE
        WHERE id = %s
    """

    rejected = False

    with connect() as t1, connect() as t2:
        t1.isolation_level = level
        t2.isolation_level = level

        count1 = scalar(t1, count_query)
        count2 = scalar(t2, count_query)

        assert count1 == count2 == 2

        t1.execute(update_query, (1,))
        t1.commit()

        try:
            t2.execute(update_query, (2,))
            t2.commit()
        except SerializationFailure:
            t2.rollback()
            rejected = True

    with connect() as db:
        remaining = scalar(db, count_query)

    if level == RR:
        assert not rejected and remaining == 0
    else:
        assert rejected and remaining == 1
    if rejected:
        result = "Т2 отклонена; остался один доступный способ оплаты."
    else:
        result = "Обе транзакции зафиксированы; доступных способов оплаты не осталось."
    print(
        f"{LEVEL_NAMES[level]} - конфликт способов оплаты: Т1 и Т2 увидели "
        "два доступных способа; Т1 отключила карту, Т2 попыталась отключить СБП. "
        f"{result}"
    )


def main() -> None:
    try:
        for level in (RU, RC):
            dirty_read(level)

        for level in (RC, RR):
            repeated_read(level, phantom=False)

        for level in (RC, RR, SER):
            repeated_read(level, phantom=True)

        for level in (RR, SER):
            write_skew(level)
    finally:
        with connect() as db:
            db.execute("DROP TABLE IF EXISTS isolation_demo_payment_methods")


if __name__ == "__main__":
    main()
