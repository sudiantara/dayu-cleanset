from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import psycopg
import json
import urllib.request

app = FastAPI(
    title="Dayu Cleanset Laundry API",
    version="0.2.0"
)


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL belum diset")

    return database_url


def get_db_connection():
    return psycopg.connect(get_database_url())


N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "http://n8n-app:5678/webhook/dayu-cleanset-notification"
)


def send_n8n_event(event: str, message: str, data: Optional[dict] = None):
    payload = {
        "event": event,
        "message": message,
        "data": data or {}
    }

    request_data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        N8N_WEBHOOK_URL,
        data=request_data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return {
                "success": True,
                "status_code": response.status
            }

    except Exception as error:
        print(f"[N8N ERROR] {error}")

        return {
            "success": False,
            "error": str(error)
        }


class OrderItemRequest(BaseModel):
    service_id: int
    quantity: float = 1
    weight: Optional[float] = None
    description: Optional[str] = None


class CreateOrderRequest(BaseModel):
    customer_id: int

    hotel_name: str
    room_number: Optional[str] = None
    location_notes: Optional[str] = None

    service_speed: str = "NORMAL"
    requested_finish_at: Optional[str] = None

    total_weight: float

    instagram_followed: bool = False
    google_reviewed: bool = False

    special_discount: float = 0
    special_discount_reason: Optional[str] = None

    pickup_type: str = "CUSTOMER_DROP"
    notes: Optional[str] = None
    created_by: Optional[int] = 1


class UpdateOrderStatusRequest(BaseModel):
    status: str
    note: Optional[str] = None
    changed_by: Optional[int] = 1


class CreatePaymentRequest(BaseModel):
    amount: float
    payment_method: str
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[int] = 1


class MarkPaidRequest(BaseModel):
    payment_method: str = "CASH"
    reference_number: Optional[str] = None
    notes: Optional[str] = "Pelunasan order"
    created_by: Optional[int] = 1


