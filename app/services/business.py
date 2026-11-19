from datetime import date
from uuid import uuid4

import aiosqlite

from app.core.exceptions import BusinessError
from app.db.database import Database
from app.schemas.business import TechnicianRequest


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


async def fetch_one(conn, query, params=()):
    async with conn.execute(query, params) as cursor:
        row = await cursor.fetchone()

        return dict(row) if row else None


async def fetch_all(conn, query, params=()):
    async with conn.execute(query, params) as cursor:
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]


class BusinessService:

    def __init__(self, db: Database):
        self.db = db

    # ----------------------------------
    # CRM
    # ----------------------------------

    async def get_customer(self, customer_id: str):

        customer = await self.db.fetch_one(
            """
            SELECT customer_id, name, phone
            FROM customers
            WHERE customer_id = ?
            """,
            (customer_id,),
        )

        if not customer:
            raise BusinessError(
                404,
                "CUSTOMER_NOT_FOUND",
                "Customer does not exist",
            )

        return customer

    # ----------------------------------
    # BILLING
    # ----------------------------------

    async def get_balance(self, customer_id: str):

        balance = await self.db.fetch_one(
            """
            SELECT customer_id, balance_paise
            FROM customers
            WHERE customer_id = ?
            """,
            (customer_id,),
        )

        if not balance:
            raise BusinessError(
                404,
                "CUSTOMER_NOT_FOUND",
                "Customer does not exist",
            )

        return {
            **balance,
            "currency": "INR",
        }

    async def get_payments(self, customer_id: str):

        return await self.db.fetch_all(
            """
            SELECT *
            FROM payments
            WHERE customer_id = ?
            ORDER BY created_at DESC, payment_id
            """,
            (customer_id,),
        )

    async def verify_payment(
        self,
        customer_id: str,
        payment_id: str,
    ):

        payment = await self.db.fetch_one(
            """
            SELECT *
            FROM payments
            WHERE payment_id = ?
              AND customer_id = ?
            """,
            (payment_id, customer_id),
        )

        if not payment:
            raise BusinessError(
                404,
                "PAYMENT_NOT_FOUND",
                "Payment record was not found",
            )

        return payment

    # ----------------------------------
    # PRODUCT CATALOG
    # ----------------------------------

    async def get_catalog(self):

        packs = await self.db.fetch_all(
            "SELECT * FROM packs ORDER BY pack_code"
        )

        channels = await self.db.fetch_all(
            "SELECT * FROM channels ORDER BY channel_code"
        )

        return {
            "packs": packs,
            "channels": channels,
        }

    # ----------------------------------
    # SUBSCRIPTIONS
    # ----------------------------------

    async def _subscription_details(
        self,
        conn: aiosqlite.Connection,
        customer_id: str,
    ):

        subscription = await fetch_one(
            conn,
            """
            SELECT
                s.customer_id,
                s.pack_code,
                s.status,
                s.expiry_date,
                p.name AS pack_name,
                p.monthly_fee_paise
            FROM subscriptions s
            JOIN packs p
              ON s.pack_code = p.pack_code
            WHERE s.customer_id = ?
            """,
            (customer_id,),
        )

        if not subscription:
            raise BusinessError(
                404,
                "SUBSCRIPTION_NOT_FOUND",
                "Subscription does not exist",
            )

        channels = await fetch_all(
            conn,
            """
            SELECT
                c.channel_code,
                c.name,
                c.monthly_fee_paise
            FROM customer_channels cc
            JOIN channels c
              ON cc.channel_code = c.channel_code
            WHERE cc.customer_id = ?
            ORDER BY c.channel_code
            """,
            (customer_id,),
        )

        expiry = date.fromisoformat(
            subscription["expiry_date"]
        )

        if (
            subscription["status"] == "active"
            and expiry < date.today()
        ):
            subscription["status"] = "inactive"

        total_fee = (
            subscription["monthly_fee_paise"]
            + sum(
                channel["monthly_fee_paise"]
                for channel in channels
            )
        )

        subscription["channels"] = channels
        subscription["monthly_fee_paise"] = total_fee

        return subscription

    async def get_subscription(self, customer_id: str):

        async with self.db.connection() as conn:
            await conn.execute("BEGIN")

            return await self._subscription_details(
                conn,
                customer_id,
            )

    async def _require_active(
        self,
        conn,
        customer_id: str,
    ):

        subscription = await self._subscription_details(
            conn,
            customer_id,
        )

        if subscription["status"] != "active":
            raise BusinessError(
                409,
                "SUBSCRIPTION_INACTIVE",
                "An active subscription is required",
            )

        return subscription

    async def change_pack(
        self,
        customer_id: str,
        pack_code: str,
    ):

        async with self.db.transaction() as conn:

            await self._require_active(conn, customer_id)

            pack = await fetch_one(
                conn,
                """
                SELECT pack_code
                FROM packs
                WHERE pack_code = ?
                """,
                (pack_code,),
            )

            if not pack:
                raise BusinessError(
                    404,
                    "PACK_NOT_FOUND",
                    "Requested pack does not exist",
                )

            await conn.execute(
                """
                UPDATE subscriptions
                SET pack_code = ?
                WHERE customer_id = ?
                """,
                (pack_code, customer_id),
            )

            return await self._subscription_details(
                conn,
                customer_id,
            )

    async def add_channel(
        self,
        customer_id: str,
        channel_code: str,
    ):

        async with self.db.transaction() as conn:

            await self._require_active(conn, customer_id)

            channel = await fetch_one(
                conn,
                """
                SELECT channel_code
                FROM channels
                WHERE channel_code = ?
                """,
                (channel_code,),
            )

            if not channel:
                raise BusinessError(
                    404,
                    "CHANNEL_NOT_FOUND",
                    "Requested channel does not exist",
                )

            await conn.execute(
                """
                INSERT INTO customer_channels
                (customer_id, channel_code)
                VALUES (?, ?)
                ON CONFLICT(customer_id, channel_code)
                DO NOTHING
                """,
                (customer_id, channel_code),
            )

            return await self._subscription_details(
                conn,
                customer_id,
            )

    async def remove_channel(
        self,
        customer_id: str,
        channel_code: str,
    ):

        async with self.db.transaction() as conn:

            await self._require_active(conn, customer_id)

            await conn.execute(
                """
                DELETE FROM customer_channels
                WHERE customer_id = ?
                  AND channel_code = ?
                """,
                (customer_id, channel_code),
            )

            return await self._subscription_details(
                conn,
                customer_id,
            )

    async def cancel_subscription(
        self,
        customer_id: str,
        confirmed: bool,
    ):

        if not confirmed:
            raise BusinessError(
                409,
                "CONFIRMATION_REQUIRED",
                "Customer must explicitly confirm cancellation",
            )

        async with self.db.transaction() as conn:

            await self._subscription_details(
                conn,
                customer_id,
            )

            await conn.execute(
                """
                UPDATE subscriptions
                SET status = 'cancelled'
                WHERE customer_id = ?
                """,
                (customer_id,),
            )

            return await self._subscription_details(
                conn,
                customer_id,
            )

    # ----------------------------------
    # CUSTOMER RETENTION
    # ----------------------------------

    async def get_retention_offers(
        self,
        customer_id: str,
    ):

        return await self.db.fetch_all(
            """
            SELECT *
            FROM retention_offers
            WHERE customer_id = ?
              AND valid_until >= ?
            ORDER BY discount_paise DESC
            """,
            (customer_id, date.today().isoformat()),
        )

    # ----------------------------------
    # COMPLAINT MANAGEMENT
    # ----------------------------------

    async def create_complaint(
        self,
        customer_id: str,
        category: str,
        description: str,
    ):

        complaint_id = new_id("CMP")

        async with self.db.transaction() as conn:

            await conn.execute(
                """
                INSERT INTO complaints
                (
                    complaint_id,
                    customer_id,
                    category,
                    description
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    complaint_id,
                    customer_id,
                    category,
                    description,
                ),
            )

            return await fetch_one(
                conn,
                """
                SELECT *
                FROM complaints
                WHERE complaint_id = ?
                  AND customer_id = ?
                """,
                (complaint_id, customer_id),
            )

    async def get_complaints(self, customer_id: str):

        return await self.db.fetch_all(
            """
            SELECT *
            FROM complaints
            WHERE customer_id = ?
            ORDER BY created_at DESC
            """,
            (customer_id,),
        )

    async def get_complaint(
        self,
        customer_id: str,
        complaint_id: str,
    ):

        complaint = await self.db.fetch_one(
            """
            SELECT *
            FROM complaints
            WHERE complaint_id = ?
              AND customer_id = ?
            """,
            (complaint_id, customer_id),
        )

        if not complaint:
            raise BusinessError(
                404,
                "COMPLAINT_NOT_FOUND",
                "Complaint does not exist",
            )

        return complaint

    # ----------------------------------
    # FIELD SERVICE
    # ----------------------------------

    async def book_technician(
        self,
        customer_id: str,
        request: TechnicianRequest,
    ):

        if request.visit_date <= date.today():
            raise BusinessError(
                422,
                "INVALID_VISIT_DATE",
                "Visit date must be in the future",
            )

        visit_date = request.visit_date.isoformat()

        async with self.db.transaction() as conn:

            await conn.execute(
                """
                INSERT INTO technician_bookings
                (
                    booking_id,
                    customer_id,
                    visit_date,
                    slot,
                    issue
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(customer_id, visit_date, slot)
                DO NOTHING
                """,
                (
                    new_id("BOOK"),
                    customer_id,
                    visit_date,
                    request.slot,
                    request.issue,
                ),
            )

            booking = await fetch_one(
                conn,
                """
                SELECT *
                FROM technician_bookings
                WHERE customer_id = ?
                  AND visit_date = ?
                  AND slot = ?
                """,
                (
                    customer_id,
                    visit_date,
                    request.slot,
                ),
            )

            if booking["issue"] != request.issue:
                raise BusinessError(
                    409,
                    "BOOKING_CONFLICT",
                    "A different booking already exists for this slot",
                )

            return booking

    async def get_bookings(self, customer_id: str):

        return await self.db.fetch_all(
            """
            SELECT *
            FROM technician_bookings
            WHERE customer_id = ?
            ORDER BY visit_date, slot
            """,
            (customer_id,),
        )

    # ----------------------------------
    # HUMAN ESCALATION
    # ----------------------------------

    async def escalate(
        self,
        customer_id: str,
        summary: str,
    ):

        return await self.create_complaint(
            customer_id=customer_id,
            category="human_handoff",
            description=summary,
        )