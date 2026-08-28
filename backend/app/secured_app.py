import json
from typing import Optional

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel

from app.auth_app import (
    COOKIE_NAME,
    _load_active_user,
    app,
    parse_session_token,
)
from app.main import get_db_connection


class UpdateCustomerRequest(BaseModel):
    name: str
    phone: str
    address: Optional[str] = None
    notes: Optional[str] = None


def required_roles(path: str, method: str):
    method = method.upper()

    if path.startswith("/api/admin/users"):
        return {"ADMIN"}

    if path.startswith("/api/customers/") and method == "DELETE":
        return {"ADMIN"}

    if path.startswith("/api/customers/") and method == "PATCH":
        return {"ADMIN", "KASIR"}

    if method == "DELETE" and path.startswith("/api/orders/"):
        return {"ADMIN"}

    if method == "POST" and path.rstrip("/") == "/api/customers":
        return {"ADMIN", "KASIR"}

    if path.startswith("/api/orders"):
        if method == "POST" and path.rstrip("/") == "/api/orders":
            return {"ADMIN", "KASIR"}
        if "/payments" in path or path.endswith("/mark-paid"):
            return {"ADMIN", "KASIR"}
        if path.endswith("/edit-v2"):
            return {"ADMIN", "KASIR"}
        if path.endswith("/status-v2") or path.endswith("/status"):
            return {"ADMIN", "KASIR", "STAFF"}

    return None


@app.middleware("http")
async def strict_role_middleware(request: Request, call_next):
    allowed = required_roles(request.url.path, request.method)
    if not allowed:
        return await call_next(request)

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return Response(
            content=json.dumps({"detail": "Silakan login"}),
            status_code=401,
            media_type="application/json",
        )

    try:
        payload = parse_session_token(token)
        user = _load_active_user(int(payload["uid"]))
    except Exception:
        return Response(
            content=json.dumps({"detail": "Sesi login tidak valid"}),
            status_code=401,
            media_type="application/json",
        )

    if user["role"] not in allowed:
        return Response(
            content=json.dumps({"detail": "Role user tidak memiliki izin untuk aksi ini"}),
            status_code=403,
            media_type="application/json",
        )

    return await call_next(request)


@app.get("/api/orders-list-v2")
def get_orders_list_v2():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    o.id,
                    o.order_number,
                    c.name AS customer,
                    c.phone,
                    o.hotel_name,
                    o.room_number,
                    o.service_speed,
                    o.status,
                    o.total_weight,
                    o.subtotal,
                    o.discount,
                    o.total,
                    o.payment_status,
                    o.requested_finish_at,
                    o.created_at,
                    u.name AS received_by
                FROM orders o
                JOIN customers c ON c.id = o.customer_id
                LEFT JOIN users u ON u.id = o.created_by
                ORDER BY o.id DESC
                """
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "order_number": row[1],
            "customer": row[2],
            "phone": row[3],
            "hotel_name": row[4],
            "room_number": row[5],
            "service_speed": row[6],
            "status": row[7],
            "total_weight": float(row[8]) if row[8] is not None else 0,
            "subtotal": float(row[9]),
            "discount": float(row[10]),
            "total": float(row[11]),
            "payment_status": row[12],
            "requested_finish_at": row[13].isoformat() if row[13] else None,
            "created_at": row[14].isoformat(),
            "received_by": row[15],
        }
        for row in rows
    ]


@app.get("/api/customers-list-v2")
def get_customers_list_v2():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.id,
                    c.name,
                    c.phone,
                    c.address,
                    c.notes,
                    c.created_at,
                    COUNT(o.id) AS order_count,
                    COALESCE(SUM(o.total), 0) AS lifetime_value,
                    MAX(o.created_at) AS last_order_at
                FROM customers c
                LEFT JOIN orders o ON o.customer_id = c.id
                GROUP BY c.id, c.name, c.phone, c.address, c.notes, c.created_at
                ORDER BY c.id DESC
                """
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "name": row[1],
            "phone": row[2],
            "address": row[3],
            "notes": row[4],
            "created_at": row[5].isoformat(),
            "order_count": row[6],
            "lifetime_value": float(row[7]),
            "last_order_at": row[8].isoformat() if row[8] else None,
        }
        for row in rows
    ]