@app.get("/")
def root():
    return {
        "app": "Dayu Cleanset Laundry",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/health/database")
def database_health():

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

        return {
            "status": "healthy",
            "database": "connected",
            "result": result[0]
        }

    except Exception as error:

        return {
            "status": "error",
            "database": "disconnected",
            "message": str(error)
        }


@app.get("/api/customers")
def get_customers():

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                cursor.execute("""
                    SELECT
                        id,
                        name,
                        phone,
                        address,
                        notes,
                        created_at
                    FROM customers
                    ORDER BY id
                """)

                rows = cursor.fetchall()

        customers = []

        for row in rows:
            customers.append({
                "id": row[0],
                "name": row[1],
                "phone": row[2],
                "address": row[3],
                "notes": row[4],
                "created_at": row[5].isoformat()
            })

        return customers

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


@app.get("/api/services")
def get_services():

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                cursor.execute("""
                    SELECT
                        id,
                        name,
                        pricing_type,
                        price,
                        unit,
                        description,
                        is_active
                    FROM services
                    WHERE is_active = TRUE
                    ORDER BY id
                """)

                rows = cursor.fetchall()

        services = []

        for row in rows:
            services.append({
                "id": row[0],
                "name": row[1],
                "pricing_type": row[2],
                "price": float(row[3]),
                "unit": row[4],
                "description": row[5],
                "is_active": row[6]
            })

        return services

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


@app.post("/api/orders")
def create_order(request: CreateOrderRequest):

    try:
        with get_db_connection() as connection:

            with connection.cursor() as cursor:

                # =========================
                # CEK CUSTOMER
                # =========================

                cursor.execute(
                    """
                    SELECT
                id,
                name,
                phone,
                address
                FROM customers
                WHERE id = %s
                """,
                    (request.customer_id,)
                )

                customer = cursor.fetchone()

                if not customer:
                    raise HTTPException(
                        status_code=404,
                        detail="Customer tidak ditemukan"
                    )

                customer_id = customer[0]
                customer_name = customer[1]
                customer_phone = customer[2]
                customer_address = customer[3]


                # =========================
                # GENERATE ORDER NUMBER
                # =========================

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM orders
                    WHERE created_at::date = CURRENT_DATE
                    """
                )

                order_count = cursor.fetchone()[0] + 1

                cursor.execute(
                    """
                    SELECT
                        'DL-' ||
                        TO_CHAR(CURRENT_DATE, 'YYYYMMDD') ||
                        '-' ||
                        LPAD(%s::text, 4, '0')
                    """,
                    (order_count,)
                )

                order_number = cursor.fetchone()[0]


                # =========================
                # SERVICE SPEED & PRICE
                # =========================

                service_speed = request.service_speed.upper()

                if service_speed not in ["NORMAL", "EXPRESS"]:
                    raise HTTPException(
                        status_code=400,
                        detail="Service speed harus NORMAL atau EXPRESS"
                    )

                if request.total_weight <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Berat laundry harus lebih dari 0 KG"
                    )

                if service_speed == "NORMAL":
                    price_per_kg = 30000

                else:
                    price_per_kg = 55000

                total_weight = request.total_weight

                subtotal = total_weight * price_per_kg


                # =========================
                # PROMO INSTAGRAM + GOOGLE
                # =========================

                if (
                    request.instagram_followed
                    and request.google_reviewed
                ):
                    promo_discount = subtotal * 0.05

                else:
                    promo_discount = 0


                # =========================
                # SPECIAL DISCOUNT / NEGO
                # =========================

                special_discount = request.special_discount or 0

                if special_discount < 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Special discount tidak boleh negatif"
                    )


                # =========================
                # TOTAL DISCOUNT
                # =========================

                discount = promo_discount + special_discount

                if discount > subtotal:
                    raise HTTPException(
                        status_code=400,
                        detail="Total diskon tidak boleh melebihi subtotal"
                    )

                total = subtotal - discount




                # =========================
                # INSERT ORDER
                # =========================

                cursor.execute(
                    """
                    INSERT INTO orders
                    (
                        order_number,
                        customer_id,
                        status,
                        pickup_type,

                        hotel_name,
                        room_number,
                        location_notes,

                        service_speed,
                        requested_finish_at,

                        total_weight,

                        instagram_followed,
                        google_reviewed,
                        promo_discount,

                        special_discount,
                        special_discount_reason,

                        subtotal,
                        discount,
                        total,

                        payment_status,
                        notes,
                        created_by
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        'NEW',
                        %s,

                        %s,
                        %s,
                        %s,

                        %s,
                        %s,

                        %s,

                        %s,
                        %s,
                        %s,

                        %s,
                        %s,

                        %s,
                        %s,
                        %s,

                        'UNPAID',
                        %s,
                        %s
                    )
                    RETURNING id
                    """,
                    (
                        order_number,
                        request.customer_id,
                        request.pickup_type,

                        request.hotel_name,
                        request.room_number,
                        request.location_notes,

                        service_speed,
                        request.requested_finish_at,

                        total_weight,

                        request.instagram_followed,
                        request.google_reviewed,
                        promo_discount,

                        special_discount,
                        request.special_discount_reason,

                        subtotal,
                        discount,
                        total,

                        request.notes,
                        request.created_by
                    )
                )

                order_id = cursor.fetchone()[0]


                # =========================
                # INSERT INITIAL HISTORY
                # =========================

                cursor.execute(
                    """
                    INSERT INTO order_status_history
                    (
                        order_id,
                        status,
                        note,
                        changed_by
                    )
                    VALUES
                    (
                        %s,
                        'NEW',
                        'Laundry diterima dari customer',
                        %s
                    )
                    """,
                    (
                        order_id,
                        request.created_by
                    )
                )


            connection.commit()

        send_n8n_event(
            event="ORDER_CREATED",
            message=f"Order baru {order_number}",
            data={
                "order_id": order_id,
                "order_number": order_number,

                "customer_id": customer_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,

                "hotel_name": request.hotel_name,
                "room_number": request.room_number,
                "location_notes": request.location_notes,

                "service_speed": service_speed,
                "requested_finish_at": request.requested_finish_at,

                "status": "NEW",

                "total_weight": total_weight,
                "price_per_kg": price_per_kg,

                "subtotal": subtotal,
                "promo_discount": promo_discount,
                "special_discount": special_discount,
                "discount": discount,
                "total": total,

                "instagram_followed": request.instagram_followed,
                "google_reviewed": request.google_reviewed,

                "payment_status": "UNPAID"
            }
        )

        return {
            "status": "success",
            "message": "Order berhasil dibuat",
            "order": {
                "id": order_id,
                "order_number": order_number,

                "customer_id": request.customer_id,

                "hotel_name": request.hotel_name,
                "room_number": request.room_number,
                "location_notes": request.location_notes,

                "service_speed": service_speed,
                "requested_finish_at": request.requested_finish_at,

                "status": "NEW",

                "total_weight": total_weight,
                "price_per_kg": price_per_kg,

                "subtotal": subtotal,
                "promo_discount": promo_discount,
                "special_discount": special_discount,
                "discount": discount,
                "total": total,

                "payment_status": "UNPAID"
            
            }
        }


    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )



@app.get("/api/orders")
def get_orders():

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                cursor.execute("""
                    SELECT
                        o.id,
                        o.order_number,
                        c.name AS customer,
                        c.phone,
                        o.status,
                        o.pickup_type,
                        o.total_weight,
                        o.subtotal,
                        o.discount,
                        o.total,
                        o.payment_status,
                        o.created_at
                    FROM orders o
                    JOIN customers c
                        ON c.id = o.customer_id
                    ORDER BY o.id DESC
                """)

                rows = cursor.fetchall()

        orders = []

        for row in rows:
            orders.append({
                "id": row[0],
                "order_number": row[1],
                "customer": row[2],
                "phone": row[3],
                "status": row[4],
                "pickup_type": row[5],
                "total_weight": float(row[6]) if row[6] is not None else 0,
                "subtotal": float(row[7]),
                "discount": float(row[8]),
                "total": float(row[9]),
                "payment_status": row[10],
                "created_at": row[11].isoformat()
            })

        return orders

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


@app.get("/api/orders/{order_number}")
def get_order_detail(order_number: str):

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                # =========================
                # ORDER HEADER
                # =========================

                cursor.execute("""
                    SELECT
                        o.id,
                        o.order_number,
                        c.id AS customer_id,
                        c.name AS customer,
                        c.phone,
                        c.address,
                        o.status,
                        o.pickup_type,
                        o.total_weight,
                        o.subtotal,
                        o.discount,
                        o.total,
                        o.payment_status,
                        o.notes,
                        o.created_at,
                        o.updated_at,
                        o.completed_at
                    FROM orders o
                    JOIN customers c
                        ON c.id = o.customer_id
                    WHERE o.order_number = %s
                """, (order_number,))

                order = cursor.fetchone()

                if not order:
                    raise HTTPException(
                        status_code=404,
                        detail="Order tidak ditemukan"
                    )


                # =========================
                # ORDER ITEMS
                # =========================

                cursor.execute("""
                    SELECT
                        oi.id,
                        s.id AS service_id,
                        s.name AS service_name,
                        oi.description,
                        oi.quantity,
                        oi.weight,
                        oi.price,
                        oi.subtotal
                    FROM order_items oi
                    JOIN services s
                        ON s.id = oi.service_id
                    WHERE oi.order_id = %s
                    ORDER BY oi.id
                """, (order[0],))

                item_rows = cursor.fetchall()

                items = []

                for row in item_rows:
                    items.append({
                        "id": row[0],
                        "service_id": row[1],
                        "service_name": row[2],
                        "description": row[3],
                        "quantity": float(row[4]),
                        "weight": float(row[5]) if row[5] is not None else None,
                        "price": float(row[6]),
                        "subtotal": float(row[7])
                    })


                # =========================
                # STATUS HISTORY
                # =========================

                cursor.execute("""
                    SELECT
                        osh.id,
                        osh.status,
                        osh.note,
                        u.name AS changed_by,
                        osh.changed_at
                    FROM order_status_history osh
                    LEFT JOIN users u
                        ON u.id = osh.changed_by
                    WHERE osh.order_id = %s
                    ORDER BY osh.changed_at
                """, (order[0],))

                history_rows = cursor.fetchall()

                history = []

                for row in history_rows:
                    history.append({
                        "id": row[0],
                        "status": row[1],
                        "note": row[2],
                        "changed_by": row[3],
                        "changed_at": row[4].isoformat()
                    })


        return {
            "id": order[0],
            "order_number": order[1],

            "customer": {
                "id": order[2],
                "name": order[3],
                "phone": order[4],
                "address": order[5]
            },

            "status": order[6],
            "pickup_type": order[7],
            "total_weight": float(order[8]) if order[8] is not None else 0,
            "subtotal": float(order[9]),
            "discount": float(order[10]),
            "total": float(order[11]),
            "payment_status": order[12],
            "notes": order[13],

            "created_at": order[14].isoformat(),
            "updated_at": order[15].isoformat(),
            "completed_at": order[16].isoformat() if order[16] else None,

            "items": items,
            "history": history
        }


    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


@app.patch("/api/orders/{order_number}/status")
def update_order_status(
    order_number: str,
    request: UpdateOrderStatusRequest
):

    allowed_statuses = [
        "NEW",
        "RECEIVED",
        "WASHING",
        "DRYING",
        "IRONING",
        "READY",
        "DELIVERING",
        "PICKED_UP",
        "CANCELLED"
    ]

    new_status = request.status.upper()

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Status tidak valid"
        )

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                cursor.execute("""
                    SELECT
                        o.id,
                        o.status,
                        c.name,
                        c.phone,
                        c.address
                    FROM orders o
                    JOIN customers c
                        ON c.id = o.customer_id
                    WHERE o.order_number = %s
                """, (order_number,))

                order = cursor.fetchone()

                if not order:
                    raise HTTPException(
                        status_code=404,
                        detail="Order tidak ditemukan"
                    )

                order_id = order[0]
                old_status = order[1]
                customer_name = order[2]
                customer_phone = order[3]
                customer_address = order[4]

                cursor.execute("""
                    SELECT name
                    FROM users
                    WHERE id = %s
                """, (request.changed_by,))

                user = cursor.fetchone()

                if user:
                    operator_name = user[0]
                else:
                    operator_name = f"User ID {request.changed_by}"

                if old_status == new_status:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Order sudah berstatus {new_status}"
                    )

                completed_at = None

                if new_status in ["PICKED_UP", "CANCELLED"]:
                    cursor.execute("""
                        UPDATE orders
                        SET
                            status = %s,
                            updated_at = NOW(),
                            completed_at = NOW()
                        WHERE id = %s
                    """, (new_status, order_id))

                else:
                    cursor.execute("""
                        UPDATE orders
                        SET
                            status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (new_status, order_id))

                note = request.note

                if not note:
                    note = f"Status berubah dari {old_status} menjadi {new_status}"

                cursor.execute("""
                    INSERT INTO order_status_history
                    (
                        order_id,
                        status,
                        note,
                        changed_by
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                """, (
                    order_id,
                    new_status,
                    note,
                    request.changed_by
                ))

            connection.commit()

        send_n8n_event(
            event="STATUS_CHANGED",
            message=f"Status order {order_number} berubah",
            data={
                "order_number": order_number,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "customer_address": customer_address,
                "old_status": old_status,
                "new_status": new_status,
                "note": note,
                "changed_by": operator_name
            }
        )

        return {
            "status": "success",
            "message": "Status order berhasil diperbarui",
            "order_number": order_number,
            "old_status": old_status,
            "new_status": new_status
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )



