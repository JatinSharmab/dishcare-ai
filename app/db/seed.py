import asyncio
from datetime import date, timedelta

from app.core.security import hash_password
from app.db.database import Database

DEMO_PASSWORD = "DemoPass123!"


async def seed_database(db: Database):

    existing = await db.fetch_one(
        "SELECT customer_id FROM customers LIMIT 1"
    )

    if existing:
        return

    today = date.today()

    future_expiry = (
        today + timedelta(days=30)
    ).isoformat()

    expired_date = (
        today - timedelta(days=2)
    ).isoformat()

    offer_expiry = (
        today + timedelta(days=14)
    ).isoformat()

    customer_hashes = [
        await asyncio.to_thread(
            hash_password,
            DEMO_PASSWORD,
        )
        for _ in range(3)
    ]

    customers = [
        (
            "CUST001",
            "Aarav Sharma",
            "DEMO-PHONE-001",
            customer_hashes[0],
            35000,
            1,
        ),
        (
            "CUST002",
            "Priya Verma",
            "DEMO-PHONE-002",
            customer_hashes[1],
            29900,
            1,
        ),
        (
            "CUST003",
            "Rahul Singh",
            "DEMO-PHONE-003",
            customer_hashes[2],
            0,
            1,
        ),
    ]

    packs = [
        ("BASIC", "Basic Hindi Pack", 19900),
        ("FAMILY", "Family Entertainment Pack", 29900),
        ("PREMIUM", "Premium HD Pack", 49900),
    ]

    channels = [
        ("SPORTS_HD", "Sports HD", 5000),
        ("MOVIES_HD", "Movies HD", 3500),
        ("NEWS_HD", "News HD", 2000),
    ]

    subscriptions = [
        ("CUST001", "FAMILY", "active", future_expiry),
        ("CUST002", "BASIC", "inactive", future_expiry),
        ("CUST003", "BASIC", "inactive", expired_date),
    ]

    payments = [
        ("PAY001", "CUST001", 35000, "success"),
        ("PAY002", "CUST002", 29900, "success"),
        ("PAY003", "CUST003", 19900, "failed"),
    ]

    offers = [
        (
            "OFFER001",
            "CUST001",
            "INR 100 discount on next eligible renewal",
            10000,
            offer_expiry,
        ),
        (
            "OFFER002",
            "CUST002",
            "INR 50 discount on next eligible renewal",
            5000,
            offer_expiry,
        ),
    ]

    async with db.transaction() as conn:

        async with conn.execute(
            "SELECT customer_id FROM customers LIMIT 1"
        ) as cursor:
            if await cursor.fetchone():
                return

        await conn.executemany(
            """
            INSERT INTO customers
            (
                customer_id, name, phone,
                password_hash, balance_paise, enabled
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            customers,
        )

        await conn.executemany(
            """
            INSERT INTO packs
            VALUES (?, ?, ?)
            """,
            packs,
        )

        await conn.executemany(
            """
            INSERT INTO channels
            VALUES (?, ?, ?)
            """,
            channels,
        )

        await conn.executemany(
            """
            INSERT INTO subscriptions
            VALUES (?, ?, ?, ?)
            """,
            subscriptions,
        )

        await conn.executemany(
            """
            INSERT INTO payments
            (payment_id, customer_id, amount_paise, status)
            VALUES (?, ?, ?, ?)
            """,
            payments,
        )

        await conn.executemany(
            """
            INSERT INTO retention_offers
            (
                offer_id, customer_id, description,
                discount_paise, valid_until
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            offers,
        )

        await conn.execute(
            """
            INSERT INTO customer_channels
            VALUES (?, ?)
            """,
            ("CUST001", "NEWS_HD"),
        )