@app.get("/api/customers/{customer_id}/orders-v2")
def get_customer_orders_v2(customer_id: int):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name, phone FROM customers WHERE id = %s", (customer_id,))
            customer = cursor.fetchone()
            if not customer:
                raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
            cursor.execute(
                """
                SELECT order_number, status, payment_status, service_speed,
                       total_weight, total, hotel_name, room_number, created_at
                FROM orders
                WHERE customer_id = %s
                ORDER BY id DESC
                """,
                (customer_id,),
            )
            rows = cursor.fetchall()

    return {
        "customer": {"id": customer[0], "name": customer[1], "phone": customer[2]},
        "orders": [
            {
                "order_number": row[0],
                "status": row[1],
                "payment_status": row[2],
                "service_speed": row[3],
                "total_weight": float(row[4] or 0),
                "total": float(row[5]),
                "hotel_name": row[6],
                "room_number": row[7],
                "created_at": row[8].isoformat(),
            }
            for row in rows
        ],
    }


@app.patch("/api/customers/{customer_id}")
def update_customer_v2(customer_id: int, payload: UpdateCustomerRequest):
    name = payload.name.strip()
    phone = payload.phone.strip()
    if not name or not phone:
        raise HTTPException(status_code=400, detail="Nama dan nomor HP wajib diisi")

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM customers WHERE LOWER(TRIM(phone)) = LOWER(TRIM(%s)) AND id <> %s LIMIT 1",
                (phone, customer_id),
            )
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail="Nomor WhatsApp / HP sudah digunakan customer lain")
            cursor.execute(
                """
                UPDATE customers
                SET name = %s, phone = %s, address = %s, notes = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING id, name, phone, address, notes, updated_at
                """,
                (name, phone, payload.address, payload.notes, customer_id),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
        connection.commit()

    return {
        "id": row[0], "name": row[1], "phone": row[2], "address": row[3],
        "notes": row[4], "updated_at": row[5].isoformat(),
    }


@app.delete("/api/customers/{customer_id}")
def delete_customer_v2(customer_id: int):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM orders WHERE customer_id = %s", (customer_id,))
            order_count = cursor.fetchone()[0]
            if order_count:
                raise HTTPException(
                    status_code=409,
                    detail=f"Customer memiliki {order_count} order dan tidak boleh dihapus",
                )
            cursor.execute("DELETE FROM customers WHERE id = %s RETURNING id", (customer_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
        connection.commit()
    return {"status": "success"}


@app.get("/api/payments-list-v2")
def get_payments_list_v2():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.id,
                    o.order_number,
                    c.name,
                    c.phone,
                    p.amount,
                    p.payment_method,
                    p.reference_number,
                    p.notes,
                    p.paid_at,
                    u.name AS operator
                FROM payments p
                JOIN orders o ON o.id = p.order_id
                JOIN customers c ON c.id = o.customer_id
                LEFT JOIN users u ON u.id = p.created_by
                ORDER BY p.paid_at DESC, p.id DESC
                """
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "order_number": row[1],
            "customer": row[2],
            "phone": row[3],
            "amount": float(row[4]),
            "payment_method": row[5],
            "reference_number": row[6],
            "notes": row[7],
            "paid_at": row[8].isoformat(),
            "operator": row[9],
        }
        for row in rows
    ]


@app.get("/api/service-config-v2")
def get_service_config_v2():
    return {
        "normal": {"name": "NORMAL", "price_per_kg": 30000, "sla": "Maksimal 1 hari"},
        "express": {"name": "EXPRESS", "price_per_kg": 55000, "sla": "Di bawah 6 jam"},
        "promo": {
            "percent": 5,
            "require_instagram": True,
            "require_google_review": True,
            "description": "Promo 5% berlaku jika customer follow Instagram dan review Google Maps.",
        },
    }