@app.get("/api/summary/today")
def get_today_summary():

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                cursor.execute("""
                    SELECT (NOW() AT TIME ZONE 'Asia/Makassar')::date
                """)

                summary_date = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT
                        COUNT(*) AS total_orders,
                        COALESCE(SUM(total_weight), 0) AS total_weight,
                        COALESCE(SUM(subtotal), 0) AS subtotal,
                        COALESCE(SUM(discount), 0) AS discount,
                        COALESCE(SUM(total), 0) AS total_amount,
                        COUNT(*) FILTER (
                            WHERE payment_status = 'PAID'
                        ) AS paid_orders,
                        COUNT(*) FILTER (
                            WHERE payment_status = 'UNPAID'
                        ) AS unpaid_orders,
                        COUNT(*) FILTER (
                        WHERE payment_status = 'PARTIAL'
                        ) AS partial_orders,
                        COALESCE(SUM(total) FILTER (
                            WHERE payment_status = 'PAID'
                        ), 0) AS paid_amount,
                        COALESCE(SUM(total) FILTER (
                            WHERE payment_status = 'UNPAID'
                        ), 0) AS unpaid_amount,
                        COALESCE(SUM(total) FILTER (
                            WHERE payment_status = 'PARTIAL'
                        ), 0) AS partial_amount
                    FROM orders
                    WHERE (created_at AT TIME ZONE 'Asia/Makassar')::date
                   = (NOW() AT TIME ZONE 'Asia/Makassar')::date
                """)

                summary = cursor.fetchone()

                cursor.execute("""
                    SELECT
                        status,
                        COUNT(*)
            FROM orders
            WHERE (created_at AT TIME ZONE 'Asia/Makassar')::date
              = (NOW() AT TIME ZONE 'Asia/Makassar')::date
            GROUP BY status
            ORDER BY status
                """)

                status_rows = cursor.fetchall()

                status_summary = {}

                for row in status_rows:
                    status_summary[row[0]] = row[1]

        return {
            "date": str(summary_date),
            "total_orders": summary[0],
            "total_weight": float(summary[1]),
            "subtotal": float(summary[2]),
            "discount": float(summary[3]),
            "total_amount": float(summary[4]),

            "payment": {
                "paid_orders": summary[5],
                "unpaid_orders": summary[6],
                "partial_orders": summary[7],
                "paid_amount": float(summary[8]),
                "unpaid_amount": float(summary[9]),
                "partial_amount": float(summary[10])
            },

            "status": status_summary
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )



@app.post("/api/orders/{order_number}/payments")
def create_payment(
    order_number: str,
    request: CreatePaymentRequest
):

    if request.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Nominal pembayaran harus lebih dari 0"
        )

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                # =========================
                # CEK ORDER
                # =========================


                cursor.execute("""
                    SELECT
                        o.id,
                        o.total,
                        o.payment_status,
                        c.name,
                        c.phone,
                        c.address
                    FROM orders o
                    JOIN customers c
                        ON c.id = o.customer_id
                    WHERE o.order_number = %s
                """, (order_number,))

                order = cursor.fetchone()

                if not order:
                    raise HTTPException(
                        status_code=404,
                        detail="Order tidak ditemukan"
                    )

                order_id = order[0]
                order_total = float(order[1])
                customer_name = order[3]
                customer_phone = order[4]
                customer_address = order[5]


                # =========================
                # TOTAL PEMBAYARAN SEBELUMNYA
                # =========================

                cursor.execute("""
                    SELECT
                        COALESCE(SUM(amount), 0)
                    FROM payments
                    WHERE order_id = %s
                """, (order_id,))

                paid_before = float(cursor.fetchone()[0])


                # =========================
                # VALIDASI OVERPAYMENT
                # =========================

                new_paid_total = paid_before + request.amount

                if new_paid_total > order_total:
                    raise HTTPException(
                        status_code=400,
                        detail="Nominal pembayaran melebihi total tagihan"
                    )


                # =========================
                # INSERT PAYMENT
                # =========================

                cursor.execute("""
                    INSERT INTO payments
                    (
                        order_id,
                        amount,
                        payment_method,
                        reference_number,
                        notes,
                        created_by
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id, paid_at
                """, (
                    order_id,
                    request.amount,
                    request.payment_method.upper(),
                    request.reference_number,
                    request.notes,
                    request.created_by
                ))

                payment = cursor.fetchone()


                # =========================
                # PAYMENT STATUS
                # =========================

                if new_paid_total == 0:
                    payment_status = "UNPAID"

                elif new_paid_total < order_total:
                    payment_status = "PARTIAL"

                else:
                    payment_status = "PAID"


                cursor.execute("""
                    UPDATE orders
                    SET
                        payment_status = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (
                    payment_status,
                    order_id
                ))

            connection.commit()

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT name
                    FROM users
                    WHERE id = %s
                """, (request.created_by,))

                user = cursor.fetchone()

                if user:
                    operator_name = user[0]
                else:
                    operator_name = f"User ID {request.created_by}"

        send_n8n_event(
            event="PAYMENT_RECEIVED",
            message=f"Pembayaran diterima untuk order {order_number}",
            data={
                "order_number": order_number,

                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "customer_address": customer_address,

                "amount": request.amount,
                "payment_method": request.payment_method.upper(),

                "order_total": order_total,
                "paid_before": paid_before,
                "paid_total": new_paid_total,
                "remaining": order_total - new_paid_total,
                "payment_status": payment_status,

                "notes": request.notes,
                "operator": operator_name
            }
        )

        return {
            "status": "success",
            "message": "Pembayaran berhasil dicatat",
            "payment": {
                "id": payment[0],
                "order_number": order_number,
                "amount": request.amount,
                "payment_method": request.payment_method.upper(),
                "paid_at": payment[1].isoformat()
            },
            "billing": {
                "order_total": order_total,
                "paid_before": paid_before,
                "paid_total": new_paid_total,
                "remaining": order_total - new_paid_total,
                "payment_status": payment_status
            }
        }


    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


@app.post("/api/orders/{order_number}/mark-paid")
def mark_order_paid(
    order_number: str,
    request: MarkPaidRequest
):

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                # =========================
                # CEK ORDER + CUSTOMER
                # =========================

                cursor.execute("""
                    SELECT
                        o.id,
                        o.total,
                        o.payment_status,
                        c.name,
                        c.phone,
                        c.address
                    FROM orders o
                    JOIN customers c
                        ON c.id = o.customer_id
                    WHERE o.order_number = %s
                """, (order_number,))

                order = cursor.fetchone()

                if not order:
                    raise HTTPException(
                        status_code=404,
                        detail="Order tidak ditemukan"
                    )

                order_id = order[0]
                order_total = float(order[1])
                current_payment_status = order[2]

                customer_name = order[3]
                customer_phone = order[4]
                customer_address = order[5]

                if current_payment_status == "PAID":
                    raise HTTPException(
                        status_code=400,
                        detail="Order sudah lunas"
                    )

                # =========================
                # HITUNG TOTAL BAYAR
                # =========================

                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM payments
                    WHERE order_id = %s
                """, (order_id,))

                paid_before = float(cursor.fetchone()[0])

                remaining = order_total - paid_before

                if remaining <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Tidak ada sisa tagihan"
                    )

                # =========================
                # INSERT PELUNASAN
                # =========================

                cursor.execute("""
                    INSERT INTO payments
                    (
                        order_id,
                        amount,
                        payment_method,
                        reference_number,
                        notes,
                        created_by
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id, paid_at
                """, (
                    order_id,
                    remaining,
                    request.payment_method.upper(),
                    request.reference_number,
                    request.notes,
                    request.created_by
                ))

                payment = cursor.fetchone()

                cursor.execute("""
                    UPDATE orders
                    SET
                        payment_status = 'PAID',
                        updated_at = NOW()
                    WHERE id = %s
                """, (order_id,))

            connection.commit()

        # =========================
        # OPERATOR
        # =========================

        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                cursor.execute("""
                    SELECT name
                    FROM users
                    WHERE id = %s
                """, (request.created_by,))

                user = cursor.fetchone()

                if user:
                    operator_name = user[0]
                else:
                    operator_name = f"User ID {request.created_by}"

        paid_total = paid_before + remaining

        # =========================
        # TELEGRAM
        # =========================

        send_n8n_event(
            event="PAYMENT_RECEIVED",
            message=f"Order {order_number} telah dilunasi",
            data={
                "order_number": order_number,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "customer_address": customer_address,

                "amount": remaining,
                "payment_method": request.payment_method.upper(),

                "order_total": order_total,
                "paid_before": paid_before,
                "paid_total": paid_total,
                "remaining": 0,
                "payment_status": "PAID",

                "notes": request.notes,
                "operator": operator_name
            }
        )

        return {
            "status": "success",
            "message": "Order berhasil ditandai lunas",
            "order_number": order_number,

            "payment": {
                "id": payment[0],
                "amount": remaining,
                "payment_method": request.payment_method.upper(),
                "paid_at": payment[1].isoformat()
            },

            "billing": {
                "order_total": order_total,
                "paid_before": paid_before,
                "paid_total": paid_total,
                "remaining": 0,
                "payment_status": "PAID"
            }
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )
